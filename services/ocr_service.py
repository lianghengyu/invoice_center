import os
# macOS 上 paddle 与 torch 各自携带 libomp，重复加载会导致段错误，必须在导入前放行
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
from paddleocr import PaddleOCR
import paddle
import urllib.request
import tarfile

# ===== 路径配置 =====
_ocr_instance = None
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "..", "model", "paddleocr")
os.makedirs(MODEL_PATH, exist_ok=True)
print(MODEL_PATH)
# ===== 模型配置 =====
MODEL_URL_BASE = "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0"
# 3 个模型配置：key → (文件名, 解压后目录名)
MODEL_CONFIGS = {
    "det": ("PP-OCRv6_medium_det_infer.tar", "PP-OCRv6_medium_det_infer"),
    "rec": ("PP-OCRv6_medium_rec_infer.tar", "PP-OCRv6_medium_rec_infer"),
    "cls": ("PP-LCNet_x1_0_textline_ori_infer.tar", "PP-LCNet_x1_0_textline_ori_infer"),
}
# ===== 模型下载函数 =====
def _ensure_models():
    """检查模型是否存在，不存在则下载并解压"""
    for key, (filename, dirname) in MODEL_CONFIGS.items():
        target_dir = os.path.join(MODEL_PATH, dirname)   
        # 检查模型是否已存在
        if os.path.exists(target_dir) and os.listdir(target_dir):
            print(f"[OK] {key} 模型已存在")
            continue
        # 下载
        os.makedirs(target_dir, exist_ok=True)
        tar_path = os.path.join(MODEL_PATH, filename)
        if not os.path.exists(tar_path):
            url = f"{MODEL_URL_BASE}/{filename}"
            print(f"下载 {filename} ...")
            urllib.request.urlretrieve(url, tar_path)
        # 解压
        print(f"解压 {filename} ...")
        with tarfile.open(tar_path, 'r') as tar:
            tar.extractall(path=MODEL_PATH)
        os.remove(tar_path)
        print(f"[完成] {key} 模型已准备")
# ===== 设备检测函数 =====
def get_best_device():
    """
    检测并返回最佳的可用设备。
    如果CUDA可用，返回 'gpu:0'，否则返回 'cpu'。
    """
    # 检查PaddlePaddle是否编译了CUDA支持，并且CUDA环境可用
    if paddle.is_compiled_with_cuda():
        try:
            # 尝试创建一个在GPU上的张量来测试CUDA是否真的可用
            test_tensor = paddle.to_tensor([1.0], place=paddle.CUDAPlace(0))
            # 如果成功，说明CUDA可用
            print("✅ CUDA is available. Using GPU: 0")
            return 'gpu:0'
        except Exception as e:
            # 如果创建失败，说明CUDA不可用（例如驱动问题、显卡被占用等）
            print(f"⚠️ CUDA is not available ({e}). Falling back to CPU.")
            return 'cpu'
    else:
        print("ℹ️ PaddlePaddle not compiled with CUDA. Using CPU.")
        return 'cpu'

# 在程序开始时设置设备
best_device = get_best_device()

def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ensure_models()  # 确保模型存在
        _ocr_instance = PaddleOCR(
            #lang='ch',
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            text_detection_model_dir=os.path.join(MODEL_PATH, 'PP-OCRv6_medium_det_infer'),
            text_recognition_model_dir=os.path.join(MODEL_PATH, 'PP-OCRv6_medium_rec_infer'),
            textline_orientation_model_dir=os.path.join(MODEL_PATH, 'PP-LCNet_x1_0_textline_ori_infer'),
            device=best_device,
        )
    return _ocr_instance


def init_ocr():
    _get_ocr()


def recognize(image):
    ocr = _get_ocr()
    results = ocr.predict(image)
    if not results:
        return []

    items = []
    for res in results:
        texts = res.get('rec_texts', [])
        scores = res.get('rec_scores', [])
        polys = res.get('dt_polys', [])

        for i, text in enumerate(texts):
            confidence = scores[i] if i < len(scores) else 0.0
            box = polys[i].tolist() if i < len(polys) else [[0, 0], [0, 0], [0, 0], [0, 0]]
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
            import paddle
            if paddle.is_compiled_with_cuda():
                paddle.device.cuda.empty_cache()
        except Exception:
            _ocr_instance = None
    else:
        _ocr_instance = None