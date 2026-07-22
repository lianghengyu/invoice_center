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
    from services.ocr_service import init_ocr
    print('正在预加载 OCR 模型...')
    init_ocr()
    print('OCR 模型加载完成，启动服务...')

    app = create_app()
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
