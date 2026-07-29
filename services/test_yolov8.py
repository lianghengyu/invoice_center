import os
import glob
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLASS_NAMES = [
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
]

model = YOLO('saved_results/yolov8_model/invoice_detect-3/weights/best.pt')

img_dir = os.path.join(BASE_DIR, "data")
img_files = sorted(
    glob.glob(os.path.join(img_dir, "0*.png"))
    + glob.glob(os.path.join(img_dir, "0*.jpg"))
    + glob.glob(os.path.join(img_dir, "b*.jpg"))
    + glob.glob(os.path.join(img_dir, "b*.png"))
)

print(f"共找到 {len(img_files)} 张图片\n")

total_detections = 0
field_stats = {name: 0 for name in CLASS_NAMES}

for img_path in img_files:
    results = model.predict(img_path, save=True, project='saved_results/yolov8_test', verbose=False)

    detected_names = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            if cls_id < len(CLASS_NAMES):
                name = CLASS_NAMES[cls_id]
                detected_names.append(f"{name}({conf:.2f})")
                field_stats[name] += 1
                total_detections += 1

    print(f"{os.path.basename(img_path)}: {len(detected_names)} 个字段 -> {detected_names}")

print(f"\n{'='*50}")
print(f"汇总：共 {len(img_files)} 张图，{total_detections} 个检测框")
print(f"{'='*50}")
for name, count in field_stats.items():
    print(f"  {name}: {count}/{len(img_files)} 张图中被检出")
