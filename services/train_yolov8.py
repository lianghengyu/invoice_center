import os
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOLO_DIR = os.path.join(BASE_DIR, "data/yolov8")
YAML_PATH = os.path.join(YOLO_DIR, "invoice.yaml")
MODEL_SAVE = os.path.join(BASE_DIR, "model/yolov8")


def main():
    os.makedirs(MODEL_SAVE, exist_ok=True)

    model = YOLO("yolov8n.pt")

    results = model.train(
        data=YAML_PATH,
        epochs=200,
        imgsz=800,
        batch=8,
        name="invoice_detect",
        project=MODEL_SAVE,
        patience=30,
        device="cpu",
        exist_ok=True,
    )

    print(f"\n训练完成！模型保存在: {MODEL_SAVE}/invoice_detect/weights/best.pt")


if __name__ == '__main__':
    main()
