import os
import glob
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


model = YOLO(os.path.join(BASE_DIR, "model/yolov8/invoice_detect/weights/best.pt"))
CLASS_NAMES = list(model.names.values())

IMG_DIRS = [
    os.path.join(BASE_DIR, "data/normal"),
    os.path.join(BASE_DIR, "data/special"),
    os.path.join(BASE_DIR, "data/synthetic"),
    os.path.join(BASE_DIR, "data/synthetic_v2"),
]

img_files = []
for d in IMG_DIRS:
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        img_files.extend(glob.glob(os.path.join(d, ext)))
img_files = sorted(set(img_files))

print(f"共找到 {len(img_files)} 张图片")
print(f"模型类别: {CLASS_NAMES}\n")

total_detections = 0
field_stats = {name: 0 for name in CLASS_NAMES}

for img_path in img_files:
    results = model.predict(img_path, save=True, project='saved_results/yolov8_test', verbose=False)

    detected_names = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            name = r.names[cls_id]
            detected_names.append(f"{name}({conf:.2f})")
            if name in field_stats:
                field_stats[name] += 1
            total_detections += 1

    print(f"{os.path.basename(img_path)}: {len(detected_names)} 个字段 -> {detected_names}")

print(f"\n{'='*50}")
print(f"汇总：共 {len(img_files)} 张图，{total_detections} 个检测框")
print(f"{'='*50}")
for name, count in field_stats.items():
    print(f"  {name}: {count}/{len(img_files)} 张图中被检出")
