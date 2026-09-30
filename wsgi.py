"""
WSGI / ASGI Canonical Entrypoint for Gunicorn and Uvicorn.
Supports:
1. Gunicorn standard WSGI: gunicorn -b 0.0.0.0:$PORT wsgi:app
2. Gunicorn + Uvicorn worker (ASGI): gunicorn -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT wsgi:app
3. Standalone Uvicorn: uvicorn wsgi:app --host 0.0.0.0 --port $PORT
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from application import app as flask_app, asgi_app

class UniversalApp:
    """Dispatches calls as ASGI (3 args: scope, receive, send) or WSGI (2 args: environ, start_response)."""
    def __init__(self, wsgi_instance, asgi_instance):
        self.wsgi_app = wsgi_instance
        self.asgi_app = asgi_instance

    def __call__(self, *args, **kwargs):
        if len(args) == 3:
            return self.asgi_app(*args, **kwargs)
        return self.wsgi_app(*args, **kwargs)

# Canonical export for Gunicorn (both standard WSGI and UvicornWorker) and Uvicorn
app = UniversalApp(flask_app, asgi_app)
application = flask_app  # Fallback for standard WSGI servers
