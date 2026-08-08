import os
import json
import subprocess
import base64
import cv2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_current_detector_name = 'none'

VALID_DETECTORS = ['yolov8', 'yolov10', 'fasterrcnn', 'none']

SUBPROCESS_SCRIPT = os.path.join(BASE_DIR, "services", "detector_subprocess.py")

def get_current_detector():
    return _current_detector_name


def get_current_detector_name():
    return _current_detector_name


def get_available_detectors():
    return VALID_DETECTORS


def switch_detector(detector_name):
    global _current_detector_name
    if detector_name not in VALID_DETECTORS:
        raise ValueError(f"不支持的检测模型: {detector_name}，可选: {VALID_DETECTORS}")
    _current_detector_name = detector_name
    print(f"检测模型已切换: {detector_name}")


def detect_fields(image):
    if _current_detector_name == 'none':
        return []

    _, buf = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    image_b64 = base64.b64encode(buf).decode('utf-8')

    try:
        result = subprocess.run(
            ['python', SUBPROCESS_SCRIPT, _current_detector_name, image_b64],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, 'KMP_DUPLICATE_LIB_OK': 'TRUE'}
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"[子进程检测错误] stderr: {result.stderr[:200]}")
            return []
    except subprocess.TimeoutExpired:
        print("[子进程检测] 超时")
        return []
    except Exception as e:
        print(f"[子进程检测] 异常: {e}")
        return []
