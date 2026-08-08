_current_engine = None

VALID_ENGINES = ['paddle', 'easyocr']


def get_current_engine():
    return _current_engine


def get_available_engines():
    return VALID_ENGINES


def _release_engine(engine_name):
    if engine_name == 'paddle':
        print('正在释放 PaddleOCR 显存...')
        from services.ocr_service import reset_ocr
        reset_ocr()
        print('PaddleOCR 显存已释放')
    elif engine_name == 'easyocr':
        print('正在释放 EasyOCR 显存...')
        from services.easyocr_service import reset_ocr
        reset_ocr()
        print('EasyOCR 显存已释放')


def _load_engine(engine_name):
    print(f'正在加载 {engine_name} 到显存...')
    if engine_name == 'paddle':
        from services.ocr_service import init_ocr
        init_ocr()
    elif engine_name == 'easyocr':
        from services.easyocr_service import init_ocr
        init_ocr()
    print(f'{engine_name} 加载完成')


def switch_engine(engine_name):
    global _current_engine
    if engine_name not in VALID_ENGINES:
        raise ValueError(f"不支持的引擎: {engine_name}，可选: {VALID_ENGINES}")

    if _current_engine == engine_name:
        return

    old_engine = _current_engine
    _release_engine(old_engine)

    try:
        _load_engine(engine_name)
    except Exception:
        # 加载失败时回滚到原引擎，避免状态与实际引擎不一致
        if old_engine is not None:
            try:
                _load_engine(old_engine)
            except Exception:
                _current_engine = None
                raise
        raise
    _current_engine = engine_name


def recognize(image):
    if _current_engine is None:
        raise RuntimeError("OCR 引擎未初始化，请先调用 switch_engine()")
    if _current_engine == 'paddle':
        from services.ocr_service import recognize as _recognize
        return _recognize(image)
    elif _current_engine == 'easyocr':
        from services.easyocr_service import recognize as _recognize
        return _recognize(image)


def _score(items):
    return sum(len(it['text'].strip()) * it['confidence'] for it in items)


def _recognize_best_of_four(image):
    """整图分别按0/90/180/270四个方向识别，选文字量*置信度打分最高的方向。

    仅在没有方向分类器可用的引擎（EasyOCR）上使用，代价是 4 倍 OCR 耗时。
    """
    from services.image_processor import rotate90

    best_img, best_items, best_score = image, [], -1.0
    for k in range(4):
        candidate = image if k == 0 else rotate90(image, k)
        items = recognize(candidate)
        score = _score(items)
        if score > best_score:
            best_img, best_items, best_score = candidate, items, score
    return best_img, best_items


def recognize_auto_rotate(image):
    """把整图转正后识别，返回 (转正后的图, items)。

    PaddleOCR 下先用文档方向分类器判角（约 10ms）再识别一次；
    EasyOCR 没有方向分类器，退回四方向打分。
    """
    from config import AUTO_ROTATE_OCR

    if not AUTO_ROTATE_OCR:
        return image, recognize(image)

    if _current_engine != 'paddle':
        return _recognize_best_of_four(image)

    from services.ocr_service import detect_orientation
    from services.image_processor import rotate90

    k = detect_orientation(image)
    if k:
        print(f'[方向纠正] 整图顺时针旋转 {k * 90}° 转正后识别')
        image = rotate90(image, k)
    return image, recognize(image)


def get_full_text(items):
    from services.ocr_service import get_full_text as _get_full_text
    return _get_full_text(items)
