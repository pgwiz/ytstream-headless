import os
import uuid
import re
import shutil
import asyncio
import threading
from flask import Blueprint, request, jsonify, send_from_directory, url_for
from config import DOWNLOADS_DIR, TEMP_LINK_EXPIRY_SECONDS, temp_links, recent_downloads, recent_lock
from services.ytdlp_service import download_youtube_tracks, extract_media_info, extract_generic_media
from services.spotify_service import fetch_spotify_tracks
from services.archive_service import schedule_cleanup

download_bp = Blueprint('download', __name__)

@download_bp.route('/download', methods=['POST'])
def handle_download():
    """Handle download request with enhanced playlist + archive support."""
    try:
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()
        track_data = data.get('track_data')
        
        print(f"📥 Received download request - URL: {repr(url)}, Track Data: {bool(track_data)}")
        
        if not url and not track_data:
            return jsonify({"error": "URL or track data is required."}), 400
        
        tracks = []
        playlist_name = None
        is_playlist = False
        session_id = str(uuid.uuid4())
        
        if track_data:
            tracks = [track_data]
            print(f"Single track download requested: {track_data.get('name', 'Unknown')}")
        elif url and "open.spotify.com" in url:
            print(f"🎵 Spotify URL detected: {url}")
            spotify_data = asyncio.run(fetch_spotify_tracks(url))
            
            if not spotify_data or not spotify_data.get('tracks'):
                return jsonify({
                    "error": "Could not fetch tracks from Spotify URL. Make sure the URL is valid and accessible."
                }), 500
            
            tracks = spotify_data['tracks']
            playlist_name = spotify_data.get('playlist_name')
            is_playlist = spotify_data.get('is_playlist', len(tracks) > 1)
            
        elif url and ("youtube.com" in url or "youtu.be" in url):
            info = extract_media_info(url)
            if info and info.get('tracks'):
                tracks = info['tracks']
                is_playlist = info.get('is_playlist', False)
                if is_playlist:
                    playlist_name = info.get('playlist_title')
            else:
                return jsonify({"error": "Could not extract video information from YouTube URL."}), 500
        elif url and url.startswith("http"):
            # Universal Multi-Platform Fallback (Instagram, TikTok, Twitter/X, SoundCloud, Facebook, Reddit, Vimeo, etc.)
            info = extract_generic_media(url)
            if info and info.get('tracks'):
                tracks = info['tracks']
                is_playlist = info.get('is_playlist', False)
                if is_playlist:
                    playlist_name = info.get('playlist_title')
            else:
                return jsonify({"error": "Could not extract media from the provided URL."}), 500
        else:
            return jsonify({"error": "Please provide a valid media URL."}), 400
        
        if not tracks:
            return jsonify({"error": "No tracks found to download."}), 400
        
        is_playlist_download = len(tracks) > 1 or is_playlist
        
        if is_playlist_download and playlist_name:
            sanitized_folder_name = re.sub(r'[\\/*?:"<>|]', "", playlist_name)
            save_dir = os.path.join(DOWNLOADS_DIR, sanitized_folder_name)
        else:
            save_dir = os.path.join(DOWNLOADS_DIR, session_id)
        
        os.makedirs(save_dir, exist_ok=True)
        print(f"📁 Created download directory: {save_dir}")
        
        downloaded_files, message, download_info = download_youtube_tracks(
            tracks, 
            save_dir, 
            is_playlist=is_playlist_download, 
            playlist_name=playlist_name
        )
        
        if not downloaded_files:
            if os.path.exists(save_dir) and not os.listdir(save_dir):
                shutil.rmtree(save_dir)
            return jsonify({"error": message or "No files were downloaded."}), 500
        
        schedule_cleanup(save_dir, TEMP_LINK_EXPIRY_SECONDS)
        
        with recent_lock:
            current_recent = recent_downloads.copy()
        
        source = "spotify" if url and "open.spotify.com" in url else "youtube"
        
        if is_playlist_download:
            return jsonify({
                "message": message, 
                "playlist_name": playlist_name,
                "is_playlist": True,
                "archives": download_info,
                "recent_downloads": current_recent,
                "success": True,
                "total_files": len(downloaded_files),
                "total_archives": len(download_info),
                "source": source
            })
        else:
            return jsonify({
                "message": message, 
                "files": download_info,
                "recent_downloads": current_recent,
                "success": True,
                "total_files": len(download_info),
                "source": source
            })
        
    except Exception as e:
        error_msg = f"Download error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500

@download_bp.route('/downloads/<path:filepath>')
@download_bp.route('/downloads/file/<path:filepath>')
def serve_download_file(filepath):
    """Directly serve a downloaded file or archive from DOWNLOADS_DIR with Range header and download toggle."""
    abs_downloads = os.path.abspath(DOWNLOADS_DIR)
    target_abs = os.path.abspath(os.path.join(DOWNLOADS_DIR, filepath))
    
    if not target_abs.startswith(abs_downloads):
        return "Permission denied", 403
    
    if not os.path.exists(target_abs) or os.path.isdir(target_abs):
        return "File not found or link expired.", 404
    
    is_download = request.args.get('download') == '1' or request.args.get('attachment') == '1'
    
    return send_from_directory(
        os.path.dirname(target_abs),
        os.path.basename(target_abs),
        as_attachment=is_download
    )

@download_bp.route('/create_temp_link', methods=['POST'])
def create_temp_link():
    """Manual temp link creation."""
    data = request.get_json() or {}
    file_path_relative = data.get('path')
    
    if not file_path_relative:
        return jsonify({'error': 'File path required'}), 400
    
    absolute_path = os.path.join(DOWNLOADS_DIR, file_path_relative)
    if not os.path.exists(absolute_path):
        return jsonify({'error': 'File not found on server. It may have been cleaned up.'}), 404
    
    link_id = str(uuid.uuid4())
    temp_links[link_id] = absolute_path
    
    threading.Timer(TEMP_LINK_EXPIRY_SECONDS, lambda: temp_links.pop(link_id, None)).start()
    
    download_url = url_for('download.download_temp', link_id=link_id, _external=True)
    return jsonify({'download_url': download_url})

@download_bp.route('/temp_download/<link_id>')
def download_temp(link_id):
    """Serve file from temporary link WITHOUT popping to allow multiple audio plays and device downloads."""
    file_path = temp_links.get(link_id)
    
    if not file_path or not os.path.exists(file_path):
        return "Download link expired or invalid.", 404
    
    is_download = request.args.get('download') == '1' or request.args.get('attachment') == '1'
    
    return send_from_directory(
        os.path.dirname(file_path), 
        os.path.basename(file_path), 
        as_attachment=is_download
    )
