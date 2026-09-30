import os
import tempfile
import threading
import hashlib
import time

# --- Base Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_BASE_URL = 'https://spotipiapi3yts.vercel.app'
SPOTIFY_API_BASE = 'https://api2.spotify.pgwiz.uk'  # Spotify API Gateway
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
COOKIES_FILE_PATH = os.path.join(BASE_DIR, "cookies.txt")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "public", "downloads")
TEMP_LINK_EXPIRY_SECONDS = 600  # 10 minutes

# --- In-memory Storage & Locks ---
temp_links = {}
stream_cache = {}
url_cache = {}  # cache_id -> (stream_url, timestamp, optional_video_id)
cache_lock = threading.Lock()
recent_downloads = []
recent_lock = threading.Lock()

# --- Cookie Manager ---
COOKIE_MANAGER = {
    'path': None,
    'loaded': False
}

def get_cookie_file_path():
    """Get or create cookie file path for yt-dlp."""
    global COOKIE_MANAGER
    
    if os.path.exists(COOKIES_FILE_PATH) and os.path.getsize(COOKIES_FILE_PATH) > 0:
        return COOKIES_FILE_PATH

    if COOKIE_MANAGER['loaded'] and COOKIE_MANAGER['path'] and os.path.exists(COOKIE_MANAGER['path']):
        return COOKIE_MANAGER['path']
    
    cookie_env = os.environ.get("YTDLP_COOKIES")
    if cookie_env:
        try:
            temp_dir = tempfile.gettempdir()
            cookie_path = os.path.join(temp_dir, "yt_cookies_reusable.txt")
            with open(cookie_path, "w", encoding='utf-8') as f:
                f.write(cookie_env)
            
            COOKIE_MANAGER['path'] = cookie_path
            COOKIE_MANAGER['loaded'] = True
            return cookie_path
        except Exception as e:
            print(f"Failed to create cookie file from env: {e}")
            return None
            
    return None

def cache_stream_url(url: str, video_id: str = None) -> str:
    """Cache full stream URL and return short 12-char hash ID."""
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
    with cache_lock:
        url_cache[url_hash] = (url, time.time(), video_id)
    return url_hash
