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


def get_full_text(items):
    from services.ocr_service import get_full_text as _get_full_text
    return _get_full_text(items)