"""对比「纯整图 OCR」与「整图 OCR + 检测框标注」两条链路的解析结果。

链路 B 与 routes/invoice_routes._recognize_image 保持一致：整图 OCR 打底，
检测框只用来给文本块打字段标签，再补全正则没抽到的字段。

用法:
    python test_pipeline_compare.py 001 002 003        # 用标注 JSON 当作理想检测框
    python test_pipeline_compare.py --det yolov8 001   # 用真实检测模型
"""
import copy
import json
import os
import sys

from services.ocr_manager import switch_engine, recognize, get_full_text
from services.image_processor import preprocess
from services.invoice_parser import parse_invoice, tag_items_with_fields, fill_from_detections

FIELDS = ['invoice_type', 'invoice_code', 'invoice_number', 'invoice_date',
          'buyer_name', 'buyer_tax_id', 'seller_name', 'seller_tax_id',
          'amount', 'tax_amount', 'total_amount', 'check_code']

# 检测模型能覆盖的标签（与 convert_to_yolov8.LABEL_MAP 保持一致）
LABEL_KEEP = {'发票代码', '发票号码', '发票日期', '购买方名称',
              '购买方纳税人识别号', '购买方纳税人税别号', '价税合计',
              '增值税电子普通发票', '电子普通发票', '增值税专用发票', '增值税普通发票'}


def load_gt_boxes(json_path, img_shape):
    """把标注 JSON 里的框缩放到 preprocess 之后的图片尺寸，模拟"检测 100% 准确"。"""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    jw, jh = data.get('imageWidth', 0), data.get('imageHeight', 0)
    h, w = img_shape[:2]
    sx = w / jw if jw else 1
    sy = h / jh if jh else 1
    dets = []
    for shape in data.get('shapes', []):
        if shape['label'] not in LABEL_KEEP:
            continue
        xs = [p[0] * sx for p in shape['points']]
        ys = [p[1] * sy for p in shape['points']]
        dets.append({'class_name': shape['label'], 'confidence': 1.0,
                     'bbox': [min(xs), min(ys), max(xs), max(ys)]})
    return dets


def detect_pipeline(items, detections, base_parsed):
    """复刻线上链路：标注字段归属 -> 解析 -> 用检测区域补全空字段。"""
    tag_items_with_fields(items, detections)
    for det in detections:
        name = det['class_name']
        hit = [it['text'] for it in items if it.get('field_name') == name]
        print(f"    [标注] {name:12s} 命中文本块 {hit if hit else '无'}")
    parsed = copy.deepcopy(base_parsed)
    filled = fill_from_detections(parsed, items)
    print(f"  检测补全的字段: {filled if filled else '无（正则已全部抽到）'}")
    return parsed


def find_image(base):
    for ext in ('png', 'jpg', 'jpeg'):
        p = os.path.join('data', f'{base}.{ext}')
        if os.path.exists(p):
            return p
    return None


def main():
    args = sys.argv[1:]
    detector = None
    if args and args[0] == '--det':
        detector = args[1]
        args = args[2:]
    targets = args or ['001']

    switch_engine('paddle')
    if detector:
        from services.detector_manager import switch_detector, detect_fields
        switch_detector(detector)

    for base in targets:
        img_path = find_image(base)
        if not img_path:
            print(f'跳过 {base}: 找不到图片')
            continue
        img = preprocess(img_path)
        print(f'\n{"#" * 70}\n# {base}  预处理后尺寸 {img.shape[1]}x{img.shape[0]}\n{"#" * 70}')

        # 链路 A: 纯整图 OCR（等价于单独跑 PaddleOCR）
        whole_items = recognize(img)
        whole_text = get_full_text(whole_items)
        whole_parsed = parse_invoice(whole_items, whole_text)

        # 链路 B: 整图 OCR + 检测框标注补全
        if detector:
            dets = detect_fields(img)
        else:
            json_path = os.path.join('data', 'labelsJson', f'{base}.json')
            if not os.path.exists(json_path):
                print(f'跳过 {base}: 缺少标注 {json_path}')
                continue
            dets = load_gt_boxes(json_path, img.shape)
        print(f'  检测框 {len(dets)} 个: {[d["class_name"] for d in dets]}')
        det_parsed = detect_pipeline(whole_items, dets, whole_parsed)

        print(f'\n  {"字段":<22s}{"纯整图OCR(基线)":<34s}{"整图+检测标注":<34s}')
        print('  ' + '-' * 88)
        for k in FIELDS:
            a = str(whole_parsed.get(k) or '-')
            b = str(det_parsed.get(k) or '-')
            a_ok = a not in ('-', '未知类型')
            b_ok = b not in ('-', '未知类型')
            if a == b:
                flag = ''
            elif a_ok and not b_ok:
                flag = '  <<< 检测链路丢失(不应出现)'
            elif a_ok and b_ok:
                flag = '  <<< 两者不一致'
            else:
                flag = '  <<< 检测链路补全'
            print(f'  {k:<22s}{a:<34s}{b:<34s}{flag}')

        print(f'\n  ===== 整图链路拼出的 full_text =====\n{whole_text}')


if __name__ == '__main__':
    main()
