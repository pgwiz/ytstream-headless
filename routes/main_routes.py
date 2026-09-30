import os
from flask import Blueprint, jsonify, Response, request

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Root JSON API overview for Headless API."""
    return jsonify({
        "service": "Stream Extractor Headless API",
        "status": "online",
        "version": "4.2.0-headless",
        "mode": "headless_api",
        "cors": "enabled (Access-Control-Allow-Origin: *)",
        "documentation": "/docs.md",
        "health": "/health",
        "endpoints": {
            "extract_stream": "GET /get?ytl={url}&quality={preset}&limit=5",
            "stream_meta": "GET /stream/{videoId_or_spotifyUrl}?quality={preset}",
            "stream_proxy": "GET /stream/play?id={cacheId}",
            "search_youtube": "GET /api/search/youtube?query={q}&limit=10",
            "search_spotify": "GET /api/search/spotify?query={q}&type=track",
            "spotify_playlist": "GET /api/spotify/playlist/{id}",
            "download": "POST /download",
            "downloads_list": "GET /api/downloads"
        },
        "supported_platforms": [
            "YouTube (Videos, Shorts, Playlists, Smart Radio)",
            "Spotify (100% Keyless Tracks, Albums, Playlists)",
            "TikTok (Keyless direct CDN progressive video & audio)",
            "Instagram (Reels, Posts, IGTV)",
            "SoundCloud",
            "Bandcamp",
            "Twitter / X",
            "Reddit (v.redd.it)",
            "Vimeo"
        ]
    })

@main_bp.route('/docs')
@main_bp.route('/documentation')
@main_bp.route('/docs.md')
@main_bp.route('/api/docs.md')
@main_bp.route('/documentation.md')
def docs_md():
    """Token-efficient raw Markdown documentation for AI agents and developers."""
    md_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs.md')
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content, mimetype='text/markdown; charset=utf-8')
    return Response("# Documentation not found", status=404, mimetype='text/markdown')
