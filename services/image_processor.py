import cv2
import numpy as np
import pypdfium2 as pdfium


def preprocess(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"无法读取图片: {image_path}")

    img = _resize_if_needed(img, max_side=2000)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    angle = _detect_skew_angle(gray)
    if abs(angle) > 0.5:
        img = _rotate_image(img, angle)
    return img


def pdf_to_images(pdf_path, dpi=200):
    pdf = pdfium.PdfDocument(pdf_path)
    images = []
    for i in range(len(pdf)):
        page = pdf[i]
        bitmap = page.render(scale=dpi / 72)
        pil_image = bitmap.to_pil()
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        images.append((i + 1, img))
    pdf.close()
    return images


def _resize_if_needed(img, max_side=2000):
    h, w = img.shape[:2]
    if max(h, w) <= max_side:
        return img
    scale = max_side / max(h, w)
    return cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def _detect_skew_angle(gray_img):
    edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                            minLineLength=100, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line.reshape(-1)[:4]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) < 45:
            angles.append(angle)
    if not angles:
        return 0.0
    return np.median(angles)


def _rotate_image(img, angle):
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)
