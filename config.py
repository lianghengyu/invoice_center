import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')
SAVED_FOLDER = os.path.join(BASE_DIR, 'saved_results')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'tiff', 'tif', 'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
DEFAULT_OCR_ENGINE = 'paddle'
AUTO_ROTATE_OCR = True  # 自动尝试0/90/180/270四个方向选识别效果最好的（关闭可提速但无法纠正整图旋转）

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXPORT_FOLDER, exist_ok=True)
os.makedirs(SAVED_FOLDER, exist_ok=True)
