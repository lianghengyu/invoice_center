import os
import json
import glob
import random
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLASS_NAMES = [
    '发票代码',
    '发票号码',
    '发票日期',
    '购买方名称',
    '购买方纳税人识别号',
    '价税合计',
    '增值税电子普通发票',
]

LABEL_MAP = {
    '发票代码': 0,
    '发票号码': 1,
    '发票日期': 2,
    '购买方名称': 3,
    '购买方纳税人识别号': 4,
    '购买方纳税人税别号': 4,
    '价税合计': 5,
    '增值税电子普通发票': 6,
    '电子普通发票': 6,
}

JSON_DIR = os.path.join(BASE_DIR, "data")
IMG_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "data/yolov8")

def convert_one(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    img_w = data.get('imageWidth', 0)
    img_h = data.get('imageHeight', 0)
    if img_w == 0 or img_h == 0:
        return None

    lines = []
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

        cx = (x1 + x2) / 2 / img_w
        cy = (y1 + y2) / 2 / img_h
        bw = (x2 - x1) / img_w
        bh = (y2 - y1) / img_h

        cx = max(0, min(1, cx))
        cy = max(0, min(1, cy))
        bw = max(0.001, min(1, bw))
        bh = max(0.001, min(1, bh))

        class_id = LABEL_MAP[label]
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    return lines


def main():
    json_files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    print(f"找到 {len(json_files)} 个标注文件")

    img_train_dir = os.path.join(OUT_DIR, "images", "train")
    img_val_dir = os.path.join(OUT_DIR, "images", "val")
    lbl_train_dir = os.path.join(OUT_DIR, "labels", "train")
    lbl_val_dir = os.path.join(OUT_DIR, "labels", "val")

    for d in [img_train_dir, img_val_dir, lbl_train_dir, lbl_val_dir]:
        os.makedirs(d, exist_ok=True)

    random.seed(42)
    random.shuffle(json_files)

    split_idx = max(1, int(len(json_files) * 0.8))
    train_files = json_files[:split_idx]
    val_files = json_files[split_idx:]

    print(f"训练集: {len(train_files)} 张, 验证集: {len(val_files)} 张")

    def process(file_list, img_dir, lbl_dir):
        total_boxes = 0
        for jf in file_list:
            lines = convert_one(jf)
            if lines is None:
                continue

            base = os.path.splitext(os.path.basename(jf))[0]
            lbl_path = os.path.join(lbl_dir, f"{base}.txt")
            with open(lbl_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')

            for ext in ['png', 'jpg', 'jpeg']:
                img_src = os.path.join(IMG_DIR, f"{base}.{ext}")
                if os.path.exists(img_src):
                    shutil.copy(img_src, os.path.join(img_dir, f"{base}.{ext}"))
                    break

            total_boxes += len(lines)
            print(f"  {base}: {len(lines)} 个标注框")

        return total_boxes

    train_boxes = process(train_files, img_train_dir, lbl_train_dir)
    val_boxes = process(val_files, img_val_dir, lbl_val_dir)

    yaml_path = os.path.join(OUT_DIR, "invoice.yaml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(f"path: {OUT_DIR}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"nc: {len(CLASS_NAMES)}\n")
        f.write("names: [")
        f.write(", ".join(f"'{n}'" for n in CLASS_NAMES))
        f.write("]\n")

    print(f"\n转换完成！")
    print(f"  训练集: {len(train_files)} 张, {train_boxes} 个框")
    print(f"  验证集: {len(val_files)} 张, {val_boxes} 个框")
    print(f"  YOLOV8配置: {yaml_path}")


if __name__ == '__main__':
    main()
