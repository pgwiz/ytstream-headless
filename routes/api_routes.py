import asyncio
import time
import re
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, stream_cache, cache_stream_url, recent_downloads, recent_lock
from services.ytdlp_service import extract_media_info, search_youtube, extract_flat_playlist, extract_youtube_radio, extract_generic_media
from services.spotify_service import fetch_spotify_tracks, search_spotify, get_spotify_playlist
from services.audio_proxy_service import proxy_audio_stream

api_bp = Blueprint('api', __name__)

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for API monitoring."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "4.0.0-py",
        "engine": "Python (yt-dlp + Flask)",
        "services": {
            "youtube_streaming": "active",
            "youtube_playlist": "active",
            "youtube_radio": "active",
            "youtube_search": "active",
            "audio_proxy": "active",
            "spotify_extractor": "active (100% keyless embed + YouTube resolution)",
            "spotify_playlist": "active"
        }
    })

@api_bp.route('/api/info', methods=['GET'])
def api_info_endpoint():
    """API metadata and endpoints list."""
    return jsonify({
        "name": "YouTube & Spotify Stream API (Python Engine)",
        "version": "4.0.0-py",
        "runtime": "Python 3 / Flask",
        "features": {
            "youtube": [
                "video streaming",
                "quality selection (audio, audio_high, saver, 360p, 720p)",
                "flat playlist & album extraction",
                "smart radio mix generation",
                "audio proxying",
                "search"
            ],
            "spotify": [
                "100% keyless metadata extraction (tracks, albums, playlists)",
                "zero Spotify API keys or external gateways required",
                "automatic YouTube videoId resolution and stream generation",
                "single track and full playlist audio downloads"
            ]
        },
        "endpoints": {
            "streaming": {
                "GET /get?ytl={url}&quality={quality}&limit={limit}": "Get streaming links with quality selection (YouTube or Spotify)",
                "GET /stream/{video_id_or_spotify_url}?quality={quality}": "Get direct video stream URL & metadata",
                "GET /stream/play?id={cache_id}": "Direct audio stream proxy with Range headers support"
            },
            "youtube": {
                "GET /api/youtube/playlist?id={playlist_id}&limit={n}": "Extract YouTube playlist, album, or mix metadata and track list",
                "GET /api/youtube/radio/{video_id}?limit={n}": "Extract YouTube Smart Radio / Mix recommendations for a track"
            },
            "spotify": {
                "GET /api/spotify/playlist/{id}": "Get Spotify playlist tracks (keyless)",
                "GET /api/search/spotify?query={q}&type={type}&limit={n}": "Search Spotify / music catalog"
            },
            "search": {
                "GET /api/search/youtube?query={q}&limit={n}": "Search YouTube videos"
            },
            "download": {
                "POST /download": "Download MP3 tracks/playlists as split archives (YouTube or Spotify)",
                "GET /temp_download/{link_id}": "Download temporary generated MP3/Zip"
            },
            "docs": {
                "GET /docs": "Interactive API Documentation & Developer Playground"
            }
        },
        "spotify_configured": True
    })

@api_bp.route('/api/status', methods=['GET'])
def api_status_endpoint():
    """API deployment & system status."""
    return jsonify({
        "service": "YouTube & Spotify Stream Extractor API",
        "version": "4.0.0-py",
        "status": "online",
        "runtime": "Python Flask",
        "spotify_keyless": True,
        "timestamp": datetime.now().isoformat()
    })

