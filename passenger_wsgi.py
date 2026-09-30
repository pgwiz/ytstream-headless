import os
import sys
import glob

# Project directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR in sys.path:
    sys.path.remove(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# Virtualenv detection: check local ./venv or CloudLinux virtualenv directory
VENV_DIR = os.path.join(BASE_DIR, 'venv')
if not os.path.exists(VENV_DIR):
    # CloudLinux selector path fallback
    VENV_DIR = '/home1/seepocok/virtualenv/public_html/ytapi.pgwiz.qzz.io/3.11'

site_packages_dirs = glob.glob(os.path.join(VENV_DIR, 'lib', 'python*', 'site-packages'))
for sp in site_packages_dirs:
    if sp not in sys.path:
        sys.path.insert(1, sp)

from application import app as application
