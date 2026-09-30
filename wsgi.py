"""
WSGI / ASGI Canonical Entrypoint for Gunicorn and Uvicorn.
Supports:
1. Gunicorn + Uvicorn worker (ASGI):
   gunicorn -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT wsgi:app
2. Standalone Uvicorn:
   uvicorn wsgi:app --host 0.0.0.0 --port $PORT
3. Standard Gunicorn (WSGI):
   gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:application
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from application import app as flask_app, asgi_app

# Primary export for ASGI runners (UvicornWorker, Uvicorn, Hypercorn):
app = asgi_app

# Secondary export for WSGI runners (Gunicorn sync worker, Phusion Passenger, uWSGI):
application = flask_app
