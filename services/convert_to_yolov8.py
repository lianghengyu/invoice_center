import os
import json
import glob
import random
import shutil
import cv2
import numpy as np

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
    '价税合计': 5,
    '增值税电子普通发票': 6,
    '电子普通发票': 6,
}

JSON_DIR = os.path.join(BASE_DIR, "data/labelsJson")
TXT_DIR = os.path.join(BASE_DIR, "data/labelsTxt")
IMG_DIRS = [
    os.path.join(BASE_DIR, "data/normal"),
    os.path.join(BASE_DIR, "data/special"),
    os.path.join(BASE_DIR, "data/synthetic"),
    os.path.join(BASE_DIR, "data/synthetic_v2"),
]
OUT_DIR = os.path.join(BASE_DIR, "data/yolov8")


def rotate_landscape_and_adjust_labels(img_path, lines, out_img_path):
    """
    如果图片是横向的（与 preprocess 逻辑一致），旋转90°顺时针并调整YOLO标注坐标。
    返回调整后的标注行列表。
    """
    img = cv2.imread(img_path)
    if img is None:
        return lines

    h, w = img.shape[:2]
    if w <= h * 1.3:
        shutil.copy(img_path, out_img_path)
        return lines

    img_rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    cv2.imwrite(out_img_path, img_rotated)

    new_h, new_w = img_rotated.shape[:2]
    adjusted = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        cls = parts[0]
        cx, cy, bw, bh = map(float, parts[1:])

        x1 = (cx - bw / 2) * w
        y1 = (cy - bh / 2) * h
        x2 = (cx + bw / 2) * w
        y2 = (cy + bh / 2) * h

        new_x1 = h - y2
        new_y1 = x1
        new_x2 = h - y1
        new_y2 = x2

        new_x1, new_x2 = min(new_x1, new_x2), max(new_x1, new_x2)
        new_y1, new_y2 = min(new_y1, new_y2), max(new_y1, new_y2)

        new_cx = (new_x1 + new_x2) / 2 / new_w
        new_cy = (new_y1 + new_y2) / 2 / new_h
        new_bw = (new_x2 - new_x1) / new_w
        new_bh = (new_y2 - new_y1) / new_h

        new_cx = max(0, min(1, new_cx))
        new_cy = max(0, min(1, new_cy))
        new_bw = max(0.001, min(1, new_bw))
        new_bh = max(0.001, min(1, new_bh))

        adjusted.append(f"{cls} {new_cx:.6f} {new_cy:.6f} {new_bw:.6f} {new_bh:.6f}")

    return adjusted


def convert_one_txt(txt_path):
    """读取已是 YOLO 格式的 txt 标注文件，过滤掉超出类别范围的行。"""
    lines = []
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls_id = int(parts[0])
            if cls_id >= len(CLASS_NAMES):
                continue
            lines.append(line)
    return lines if lines else None


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
    import sys
    source = sys.argv[1] if len(sys.argv) > 1 else 'txt'

    if source == 'json':
        label_files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
        fmt = 'json'
    elif source == 'txt':
        label_files = sorted(glob.glob(os.path.join(TXT_DIR, "*.txt")))
        fmt = 'txt'
    else:
        print(f"用法: python convert_to_yolov8.py [json|txt]")
        print(f"  json - 使用 {JSON_DIR} 下的 labelme JSON 标注")
        print(f"  txt  - 使用 {TXT_DIR} 下的 YOLO TXT 标注（默认）")
        return

    print(f"标注源: {fmt.upper()} 共 {len(label_files)} 个文件")

    img_train_dir = os.path.join(OUT_DIR, "images", "train")
    img_val_dir = os.path.join(OUT_DIR, "images", "val")
    lbl_train_dir = os.path.join(OUT_DIR, "labels", "train")
    lbl_val_dir = os.path.join(OUT_DIR, "labels", "val")

    for d in [img_train_dir, img_val_dir, lbl_train_dir, lbl_val_dir]:
        os.makedirs(d, exist_ok=True)

    random.seed(42)
    random.shuffle(label_files)

    split_idx = max(1, int(len(label_files) * 0.8))
    train_files = label_files[:split_idx]
    val_files = label_files[split_idx:]

    print(f"训练集: {len(train_files)} 张, 验证集: {len(val_files)} 张")

    def process(file_list, img_dir, lbl_dir):
        total_boxes = 0
        for fpath in file_list:
            if fmt == 'json':
                lines = convert_one(fpath)
            else:
                lines = convert_one_txt(fpath)

            if lines is None:
                continue

            base = os.path.splitext(os.path.basename(fpath))[0]
            lbl_path = os.path.join(lbl_dir, f"{base}.txt")

            out_img_path = None
            img_src = None
            for d in IMG_DIRS:
                for ext in ['png', 'jpg', 'jpeg']:
                    candidate = os.path.join(d, f"{base}.{ext}")
                    if os.path.exists(candidate):
                        img_src = candidate
                        out_img_path = os.path.join(img_dir, f"{base}.{ext}")
                        break
                if img_src:
                    break

            if out_img_path:
                lines = rotate_landscape_and_adjust_labels(
                    img_src, lines, out_img_path
                )

            with open(lbl_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')

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
