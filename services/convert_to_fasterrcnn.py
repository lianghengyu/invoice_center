import os
import json
import glob
import random
import shutil
import torch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLASS_NAMES = [
    '__background__',
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
]

LABEL_MAP = {
    '发票代码': 1,
    '发票号码': 2,
    '发票日期': 3,
    '购买方名称': 4,
    '购买方纳税人识别号': 5,
    '购买方纳税人税别号': 5,
    '价税合计': 6,
    '增值税电子普通发票': 7,
    '电子普通发票': 7,
}

JSON_DIR = os.path.join(BASE_DIR, "data")
IMG_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "data/fasterrcnn")


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

    return {
        'boxes': torch.as_tensor(boxes, dtype=torch.float32),
        'labels': torch.as_tensor(labels, dtype=torch.int64),
        'image_id': torch.tensor([0]),
        'area': torch.as_tensor([(b[2]-b[0])*(b[3]-b[1]) for b in boxes], dtype=torch.float32),
        'iscrowd': torch.zeros((len(boxes),), dtype=torch.int64),
    }


def main():
    json_files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    print(f"找到 {len(json_files)} 个标注文件")

    img_train_dir = os.path.join(OUT_DIR, "images", "train")
    img_val_dir = os.path.join(OUT_DIR, "images", "val")
    ann_train_dir = os.path.join(OUT_DIR, "annotations", "train")
    ann_val_dir = os.path.join(OUT_DIR, "annotations", "val")

    for d in [img_train_dir, img_val_dir, ann_train_dir, ann_val_dir]:
        os.makedirs(d, exist_ok=True)

    random.seed(42)
    random.shuffle(json_files)

    split_idx = max(1, int(len(json_files) * 0.8))
    train_files = json_files[:split_idx]
    val_files = json_files[split_idx:]

    print(f"训练集: {len(train_files)} 张, 验证集: {len(val_files)} 张")

    def process(file_list, img_dir, ann_dir):
        total_boxes = 0
        for jf in file_list:
            target = convert_one(jf)
            if len(target['boxes']) == 0:
                continue

            base = os.path.splitext(os.path.basename(jf))[0]

            ann_path = os.path.join(ann_dir, f"{base}.pt")
            torch.save(target, ann_path)

            for ext in ['png', 'jpg', 'jpeg']:
                img_src = os.path.join(IMG_DIR, f"{base}.{ext}")
                if os.path.exists(img_src):
                    shutil.copy(img_src, os.path.join(img_dir, f"{base}.{ext}"))
                    break

            total_boxes += len(target['boxes'])
            print(f"  {base}: {len(target['boxes'])} 个标注框")

        return total_boxes

    train_boxes = process(train_files, img_train_dir, ann_train_dir)
    val_boxes = process(val_files, img_val_dir, ann_val_dir)

    print(f"\n转换完成！")
    print(f"  训练集: {len(train_files)} 张, {train_boxes} 个框")
    print(f"  验证集: {len(val_files)} 张, {val_boxes} 个框")


if __name__ == '__main__':
    main()
