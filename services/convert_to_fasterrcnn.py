import os
import json
import glob
import random
import shutil
import torch
import cv2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLASS_NAMES = [
    '__background__',
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
    '发票',
]

LABEL_MAP = {
    '发票': 8,
    '发票代码': 1,
    '发票号码': 2,
    '发票日期': 3,
    '购买方名称': 4,
    '购买方纳税人识别号': 5,
    '购买方纳税人税别号': 5,
    '价税合计': 6,
    '增值税电子普通发票': 7,
    '电子普通发票': 7,
    '增值税专用发票': 7,
    '增值税普通发票': 7,
}

JSON_DIR = os.path.join(BASE_DIR, "data/labelsJson")
TXT_DIR = os.path.join(BASE_DIR, "data/labelsTxt")
IMG_DIRS = [
    os.path.join(BASE_DIR, "data/normal"),
    os.path.join(BASE_DIR, "data/special"),
    os.path.join(BASE_DIR, "data/synthetic"),
    os.path.join(BASE_DIR, "data/synthetic_v2"),
]
OUT_DIR = os.path.join(BASE_DIR, "data/fasterrcnn")


def find_image(base):
    for d in IMG_DIRS:
        for ext in ['png', 'jpg', 'jpeg']:
            p = os.path.join(d, f"{base}.{ext}")
            if os.path.exists(p):
                return p
    return None


def convert_one(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    boxes = []
    labels = []

    for shape in data.get('shapes', []):
        label = shape['label']
        if label not in LABEL_MAP:
            continue
        if shape['shape_type'] != 'rectangle':
            continue

        pts = shape['points']
        x1, y1 = pts[0]
        x2, y2 = pts[1]
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)

        boxes.append([x1, y1, x2, y2])
        labels.append(LABEL_MAP[label])

    if not boxes:
        return None

    return {
        'boxes': torch.as_tensor(boxes, dtype=torch.float32),
        'labels': torch.as_tensor(labels, dtype=torch.int64),
        'image_id': torch.tensor([0]),
        'area': torch.as_tensor([(b[2]-b[0])*(b[3]-b[1]) for b in boxes], dtype=torch.float32),
        'iscrowd': torch.zeros((len(boxes),), dtype=torch.int64),
    }


def convert_one_txt(txt_path):
    img_path = find_image(os.path.splitext(os.path.basename(txt_path))[0])
    if img_path is None:
        return None

    img = cv2.imread(img_path)
    if img is None:
        return None

    h, w = img.shape[:2]
    boxes = []
    labels = []

    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls_id = int(parts[0])
            if cls_id == 0 or cls_id >= len(CLASS_NAMES):
                continue
            cx, cy, bw, bh = map(float, parts[1:])
            x1 = (cx - bw / 2) * w
            y1 = (cy - bh / 2) * h
            x2 = (cx + bw / 2) * w
            y2 = (cy + bh / 2) * h
            x1, x2 = max(0, min(w, x1)), max(0, min(w, x2))
            y1, y2 = max(0, min(h, y1)), max(0, min(h, y2))
            if x2 <= x1 or y2 <= y1:
                continue
            boxes.append([x1, y1, x2, y2])
            labels.append(cls_id)

    if not boxes:
        return None

    return {
        'boxes': torch.as_tensor(boxes, dtype=torch.float32),
        'labels': torch.as_tensor(labels, dtype=torch.int64),
        'image_id': torch.tensor([0]),
        'area': torch.as_tensor([(b[2]-b[0])*(b[3]-b[1]) for b in boxes], dtype=torch.float32),
        'iscrowd': torch.zeros((len(boxes),), dtype=torch.int64),
    }


def main():
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else 'json'

    if source == 'json':
        label_files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
        fmt = 'json'
    elif source == 'txt':
        label_files = sorted(glob.glob(os.path.join(TXT_DIR, "*.txt")))
        fmt = 'txt'
    else:
        print(f"用法: python convert_to_fasterrcnn.py [json|txt]")
        print(f"  json - 使用 {JSON_DIR} 下的 labelme JSON 标注（默认）")
        print(f"  txt  - 使用 {TXT_DIR} 下的 YOLO TXT 标注")
        return

    print(f"标注源: {fmt.upper()} 共 {len(label_files)} 个文件")

    img_train_dir = os.path.join(OUT_DIR, "images", "train")
    img_val_dir = os.path.join(OUT_DIR, "images", "val")
    ann_train_dir = os.path.join(OUT_DIR, "annotations", "train")
    ann_val_dir = os.path.join(OUT_DIR, "annotations", "val")

    for d in [img_train_dir, img_val_dir, ann_train_dir, ann_val_dir]:
        os.makedirs(d, exist_ok=True)

    random.seed(42)
    random.shuffle(label_files)

    split_idx = max(1, int(len(label_files) * 0.8))
    train_files = label_files[:split_idx]
    val_files = label_files[split_idx:]

    print(f"训练集: {len(train_files)} 张, 验证集: {len(val_files)} 张")

    def process(file_list, img_dir, ann_dir):
        total_boxes = 0
        class_count = {}
        for fpath in file_list:
            if fmt == 'json':
                target = convert_one(fpath)
            else:
                target = convert_one_txt(fpath)

            if target is None:
                continue

            base = os.path.splitext(os.path.basename(fpath))[0]

            ann_path = os.path.join(ann_dir, f"{base}.pt")
            torch.save(target, ann_path)

            img_src = find_image(base)
            if img_src:
                ext = os.path.splitext(img_src)[1]
                shutil.copy(img_src, os.path.join(img_dir, f"{base}{ext}"))
            else:
                print(f"  [警告] {base}: 找不到对应图片")

            for lbl in target['labels'].tolist():
                name = CLASS_NAMES[lbl] if lbl < len(CLASS_NAMES) else f"unknown_{lbl}"
                class_count[name] = class_count.get(name, 0) + 1

            total_boxes += len(target['boxes'])
            print(f"  {base}: {len(target['boxes'])} 个标注框")

        print(f"  类别统计: {class_count}")
        return total_boxes

    train_boxes = process(train_files, img_train_dir, ann_train_dir)
    val_boxes = process(val_files, img_val_dir, ann_val_dir)

    print(f"\n转换完成！")
    print(f"  训练集: {len(train_files)} 张, {train_boxes} 个框")
    print(f"  验证集: {len(val_files)} 张, {val_boxes} 个框")


if __name__ == '__main__':
    main()
