from easyocr import easyocr

_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = easyocr.Reader(['ch_sim', 'en'], gpu=True)
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
