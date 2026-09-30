import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR in sys.path:
    sys.path.remove(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from flask import Flask, request, jsonify
from config import DOWNLOADS_DIR
from routes.main_routes import main_bp
from routes.api_routes import api_bp
from routes.download_routes import download_bp

def create_app():
    app = Flask(__name__)

    # Universal CORS Middleware for Headless API Access
    @app.after_request
    def apply_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Range, X-Requested-With, Accept'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Length, Content-Range, Content-Disposition'
        return response

    # Handle OPTIONS Preflight Requests Globally
    @app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
    @app.route('/<path:path>', methods=['OPTIONS'])
    def handle_options_preflight(path):
        return ('', 204)

    # Register Blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(download_bp)

    # Ensure runtime directories exist
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'tmp'), exist_ok=True)

    return app

app = create_app()

# ASGI Compatibility Layer for Uvicorn / Hypercorn (Render, Railway, Fly.io)
try:
    from asgiref.wsgi import WsgiToAsgi
    asgi_app = WsgiToAsgi(app)
except ImportError:
    try:
        from a2wsgi import WSGIMiddleware
        asgi_app = WSGIMiddleware(app)
    except ImportError:
        asgi_app = app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() in ('true', '1')
    app.run(host=host, port=port, debug=debug)
