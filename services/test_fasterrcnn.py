import os
import glob
import torch
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.transforms import functional as F
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CLASS_NAMES = [
    '__background__',
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
    '发票',
]

MODEL_PATH = os.path.join(BASE_DIR, "model/fasterrcnn/best.pth")

IMG_DIRS = [
    os.path.join(BASE_DIR, "data/normal"),
    os.path.join(BASE_DIR, "data/special"),
    os.path.join(BASE_DIR, "data/synthetic"),
    os.path.join(BASE_DIR, "data/synthetic_v2"),
]

CONF_THRESHOLD = 0.3


def load_model():
    model = fasterrcnn_resnet50_fpn(weights=None, num_classes=len(CLASS_NAMES))
    state_dict = torch.load(MODEL_PATH, map_location='cpu', weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    return model


def main():
    device = torch.device('cpu')
    model = load_model().to(device)
    print(f"模型加载完成: {MODEL_PATH}")

    img_files = []
    for d in IMG_DIRS:
        for ext in ['*.png', '*.jpg', '*.jpeg']:
            img_files.extend(glob.glob(os.path.join(d, ext)))
    img_files = sorted(set(img_files))

    print(f"共找到 {len(img_files)} 张图片\n")

    total_detections = 0
    field_stats = {name: 0 for name in CLASS_NAMES[1:]}

    with torch.no_grad():
        for img_path in img_files:
            img = Image.open(img_path).convert("RGB")
            img_tensor = F.to_tensor(img).to(device)

            results = model([img_tensor])

            detected_names = []
            for box, label, score in zip(
                results[0]['boxes'], results[0]['labels'], results[0]['scores']
            ):
                conf = float(score)
                if conf < CONF_THRESHOLD:
                    continue
                cls_id = int(label)
                if 0 < cls_id < len(CLASS_NAMES):
                    name = CLASS_NAMES[cls_id]
                    detected_names.append(f"{name}({conf:.2f})")
                    field_stats[name] += 1
                    total_detections += 1

            print(f"{os.path.basename(img_path)}: {len(detected_names)} 个字段 -> {detected_names}")

    print(f"\n{'='*50}")
    print(f"汇总：共 {len(img_files)} 张图，{total_detections} 个检测框（置信度≥{CONF_THRESHOLD}）")
    print(f"{'='*50}")
    for name, count in field_stats.items():
        print(f"  {name}: {count}/{len(img_files)} 张图中被检出")


if __name__ == '__main__':
    main()
