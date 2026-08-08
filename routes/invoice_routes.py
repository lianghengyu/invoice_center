import os
import uuid
import time
import zipfile
import cv2
import numpy as np
import base64
from flask import Blueprint, request, jsonify, send_file, after_this_request
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS, SAVED_FOLDER
from services.image_processor import preprocess, pdf_to_images
from services.ocr_manager import recognize, get_full_text, get_current_engine
from services.detector_manager import detect_fields, get_current_detector, VALID_DETECTORS
from services.invoice_parser import parse_invoice
from services.excel_exporter import export_to_excel, DEFAULT_FILENAME
from services.report_service import create_batch, record_recognition

invoice_bp = Blueprint('invoice', __name__, url_prefix='/api/invoice')

BOX_COLORS = {
    '发票代码': (255, 0, 0),
    '发票号码': (0, 200, 0),
    '发票日期': (0, 100, 255),
    '购买方名称': (255, 165, 0),
    '购买方纳税人识别号': (128, 0, 128),
    '价税合计': (0, 200, 200),
    '增值税电子普通发票': (200, 0, 200),
}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _draw_detections(img, detections):
    from PIL import Image, ImageDraw, ImageFont
    vis = img.copy()
    vis_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(vis_rgb)
    draw = ImageDraw.Draw(pil_img)

    font = None
    for font_path in [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]:
        try:
            font = ImageFont.truetype(font_path, 16)
            break
        except:
            continue
    if font is None:
        font = ImageFont.load_default()

    for det in detections:
        name = det['class_name']
        x1, y1, x2, y2 = [int(v) for v in det['bbox']]
        color = BOX_COLORS.get(name, (100, 100, 100))
        color_rgb = tuple(color)

        draw.rectangle([x1, y1, x2, y2], outline=color_rgb, width=3)

        label = f"{name} {det['confidence']:.2f}"
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        label_y = max(0, y1 - th - 4)
        draw.rectangle([x1, label_y, x1 + tw + 6, label_y + th + 4], fill=color_rgb)
        draw.text((x1 + 3, label_y + 2), label, fill=(255, 255, 255), font=font)

    vis_result = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return vis_result


def _img_to_base64(img):
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf).decode('utf-8')


def _recognize_image(img, filename):
    start_time = time.time()
    try:
        detector = get_current_detector()
        print(f"[调试] detector类型: {type(detector).__name__ if detector else 'None'}")
        
        detected_fields = []
        vis_img = None
        detections = []

        # 阶段1: 目标检测（PyTorch）
        if detector is not None:
            try:
                detections = detect_fields(img)
                detected_fields = [d['class_name'] for d in detections]
                print(f"[检测] {filename}: 检测到 {len(detections)} 个字段 -> {detected_fields}")
                if detections:
                    vis_img = _draw_detections(img, detections)
                    print(f"[调试] vis_img形状: {vis_img.shape}")
                else:
                    print(f"[调试] 检测结果为空，不画框")
            except Exception as e:
                print(f"[检测] {filename}: 检测失败，降级到纯OCR: {e}")
                import traceback
                traceback.print_exc()
                detections = []
        else:
            print(f"[调试] 检测模型未加载，使用纯OCR")

        # 阶段2: OCR识别（PaddlePaddle）
        if detections:
            ocr_items = []
            for det in detections:
                if det['class_name'] == '发票':
                    continue
                try:
                    x1, y1, x2, y2 = [int(v) for v in det['bbox']]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)
                    if x2 <= x1 or y2 <= y1:
                        continue
                    crop = img[y1:y2, x1:x2]
                    crop_ocr = recognize(crop)
                    for item in crop_ocr:
                        item['field_name'] = det['class_name']
                    ocr_items.extend(crop_ocr)
                except Exception as e:
                    print(f"[OCR裁剪] {det['class_name']} 识别失败: {e}")
                    continue

            full_text = get_full_text(ocr_items)
            parsed = parse_invoice(ocr_items, full_text)
            parsed['detected_fields'] = detected_fields
        else:
            ocr_items = recognize(img)
            full_text = get_full_text(ocr_items)
            parsed = parse_invoice(ocr_items, full_text)

        parsed['filename'] = filename
        parsed['raw_text'] = full_text
        parsed['duration'] = round(time.time() - start_time, 2)

        if vis_img is not None:
            parsed['preview_image'] = _img_to_base64(vis_img)
            print(f"[调试] preview_image已生成，长度: {len(parsed['preview_image'])}")
        else:
            print(f"[调试] preview_image未生成（vis_img为None）")

        print(f"[完成] {filename}: 耗时 {parsed['duration']}s")
        return parsed
    except Exception as e:
        print(f"[错误] {filename}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'filename': filename,
            'error': str(e),
            'duration': round(time.time() - start_time, 2),
        }


