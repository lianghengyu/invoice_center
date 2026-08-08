import os
# macOS 上 torch 与 paddle 各自携带 libomp，重复加载会导致段错误，必须在导入前放行
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import easyocr
import urllib.request

_ocr_instance = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR,"..", "model", "easyocr")
if not os.path.exists(MODEL_PATH):
    os.makedirs(MODEL_PATH)

MODEL_URL = "https://www.modelscope.cn/models/Ceceliachenen/easyocr/resolve/master"

craft_path = os.path.join(MODEL_PATH, "craft_mlt_25k.pth")
if not os.path.exists(craft_path):
    print("下载 craft_mlt_25k.pth ...")
    urllib.request.urlretrieve(f"{MODEL_URL}/craft_mlt_25k.pth", craft_path)

english_path = os.path.join(MODEL_PATH, "english_g2.pth")
if not os.path.exists(english_path):
    print("下载 english_g2.pth ...")
    urllib.request.urlretrieve(f"{MODEL_URL}/english_g2.pth", english_path)

zh_path = os.path.join(MODEL_PATH, "zh_sim_g2.pth")
if not os.path.exists(zh_path):
    print("下载 zh_sim_g2.pth ...")
    urllib.request.urlretrieve(f"{MODEL_URL}/zh_sim_g2.pth", zh_path)

def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = easyocr.Reader(['ch_sim', 'en'], 
                                       gpu=True,
                                       model_storage_directory=MODEL_PATH,
                                       download_enabled=False,  
                                    )
    return _ocr_instance


def init_ocr():
    _get_ocr()


def recognize(image):
    ocr = _get_ocr()
    results = ocr.readtext(image)
    if not results:
        return []

    items = []
    for bbox, text, confidence in results:
        box = [[int(p[0]), int(p[1])] for p in bbox]
        y_center = (box[0][1] + box[2][1]) / 2
        x_center = (box[0][0] + box[2][0]) / 2
        items.append({
                'text': text,
                'confidence': confidence,
                'box': box,
                'y': y_center,
                'x': x_center,
        })

    items.sort(key=lambda it: (round(it['y'] / 15), it['x']))
    return items


def get_full_text(items):
    if not items:
        return ''
    lines = []
    current_line = [items[0]['text']]
    current_y = items[0]['y']

    for item in items[1:]:
        if abs(item['y'] - current_y) < 15:
            current_line.append(item['text'])
        else:
            lines.append(' '.join(current_line))
            current_line = [item['text']]
            current_y = item['y']
    lines.append(' '.join(current_line))
    return '\n'.join(lines)

def reset_ocr():
    global _ocr_instance
    if _ocr_instance is not None:
        try:
            import gc
            _ocr_instance = None
            gc.collect()
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            _ocr_instance = None
    else:
        _ocr_instance = None