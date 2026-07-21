import os
import uuid
import time
import zipfile
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, send_file, after_this_request
from config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS
from services.image_processor import preprocess, pdf_to_images
from services.ocr_service import recognize, get_full_text
from services.invoice_parser import parse_invoice
from services.excel_exporter import export_to_excel

invoice_bp = Blueprint('invoice', __name__, url_prefix='/api/invoice')


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _recognize_image(img, filename):
    start_time = time.time()
    try:
        ocr_items = recognize(img)
        full_text = get_full_text(ocr_items)
        parsed = parse_invoice(ocr_items, full_text)
        parsed['filename'] = filename
        parsed['raw_text'] = full_text
        parsed['duration'] = round(time.time() - start_time, 2)
        return parsed
    except Exception as e:
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

    return jsonify({'success': True, 'results': results})


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
