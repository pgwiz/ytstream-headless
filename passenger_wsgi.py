import os
import sys
import glob

# Project directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR in sys.path:
    sys.path.remove(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# Virtualenv detection: check sys.prefix first, then local ./venv, then CloudLinux paths
venv_candidates = [
    sys.prefix,
    os.path.join(BASE_DIR, 'venv'),
    '/home1/seepocok/virtualenv/public_html/ytapi.pgwiz.qzz.io/3.13',
    '/home1/seepocok/virtualenv/public_html/ytapi.pgwiz.qzz.io/3.11',
]

for venv in venv_candidates:
    if os.path.exists(venv):
        for sp in glob.glob(os.path.join(venv, 'lib', 'python*', 'site-packages')):
            if sp not in sys.path:
                sys.path.insert(1, sp)

from application import app as application