@api_bp.route('/get', methods=['GET'])
def get_endpoint():
    """Scrape metadata & stream URLs for YouTube video, playlist, mix, or Spotify link."""
    youtube_url = request.args.get('ytl', '').strip()
    quality = request.args.get('quality', 'audio').strip()
    limit = int(request.args.get('limit', 5))

    if not youtube_url:
        return render_template('docs.html')

    try:
        if "open.spotify.com" in youtube_url:
            spotify_data = asyncio.run(fetch_spotify_tracks(youtube_url, limit=limit, resolve_youtube=True))
            if not spotify_data:
                return jsonify({"error": "Could not fetch Spotify tracks from the provided URL."}), 500
            
            # If single track, resolve full stream and proxy URL immediately
            if not spotify_data.get('is_playlist') and spotify_data.get('tracks'):
                t = spotify_data['tracks'][0]
                v_id = t.get('videoId')
                if v_id:
                    s_info = extract_media_info(f"https://www.youtube.com/watch?v={v_id}", quality=quality)
                    if s_info and s_info.get('tracks'):
                        stream_track = s_info['tracks'][0]
                        s_url = stream_track.get('url')
                        c_id = cache_stream_url(s_url, video_id=v_id) if s_url else ""
                        return jsonify({
                            "title": t.get('name') or t.get('title'),
                            "artist": t.get('artist'),
                            "uploader": t.get('artist'),
                            "videoId": v_id,
                            "url": s_url,
                            "streamUrl": s_url,
                            "proxy_url": f"/stream/play?id={c_id}" if c_id else "",
                            "cache_id": c_id,
                            "quality": quality,
                            "duration": t.get('duration'),
                            "thumbnail": t.get('thumbnail'),
                            "ext": "mp4",
                            "source": "spotify"
                        })
            
            # For playlists/albums
            for t in spotify_data.get('tracks', []):
                v_id = t.get('videoId')
                if v_id:
                    t['stream_endpoint'] = f"/stream/{v_id}"
                    t['proxy_url'] = f"/stream/{v_id}"
            
            return jsonify(spotify_data)

        # Fast path for YouTube playlists, albums, and mixes
        if ("youtube.com" in youtube_url or "youtu.be" in youtube_url) and ("list=" in youtube_url or "playlist" in youtube_url) and not ("v=" in youtube_url and not "list=RD" in youtube_url):
            pl_data = extract_flat_playlist(youtube_url, limit=limit)
            return jsonify({
                "is_playlist": True,
                "playlist_title": pl_data.get('title', 'Playlist'),
                "title": pl_data.get('title', 'Playlist'),
                "total_tracks": pl_data.get('total_tracks', len(pl_data.get('tracks', []))),
                "quality": quality,
                "tracks": pl_data.get('tracks', [])[:limit]
            })

        # YouTube video extraction
        if "youtube.com" in youtube_url or "youtu.be" in youtube_url:
            info = extract_media_info(youtube_url, quality=quality)
        else:
            # Universal Multi-Platform Fallback (Instagram, TikTok, Twitter/X, SoundCloud, Facebook, Reddit, etc.)
            info = extract_generic_media(youtube_url, quality=quality)

        if not info:
            return jsonify({"error": "Could not extract media info."}), 500

        if info.get('is_playlist'):
            tracks = info.get('tracks', [])[:limit]
            for t in tracks:
                if t.get('url'):
                    c_id = cache_stream_url(t['url'], video_id=t.get('videoId'))
                    t['proxy_url'] = f"/stream/play?id={c_id}"
            return jsonify({
                "is_playlist": True,
                "playlist_title": info.get('playlist_title', 'Playlist'),
                "quality": quality,
                "tracks": tracks
            })
        else:
            tracks = info.get('tracks', [])
            if not tracks:
                return jsonify({"error": "No tracks found for the given video URL."}), 404
            track = tracks[0]
            stream_url = track.get('url')
            clean_vid = track.get('videoId') or track.get('id', '')
            cache_id = cache_stream_url(stream_url, video_id=clean_vid) if stream_url else ""
            return jsonify({
                "title": track.get('title', track.get('name', 'Untitled')),
                "url": stream_url,
                "streamUrl": stream_url,
                "proxy_url": f"/stream/play?id={cache_id}" if cache_id else "",
                "cache_id": cache_id,
                "quality": quality,
                "ext": "mp4",
                "isLive": False,
                "thumbnail": track.get('thumbnail', f"https://img.youtube.com/vi/{clean_vid}/mqdefault.jpg"),
                "duration": track.get('duration_string', track.get('duration', 'N/A')),
                "videoId": clean_vid,
                "artist": track.get('artist', track.get('uploader', 'Unknown')),
                "uploader": track.get('uploader', 'Unknown')
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def handle_stream_request(video_id):
    """Helper to process /stream/<video_id> requests (Supports YouTube ID or Spotify URL)."""
    try:
        quality = request.args.get('quality', 'audio').strip()
        clean_id = video_id

        # If Spotify URL passed to /stream
        if "open.spotify.com" in video_id:
            sp_data = asyncio.run(fetch_spotify_tracks(video_id, limit=1, resolve_youtube=True))
            if sp_data and sp_data.get('tracks') and sp_data['tracks'][0].get('videoId'):
                clean_id = sp_data['tracks'][0]['videoId']
                youtube_url = f"https://www.youtube.com/watch?v={clean_id}"
            else:
                return jsonify({"error": "Could not resolve Spotify URL to a playable YouTube track."}), 404
        elif video_id.startswith('http') and not ("youtube.com" in video_id or "youtu.be" in video_id):
            # Universal Multi-Platform direct stream (Instagram, TikTok, Twitter/X, SoundCloud, etc.)
            info = extract_generic_media(video_id, quality=quality)
            if info and info.get('tracks'):
                track = info['tracks'][0]
                stream_url = track.get('url')
                cache_id = cache_stream_url(stream_url, video_id=track.get('id', 'media')) if stream_url else ""
                return jsonify({
                    "videoId": track.get('id', 'media'),
                    "streamUrl": stream_url,
                    "url": stream_url,
                    "proxy_url": f"/stream/play?id={cache_id}" if cache_id else "",
                    "cache_id": cache_id,
                    "cached": False,
                    "quality": quality,
                    "title": track.get('title', 'Media Stream'),
                    "uploader": track.get('uploader', 'Unknown'),
                    "duration": track.get('duration', 'N/A'),
                    "thumbnail": track.get('thumbnail', ''),
                    "ext": track.get('ext', 'mp4'),
                    "source": track.get('source', 'web')
                })
            return jsonify({"error": "Could not extract stream URL for this media."}), 404
        elif video_id.startswith('http'):
            youtube_url = video_id
            match = re.search(r'(?:v=|\/|youtu\.be\/)([\w-]{11})', video_id)
            if match:
                clean_id = match.group(1)
        else:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        cache_key = f"{clean_id}_{quality}"
        if cache_key in stream_cache:
            cached_data = stream_cache[cache_key]
            if time.time() - cached_data['timestamp'] < 3600:
                stream_url = cached_data['url']
                cache_id = cache_stream_url(stream_url, video_id=clean_id)
                return jsonify({
                    "videoId": clean_id,
                    "streamUrl": stream_url,
                    "url": stream_url,
                    "proxy_url": f"/stream/play?id={cache_id}",
                    "cache_id": cache_id,
                    "cached": True,
                    "quality": quality,
                    "title": cached_data.get('title', 'Cached Stream'),
                    "uploader": cached_data.get('uploader', 'Unknown'),
                    "duration": cached_data.get('duration', 'N/A'),
                    "thumbnail": f"https://img.youtube.com/vi/{clean_id}/mqdefault.jpg",
                    "ext": "mp4"
                })

        info = extract_media_info(youtube_url, quality=quality)
        if info and info.get('tracks') and len(info['tracks']) > 0:
            track = info['tracks'][0]
            stream_url = track.get('url')
            if stream_url:
                cache_id = cache_stream_url(stream_url, video_id=clean_id)
                proxy_url = f"/stream/play?id={cache_id}"
                title = track.get('title') or track.get('name') or 'Untitled'
                uploader = track.get('uploader') or track.get('artist') or 'Unknown'
                duration = track.get('duration_string') or track.get('duration') or 'N/A'
                thumbnail = track.get('thumbnail') or f"https://img.youtube.com/vi/{clean_id}/mqdefault.jpg"

                stream_cache[cache_key] = {
                    'url': stream_url,
                    'timestamp': time.time(),
                    'title': title,
                    'uploader': uploader,
                    'duration': duration
                }

                return jsonify({
                    "videoId": clean_id,
                    "streamUrl": stream_url,
                    "url": stream_url,
                    "proxy_url": proxy_url,
                    "cache_id": cache_id,
                    "cached": False,
                    "quality": quality,
                    "title": title,
                    "uploader": uploader,
                    "duration": duration,
                    "thumbnail": thumbnail,
                    "ext": "mp4"
                })

        return jsonify({"error": "Could not get stream URL for this video."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/stream/<path:video_id>', methods=['GET', 'POST'])
@api_bp.route('/api/stream/<path:video_id>', methods=['GET', 'POST'])
def get_stream_endpoint(video_id):
    """Direct stream URL endpoint for YouTube video ID or Spotify URL."""
    return handle_stream_request(video_id)

@api_bp.route('/stream/play', methods=['GET'])
def proxy_stream_play():
    """Proxy direct audio bytes to media player with Range header support."""
    cache_id = request.args.get('id')
    encoded_url = request.args.get('url')
    return proxy_audio_stream(cache_id, encoded_url, request.headers)

@api_bp.route('/api/search/youtube', methods=['GET'])
def search_youtube_endpoint():
    """YouTube search endpoint."""
    query = request.args.get('query')
    limit = int(request.args.get('limit', 10))

    if not query:
        return jsonify({"error": "Query parameter is required."}), 400

    try:
        results = asyncio.run(search_youtube(query, limit))
        return jsonify({
            "query": query,
            "limit": limit,
            "total_results": len(results),
            "results": results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/search/spotify', methods=['GET'])
def search_spotify_endpoint():
    """Spotify search endpoint for tracks, albums, playlists (zero API keys required)."""
    query = request.args.get('query')
    search_type = request.args.get('type', 'track')
    limit = int(request.args.get('limit', 10))

    if not query:
        return jsonify({"error": "Query parameter is required."}), 400

    if search_type not in ['track', 'album', 'playlist', 'artist']:
        return jsonify({"error": "Type must be one of: track, album, playlist, artist"}), 400

    res = asyncio.run(search_spotify(query, search_type, limit))
    return jsonify(res)

@api_bp.route('/api/spotify/playlist/<playlist_id>', methods=['GET'])
def get_spotify_playlist_endpoint(playlist_id):
    """Spotify playlist tracks endpoint (Keyless embed extraction)."""
    res = asyncio.run(get_spotify_playlist(playlist_id))
    if res:
        return jsonify(res)
    return jsonify({"error": "Could not fetch Spotify playlist"}), 500

@api_bp.route('/api/youtube/playlist', methods=['GET'])
@api_bp.route('/playlist/<path:playlist_id>', methods=['GET'])
def get_youtube_playlist_endpoint(playlist_id=None):
    """Extract YouTube playlist, album, or mix metadata and track list (flat extraction)."""
    target = playlist_id or request.args.get('id') or request.args.get('url') or request.args.get('ytl') or ''
    limit = int(request.args.get('limit', 15))
    if not target:
        return jsonify({"error": "Playlist ID or URL is required (param 'id' or 'url')."}), 400
    try:
        data = extract_flat_playlist(target, limit=limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/youtube/radio/<video_id>', methods=['GET'])
@api_bp.route('/api/youtube/radio', methods=['GET'])
def get_youtube_radio_endpoint(video_id=None):
    """Extract YouTube Smart Radio / Mix recommendations for a given track video ID."""
    v_id = video_id or request.args.get('id') or request.args.get('videoId') or ''
    limit = int(request.args.get('limit', 15))
    if not v_id:
        return jsonify({"error": "Video ID is required."}), 400
    try:
        data = extract_youtube_radio(v_id, limit=limit)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from services.archive_service import get_all_downloads, delete_download, clear_all_downloads

@api_bp.route('/api/recent-downloads', methods=['GET'])
def get_recent_downloads():
    """Get the list of recent downloads."""
    with recent_lock:
        return jsonify({"recent_downloads": recent_downloads.copy()})

@api_bp.route('/api/downloads', methods=['GET'])
def list_downloads_endpoint():
    """List all saved audio downloads and ZIP archives on the server."""
    files = get_all_downloads()
    return jsonify({
        "total_files": len(files),
        "downloads": files
    })

@api_bp.route('/api/downloads', methods=['DELETE', 'POST'])
def delete_downloads_endpoint():
    """Delete a specific download file or clear all downloads."""
    data = request.get_json(silent=True) or {}
    file_target = request.args.get('file') or data.get('file') or data.get('path')
    clear_all = request.args.get('clear_all') == 'true' or data.get('clear_all') is True

    if clear_all:
        success, msg = clear_all_downloads()
        if success:
            return jsonify({"success": True, "message": msg})
        return jsonify({"error": msg}), 500

    if not file_target:
        return jsonify({"error": "Target file or path is required."}), 400

    success, msg = delete_download(file_target)
    if success:
        return jsonify({"success": True, "message": msg, "target": file_target})
    return jsonify({"error": msg}), 400
