import os
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['PADDLE_DISABLE_PIR'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['KMP_BLOCKTIME'] = '0'

from flask import Flask
from config import MAX_CONTENT_LENGTH
from routes.invoice_routes import invoice_bp


def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    app.register_blueprint(invoice_bp)

    @app.route('/')
    def index():
        return app.send_static_file('index.html')

    return app


if __name__ == '__main__':
    print('正在检查 EasyOCR 模型...')
    import services.easyocr_service
    
    from services.ocr_manager import switch_engine
    from config import DEFAULT_OCR_ENGINE
    print(f'正在预加载 OCR 引擎 ({DEFAULT_OCR_ENGINE})...')
    switch_engine(DEFAULT_OCR_ENGINE)
    print('OCR 引擎加载完成，启动服务...')

    app = create_app()
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