@invoice_bp.route('/recognize', methods=['POST'])
def recognize_invoices():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    results = []
    for f in files:
        if not f or not f.filename:
            continue
        if not _allowed_file(f.filename):
            results.append({
                'filename': f.filename,
                'error': f'不支持的文件格式，仅支持 {", ".join(ALLOWED_EXTENSIONS)}',
            })
            continue

        ext = f.filename.rsplit('.', 1)[1].lower()
        saved_name = f"{uuid.uuid4().hex}.{ext}"
        saved_path = os.path.join(UPLOAD_FOLDER, saved_name)
        f.save(saved_path)

        try:
            if ext == 'pdf':
                pages = pdf_to_images(saved_path)
                for page_num, img in pages:
                    label = f"{f.filename} (第{page_num}页)" if len(pages) > 1 else f.filename
                    result = _recognize_image(img, label)
                    results.append(result)
            else:
                processed = preprocess(saved_path)
                result = _recognize_image(processed, f.filename)
                results.append(result)
        except Exception as e:
            results.append({'filename': f.filename, 'error': str(e)})
        finally:
            if os.path.exists(saved_path):
                os.remove(saved_path)

    # 记录到报表数据库
    ocr_engine = get_current_engine()
    detector_name = get_current_detector() or 'none'
    success_count = len([r for r in results if 'error' not in r])
    batch_id = create_batch(len(results), success_count, ocr_engine, detector_name)
    for r in results:
        record_recognition(batch_id, r)

    return jsonify({'success': True, 'results': results})


@invoice_bp.route('/save-results', methods=['POST'])
def save_results():
    data = request.get_json()
    if not data or not data.get('results'):
        return jsonify({'success': False, 'message': '无识别结果可保存'}), 400

    results = data['results']
    filepath = export_to_excel(results, DEFAULT_FILENAME)

    return jsonify({
        'success': True,
        'filename': DEFAULT_FILENAME,
        'saved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(results),
    })


@invoice_bp.route('/saved-files', methods=['GET'])
def list_saved_files():
    files = []
    if os.path.exists(SAVED_FOLDER):
        for f in sorted(os.listdir(SAVED_FOLDER), reverse=True):
            if f.endswith('.xlsx'):
                full_path = os.path.join(SAVED_FOLDER, f)
                stat = os.stat(full_path)
                files.append({
                    'filename': f,
                    'size': stat.st_size,
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_ctime)),
                })
    return jsonify({'success': True, 'files': files})


@invoice_bp.route('/saved-files/<filename>', methods=['GET'])
def download_saved_file(filename):
    filepath = os.path.join(SAVED_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': '文件不存在'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@invoice_bp.route('/saved-files/<filename>', methods=['DELETE'])
def delete_saved_file(filename):
    filepath = os.path.join(SAVED_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': '文件不存在'}), 404
    os.remove(filepath)
    return jsonify({'success': True})


def _extract_images_from_xlsx(xlsx_path):
    images = []
    with zipfile.ZipFile(xlsx_path, 'r') as zf:
        media_files = [n for n in zf.namelist() if n.startswith('xl/media/')]
        for i, name in enumerate(sorted(media_files), 1):
            ext = name.rsplit('.', 1)[-1].lower()
            if ext not in ('png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'emf', 'wmf'):
                continue
            data = zf.read(name)
            arr = np.frombuffer(data, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                images.append((f"图片{i}.{ext}", img))
    return images


@invoice_bp.route('/batch-export', methods=['POST'])
def batch_export():
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    if not f.filename.lower().endswith('.xlsx'):
        return jsonify({'success': False, 'message': '仅支持 .xlsx 格式'}), 400

    saved_name = f"{uuid.uuid4().hex}.xlsx"
    saved_path = os.path.join(UPLOAD_FOLDER, saved_name)
    f.save(saved_path)

    try:
        images = _extract_images_from_xlsx(saved_path)
    except Exception as e:
        if os.path.exists(saved_path):
            os.remove(saved_path)
        return jsonify({'success': False, 'message': f'读取 Excel 失败: {e}'}), 400

    if os.path.exists(saved_path):
        os.remove(saved_path)

    if not images:
        return jsonify({'success': False, 'message': 'Excel 中未找到嵌入的图片'}), 400

    results = []
    for name, img in images:
        result = _recognize_image(img, name)
        results.append(result)

    success_results = [r for r in results if 'error' not in r]
    export_name = f"发票识别结果_{uuid.uuid4().hex[:8]}.xlsx"
    filepath = export_to_excel(success_results if success_results else results, export_name)

    @after_this_request
    def cleanup(response):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError:
            pass
        return response

    return send_file(filepath, as_attachment=True, download_name=export_name,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@invoice_bp.route('/switch-engine', methods=['POST'])
def switch_engine():
    data = request.get_json()
    engine = data.get('engine', '')
    try:
        from services.ocr_manager import switch_engine as _switch_engine
        _switch_engine(engine)
        return jsonify({'success': True, 'engine': engine})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'切换引擎失败: {str(e)}'}), 500


@invoice_bp.route('/current-engine', methods=['GET'])
def current_engine():
    from services.ocr_manager import get_current_engine, get_available_engines
    return jsonify({
        'success': True,
        'current': get_current_engine(),
        'available': get_available_engines(),
    })


@invoice_bp.route('/switch-detector', methods=['POST'])
def switch_detector_route():
    data = request.get_json()
    detector = data.get('detector', 'none')
    try:
        from services.detector_manager import switch_detector as _switch_detector
        _switch_detector(detector)
        return jsonify({'success': True, 'detector': detector})
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'切换检测模型失败: {str(e)}'}), 500


@invoice_bp.route('/current-detector', methods=['GET'])
def current_detector():
    name = get_current_detector()
    if not name or name == 'none':
        name = 'none'
    return jsonify({
        'success': True,
        'current': name,
        'available': VALID_DETECTORS,
    })
