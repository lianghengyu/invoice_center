from paddleocr import PaddleOCR

_ocr_instance = None


def _get_ocr():
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
            lang='ch',
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