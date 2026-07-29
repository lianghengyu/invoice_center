import os
import sys
import glob
import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from torchvision.models.detection import fasterrcnn_resnet50_fpn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLASS_NAMES = [
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
]

FR_CLASS_NAMES = [
    '__background__',
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
]

COLORS = [
    (255, 0, 0), (0, 200, 0), (0, 100, 255),
    (255, 165, 0), (128, 0, 128), (0, 200, 200), (200, 0, 200),
]

FONT_SIZE = 16


def find_font():
    candidates = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, FONT_SIZE)
    return ImageFont.load_default()


def draw_detections(img_path, detections, out_path, model_name, font):
    img = cv2.imread(img_path)
    if img is None:
        return
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)

    stats = {name: 0 for name in CLASS_NAMES}

    for det in detections:
        cls_id = det['class_id']
        conf = det['confidence']
        x1, y1, x2, y2 = [int(v) for v in det['bbox']]
        name = det['class_name']

        if cls_id >= len(CLASS_NAMES):
            continue

        color = COLORS[cls_id % len(COLORS)]
        stats[name] += 1

        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        label = f"{name} {conf:.2f}"
        text_bbox = draw.textbbox((0, 0), label, font=font)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]

        label_y = max(0, y1 - th - 6)
        draw.rectangle([x1, label_y, x1 + tw + 6, label_y + th + 3], fill=color)
        draw.text((x1 + 3, label_y + 1), label, fill=(255, 255, 255), font=font)

    title = f"[{model_name}] {os.path.basename(img_path)}"
    draw.text((10, 10), title, fill=(0, 0, 0), font=font)

    img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    cv2.imwrite(out_path, img_bgr)

    return stats


class YOLOv8Detector:
    def __init__(self, model_path):
        from ultralytics import YOLO
        self.model = YOLO(model_path)

    def detect(self, img_path):
        results = self.model.predict(img_path, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if cls_id >= len(CLASS_NAMES):
                    continue
                detections.append({
                    'class_id': cls_id,
                    'class_name': CLASS_NAMES[cls_id],
                    'confidence': float(box.conf[0]),
                    'bbox': [float(v) for v in box.xyxy[0].tolist()],
                })
        return detections


class FasterRCNNDetector:
    def __init__(self, model_path, confidence_threshold=0.1):
        self.model = fasterrcnn_resnet50_fpn(weights=None, num_classes=len(FR_CLASS_NAMES))
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))
        self.model.eval()
        self.confidence_threshold = confidence_threshold

    def detect(self, img_path):
        img = Image.open(img_path).convert("RGB")
        from torchvision.transforms import functional as F
        tensor = F.to_tensor(img).unsqueeze(0)

        with torch.no_grad():
            predictions = self.model(tensor)[0]

        detections = []
        for i, score in enumerate(predictions['scores']):
            if score < self.confidence_threshold:
                continue
            cls_id = int(predictions['labels'][i])
            if cls_id == 0:
                continue
            box = predictions['boxes'][i].tolist()
            name = FR_CLASS_NAMES[cls_id] if cls_id < len(FR_CLASS_NAMES) else 'unknown'
            detections.append({
                'class_id': cls_id - 1,
                'class_name': name,
                'confidence': float(score),
                'bbox': [float(v) for v in box],
            })
        return detections


def test_model(detector, img_dir, out_dir, model_name):
    os.makedirs(out_dir, exist_ok=True)
    font = find_font()

    img_files = sorted(
        glob.glob(os.path.join(img_dir, "0*.png"))
        + glob.glob(os.path.join(img_dir, "0*.jpg"))
        + glob.glob(os.path.join(img_dir, "b*.jpg"))
        + glob.glob(os.path.join(img_dir, "b*.png"))
    )

    all_stats = []
    for img_path in img_files:
        detections = detector.detect(img_path)
        out_name = f"{model_name}_{os.path.basename(img_path)}"
        out_path = os.path.join(out_dir, out_name)
        stats = draw_detections(img_path, detections, out_path, model_name, font)
        all_stats.append(stats)

        detected = [d['class_name'] for d in detections]
        print(f"  {os.path.basename(img_path)}: {len(detections)} 个字段 -> {detected}")

    print(f"\n[{model_name}] 测试完成！共 {len(img_files)} 张，结果保存在 {out_dir}")
    return all_stats


def compare_models(v8_model_path, fr_model_path, img_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("开始测试 YOLOv8...")
    print("=" * 60)
    v8_detector = YOLOv8Detector(v8_model_path)
    v8_stats = test_model(v8_detector, img_dir, out_dir, "v8")

    v10_stats = None
    if fr_model_path:
        print("\n" + "=" * 60)
        print("开始测试 Faster R-CNN...")
        print("=" * 60)
        fr_detector = FasterRCNNDetector(fr_model_path)
        v10_stats = test_model(fr_detector, img_dir, out_dir, "fr")

    img_files = sorted(
        glob.glob(os.path.join(img_dir, "0*.png"))
        + glob.glob(os.path.join(img_dir, "0*.jpg"))
        + glob.glob(os.path.join(img_dir, "b*.jpg"))
        + glob.glob(os.path.join(img_dir, "b*.png"))
    )

    print("\n" + "=" * 60)
    print("检测结果对比汇总")
    print("=" * 60)
    print(f"{'字段':<20} {'v8检出':>10} {'FasterRCNN':>12}")
    print("-" * 45)

    for name in CLASS_NAMES:
        v8_count = sum(1 for s in v8_stats if s.get(name, 0) > 0)
        fr_count = sum(1 for s in v10_stats if s.get(name, 0) > 0) if v10_stats else "-"
        fr_str = f"{fr_count}/{len(img_files)}" if isinstance(fr_count, int) else "-"
        print(f"{name:<18} {v8_count:>6}/{len(img_files)}  {fr_str:>10}")


def main():
    if len(sys.argv) < 2:
        print("用法: python test_yolo_compare.py <YOLOv8模型路径> [FasterRCNN模型路径]")
        print("示例1: python test_yolo_compare.py saved_results/yolov8_model/invoice_detect-3/weights/best.pt")
        print("示例2: python test_yolo_compare.py saved_results/yolov8_model/invoice_detect-3/weights/best.pt saved_results/fasterrcnn_model/best.pth")
        return

    v8_model = sys.argv[1]
    fr_model = sys.argv[2] if len(sys.argv) > 2 else None
    img_dir = os.path.join(BASE_DIR, "data")
    out_dir = os.path.join(BASE_DIR, "saved_results/yolo_test")

    compare_models(v8_model, fr_model, img_dir, out_dir)


if __name__ == '__main__':
    main()
