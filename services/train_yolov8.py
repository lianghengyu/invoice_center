import os
from ultralytics import YOLO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOLO_DIR = os.path.join(BASE_DIR, "data/yolov8")
YAML_PATH = os.path.join(YOLO_DIR, "invoice.yaml")
MODEL_SAVE = os.path.join(BASE_DIR, "model/yolov8")


def main():
    os.makedirs(MODEL_SAVE, exist_ok=True)

    model = YOLO("yolov8s.pt")

    results = model.train(
        data=YAML_PATH,
        epochs=300,
        imgsz=1024,
        batch=16,
        name="invoice_detect",
        project=MODEL_SAVE,
        patience=50,
        device="mps",
        exist_ok=True,
        workers=4,
        lr0=0.001,
        cos_lr=True,
        weight_decay=0.0005,
        mosaic=1.0,
        mixup=0.3,
        copy_paste=0.3,
        degrees=5.0,
        scale=0.3,
        flipud=0.5,
        fliplr=0.5,
        hsv_s=0.4,
        hsv_v=0.4,
        close_mosaic=30,
        amp=False,
    )

    print(f"\n训练完成！模型保存在: {MODEL_SAVE}/invoice_detect/weights/best.pt")


if __name__ == '__main__':
    main()
