# 测试脚本 test_ocr.py
import cv2
from services.easyocr_service import recognize, get_full_text

# 读取一张发票图片
image = cv2.imread('data/001.png')
# 测试识别
items = recognize(image)
print(f"识别到 {len(items)} 个文本区域")
for item in items[:5]:  # 只打印前5个
    print(f"  文字: {item['text']}, 置信度: {item['confidence']:.2f}")
# 获取完整文本
full_text = get_full_text(items)
print(f"\n完整文本:\n{full_text}")