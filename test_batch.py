"""批量测试 data/001-010 发票识别效果，输出解析字段和 OCR 明细供人工核对。"""
import glob
import json
import os
import sys

from services.ocr_manager import switch_engine, recognize, get_full_text
from services.image_processor import preprocess
from services.invoice_parser import parse_invoice

FIELDS = ['invoice_type', 'invoice_code', 'invoice_number', 'invoice_date',
          'buyer_name', 'buyer_tax_id', 'seller_name', 'seller_tax_id',
          'amount', 'tax_amount', 'total_amount', 'check_code']


def main():
    switch_engine('paddle')
    files = []
    for i in range(1, 11):
        for ext in ('png', 'jpg', 'jpeg'):
            p = f'data/{i:03d}.{ext}'
            if os.path.exists(p):
                files.append(p)
                break

    dump = {}
    for path in files:
        name = os.path.basename(path)
        try:
            img = preprocess(path)
            items = recognize(img)
            full_text = get_full_text(items)
            result = parse_invoice(items, full_text)
        except Exception as e:
            print(f'===== {name} ERROR: {e}')
            continue

        print(f'===== {name} =====')
        for k in FIELDS:
            mark = '  [缺失]' if not result[k] or result[k] == '未知类型' else ''
            print(f'  {k:15s}: {result[k]}{mark}')
        dump[name] = {
            'parsed': result,
            'items': [{'x': it['x'], 'y': it['y'], 'text': it['text']} for it in items],
            'full_text': full_text,
        }

    with open('test_batch_dump.json', 'w', encoding='utf-8') as f:
        json.dump(dump, f, ensure_ascii=False, indent=1)
    print('\n明细已写入 test_batch_dump.json')


if __name__ == '__main__':
    main()
