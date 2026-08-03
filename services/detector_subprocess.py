import sys
import os
import json
import base64
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOLOV8_MODEL = os.path.join(BASE_DIR, "model/yolov8/invoice_detect/weights/best.pt")
FASTERRCNN_MODEL = os.path.join(BASE_DIR, "model/fasterrcnn/best.pth")


def run_yolov8(image_b64):
    import cv2
    from ultralytics import YOLO
    img_bytes = base64.b64decode(image_b64)
    img = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_COLOR)

    model = YOLO(YOLOV8_MODEL)
    model_names = model.names
    results = model.predict(img, verbose=False, conf=0.3)

    detections = []
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            if cls_id >= len(model_names):
                continue
            detections.append({
                'class_name': model_names[cls_id],
                'confidence': float(box.conf[0]),
                'bbox': [float(v) for v in box.xyxy[0].tolist()],
            })
    return detections


def run_fasterrcnn(image_b64):
    import cv2
    import torch
    from torchvision.models.detection import fasterrcnn_resnet50_fpn
    from torchvision.transforms import functional as F
    from PIL import Image

    img_bytes = base64.b64decode(image_b64)
    img = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(img, cv2.IMREAD_COLOR)
    img_rgb = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    model = fasterrcnn_resnet50_fpn(weights=None, num_classes=9)
    if os.path.exists(FASTERRCNN_MODEL):
        model.load_state_dict(torch.load(FASTERRCNN_MODEL, map_location='cpu', weights_only=True))
    model.eval()

    tensor = F.to_tensor(img_rgb).unsqueeze(0)
    with torch.no_grad():
        predictions = model(tensor)[0]

    model_names = ['发票代码', '发票号码', '发票日期', '购买方名称',
                   '购买方纳税人识别号', '价税合计', '增值税电子普通发票', '发票']

    detections = []
    for i, score in enumerate(predictions['scores']):
        if score < 0.3:
            continue
        cls_id = int(predictions['labels'][i])
        if cls_id == 0:
            continue
        box = predictions['boxes'][i].tolist()
        name = model_names[cls_id - 1] if 0 < cls_id <= len(model_names) else 'unknown'
        detections.append({
            'class_id': cls_id - 1,
            'class_name': name,
            'confidence': float(score),
            'bbox': [float(v) for v in box],
        })
    return detections


if __name__ == '__main__':
    import cv2
    mode = sys.argv[1]
    image_b64 = sys.argv[2]

    if mode == 'yolov8':
        result = run_yolov8(image_b64)
    elif mode == 'fasterrcnn':
        result = run_fasterrcnn(image_b64)
    else:
        result = []

    print(json.dumps(result))
