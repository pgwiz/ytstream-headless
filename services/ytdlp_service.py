import sys
import subprocess
import json
import re
import os
import random
import time
import shutil
from config import BASE_DIR, get_cookie_file_path, cache_stream_url
from services.archive_service import create_split_archives, safe_delete_files, create_temp_link_for_file, add_to_recent_downloads

def get_python_binary():
    venv_python = os.path.join(BASE_DIR, "venv", "bin", "python")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable

QUALITY_FORMAT_MAP = {
    'audio': '18/140/ba/b/bestaudio/best',
    'audio_high': '18/140/251/ba/bestaudio/best',
    'high': '18/140/251/ba/bestaudio/best',
    'saver': '139/18/ba[abr<=64]/worst',
    'low': '139/18/ba[abr<=64]/worst',
    'video': '18/best[height<=360]',
    '360p': '18/best[height<=360]',
    '720p': '22/18/136+140/bestvideo[height<=720]+bestaudio/best',
    'video_hd': '22/18/136+140/bestvideo[height<=720]+bestaudio/best',
    'best': '18/22/best'
}

GENERIC_QUALITY_MAP = {
    'audio': 'bestaudio/best',
    'audio_high': 'bestaudio[abr>=160]/bestaudio/best',
    'high': 'bestaudio[abr>=160]/bestaudio/best',
    'saver': 'b[height<=480]/b[height<=360]/worst[ext=mp4]/worst',
    'low': 'b[height<=480]/b[height<=360]/worst[ext=mp4]/worst',
    'video': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best',
    '360p': 'bestvideo[height<=360]+bestaudio/best[height<=360]/best',
    '480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best[height<=720]/best',
    'video_480p': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best[height<=720]/best',
    'sd': 'bestvideo[height<=480]+bestaudio/best[height<=480]/best[height<=720]/best',
    '720p': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
    'video_hd': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
    'best': 'bestvideo+bestaudio/best'
}

def _execute_yt_dlp_command(youtube_url: str, quality: str = None):
    cookie_path = get_cookie_file_path()
    python_bin = get_python_binary()
    
    format_spec = QUALITY_FORMAT_MAP.get(quality, '18/140/ba/b/bestaudio/best') if quality else '18/140/ba/b/bestaudio/best'
    
    client_configs = [
        "youtube:player_client=android",
        "youtube:player_client=mweb",
        "youtube:player_client=web",
        "youtube:player_client=tv",
        ""
    ]

    last_error = ""

    for client_args in client_configs:
        command = [
            python_bin, "-m", "yt_dlp",
            youtube_url,
            "--no-cache-dir",
            "--no-check-certificate", 
            "--remote-components", "ejs:github",
            "--dump-single-json",
            "-f", format_spec
        ]

        if client_args:
            command.extend(["--extractor-args", client_args])

        if cookie_path and "android" not in client_args:
            command.extend(["--cookies", cookie_path])

        try:
            process = subprocess.run(command, capture_output=True, text=True, check=True)
            return json.loads(process.stdout)
        except subprocess.CalledProcessError as e:
            last_error = e.stderr.strip()
            print(f"yt-dlp extract note ({client_args or 'default'}): {last_error[:120]}")
            if "Private video" in last_error or "is unavailable" in last_error:
                break
        except Exception as e:
            last_error = str(e)

    if "confirm you're not a bot" in last_error:
        raise RuntimeError("YouTube's bot detection was triggered.")
    if "is unavailable" in last_error or "Private video" in last_error:
        raise RuntimeError("The requested video is private or unavailable.")
    raise RuntimeError(f"Failed to extract video information: {last_error}")

def _process_single_video_entry(entry: dict) -> dict:
    if not entry:
        return None

    return {
        'title': entry.get('title', 'Untitled'),
        'url': entry.get('url'),
        'thumbnail': entry.get('thumbnail'),
        'duration': entry.get('duration_string', 'N/A'),
        'uploader': entry.get('uploader', 'Unknown'),
        'videoId': entry.get('id', ''),
        'name': entry.get('title', 'Untitled'),
        'artist': entry.get('uploader', 'Unknown')
    }

def extract_media_info(youtube_url: str, quality: str = None) -> dict:
    info = _execute_yt_dlp_command(youtube_url, quality=quality)
    
    if 'entries' in info:
        tracks = [
            {
                'title': entry.get('title', 'Untitled'),
                'url': entry.get('url'),
                'id': entry.get('id'),
                'videoId': entry.get('id'),
                'duration_string': entry.get('duration_string', 'N/A'),
                'uploader': entry.get('uploader', 'Unknown'),
                'name': entry.get('title', 'Untitled'),
                'artist': entry.get('uploader', 'Unknown'),
                'duration': entry.get('duration_string', 'N/A'),
                'thumbnail': entry.get('thumbnail', f"https://img.youtube.com/vi/{entry.get('id', '')}/mqdefault.jpg")
            }
            for entry in info.get('entries', []) if entry
        ]
        
        return {
            'is_playlist': True,
            'playlist_title': info.get('title'),
            'tracks': tracks
        }
    else:
        track = _process_single_video_entry(info)
        return {
            'is_playlist': False,
            'tracks': [track] if track and track.get('url') else []
        }

async def search_youtube(query, limit=10):
    cookie_path = get_cookie_file_path()
    python_bin = get_python_binary()
    client_configs = ["youtube:player_client=android", "youtube:player_client=mweb", "youtube:player_client=web", ""]

    for client_args in client_configs:
        try:
            command = [
                python_bin, "-m", "yt_dlp",
                f"ytsearch{limit}:{query}",
                "--remote-components", "ejs:github",
                "--dump-single-json",
                "--flat-playlist",
                "--no-cache-dir"
            ]
            if client_args:
                command.extend(["--extractor-args", client_args])

            if cookie_path and "android" not in client_args:
                command.extend(["--cookies", cookie_path])
            
            process = subprocess.run(command, capture_output=True, text=True, check=True)
            data = json.loads(process.stdout)
            
            results = []
            if 'entries' in data:
                for entry in data['entries'][:limit]:
                    if entry:
                        v_id = entry.get('id', '')
                        title = entry.get('title', 'Unknown Title')
                        uploader = entry.get('uploader') or entry.get('channel') or 'YouTube Artist'
                        results.append({
                            'videoId': v_id,
                            'id': v_id,
                            'name': title,
                            'title': title,
                            'artist': uploader,
                            'uploader': uploader,
                            'duration': entry.get('duration_string') or (f"{int(entry.get('duration')//60)}:{int(entry.get('duration')%60):02d}" if entry.get('duration') else '3:30'),
                            'duration_string': entry.get('duration_string', 'Unknown'),
                            'thumbnail': entry.get('thumbnail', f"https://img.youtube.com/vi/{v_id}/mqdefault.jpg"),
                            'url': f"https://www.youtube.com/watch?v={v_id}"
                        })
            if results:
                return results
        except Exception as e:
            print(f"Search YouTube attempt ({client_args or 'default'}) note: {e}")

    return []

def extract_flat_playlist(playlist_or_mix_url: str, limit: int = 15) -> dict:
    """
    Extract YouTube playlist, album, or Smart Radio / Mix metadata and tracks via flat-playlist (0ms audio download).
    Supports regular playlists (list=PL...), smart radios (list=RD<id>), and artist discs.
    """
    cookie_path = get_cookie_file_path()
    python_bin = get_python_binary()

    # Clean URL / ID input
    url = playlist_or_mix_url.strip()
    if "list=RD" in url:
        match = re.search(r'list=RD([\w-]{11})', url)
        if match:
            v_id = match.group(1)
            url = f"https://www.youtube.com/watch?v={v_id}&list=RD{v_id}"
        elif url.startswith("RD"):
            clean_vid = url[2:] if len(url) > 2 else url
            url = f"https://www.youtube.com/watch?v={clean_vid}&list={url}"
    elif url.startswith("RD"):
        clean_vid = url[2:] if len(url) > 2 else url
        url = f"https://www.youtube.com/watch?v={clean_vid}&list={url}"
    elif url.startswith("PL") or url.startswith("OLAK5uy_"):
        url = f"https://www.youtube.com/playlist?list={url}"
    elif not url.startswith("http"):
        clean_id = url.split('&')[0].split('?')[0].strip()
        url = f"https://www.youtube.com/watch?v={clean_id}&list=RD{clean_id}"

    client_configs = ["youtube:player_client=android", "youtube:player_client=mweb", "youtube:player_client=web", ""]

    last_error = ""
    for client_args in client_configs:
        command = [
            python_bin, "-m", "yt_dlp",
            url,
            "--flat-playlist",
            "--dump-single-json",
            "--playlist-end", str(limit),
            "--no-cache-dir",
            "--no-check-certificate"
        ]
        if client_args:
            command.extend(["--extractor-args", client_args])
        if cookie_path and "android" not in client_args:
            command.extend(["--cookies", cookie_path])

        try:
            process = subprocess.run(command, capture_output=True, text=True, check=True)
            data = json.loads(process.stdout)

            entries = data.get('entries', []) or []
            tracks = []
            for entry in entries[:limit]:
                if not entry:
                    continue
                v_id = entry.get('id', '')
                if not v_id:
                    continue
                title = entry.get('title', 'Unknown Track')
                uploader = entry.get('uploader') or entry.get('channel') or entry.get('artist') or 'YouTube Music'
                
                # Duration formatting
                dur_str = entry.get('duration_string')
                if not dur_str and entry.get('duration'):
                    try:
                        dur_sec = int(entry.get('duration'))
                        dur_str = f"{dur_sec // 60}:{dur_sec % 60:02d}"
                    except Exception:
                        dur_str = '3:30'
                
                tracks.append({
                    'id': v_id,
                    'videoId': v_id,
                    'title': title,
                    'name': title,
                    'artist': uploader,
                    'uploader': uploader,
                    'duration': dur_str or '--:--',
                    'duration_string': dur_str or '--:--',
                    'thumbnail': entry.get('thumbnail') or f"https://img.youtube.com/vi/{v_id}/mqdefault.jpg",
                    'url': f"https://www.youtube.com/watch?v={v_id}"
                })

            playlist_title = data.get('title') or ('Smart Radio Mix' if 'list=RD' in url else 'YouTube Playlist')
            return {
                'status': 'success',
                'is_playlist': True,
                'playlist_id': data.get('id') or 'playlist',
                'title': playlist_title,
                'playlist_title': playlist_title,
                'total_tracks': len(tracks),
                'tracks': tracks
            }
        except subprocess.CalledProcessError as e:
            last_error = e.stderr.strip()
            print(f"Flat playlist extract attempt ({client_args or 'default'}): {last_error[:120]}")
        except Exception as e:
            last_error = str(e)

    raise RuntimeError(f"Failed to extract playlist or radio mix: {last_error}")

def extract_youtube_radio(video_id: str, limit: int = 15) -> dict:
    """
    Extract YouTube's official Smart Radio / endless autoplay Mix for a specific video ID (list=RD<video_id>).
    """
    clean_id = video_id.replace('https://www.youtube.com/watch?v=', '').replace('https://youtu.be/', '').split('&')[0].split('?')[0].strip()
    mix_url = f"https://www.youtube.com/watch?v={clean_id}&list=RD{clean_id}"
    return extract_flat_playlist(mix_url, limit=limit)

def extract_instagram_embed_direct(url: str):
    """
    Direct extraction of Instagram Reels & Posts via public embed endpoint.
    Extracts direct CDN progressive MP4 stream without requiring login or cookies.
    """
    import urllib.request
    match = re.search(r'(?:reel|p)/([a-zA-Z0-9_-]+)', url)
    if not match:
        return None
    shortcode = match.group(1)
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1'
    }
    try:
        req = urllib.request.Request(embed_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            clean_url = None
            if 'video_url' in html:
                idx = html.find('video_url')
                start = html.find('https:', idx)
                end_mp4 = html.find('.mp4', start) + 4
                end_quote = html.find('"', end_mp4)
                if '\\"' in html[end_mp4:end_mp4+1000]:
                    end_quote = html.find('\\"', end_mp4)
                url_raw = html[start:end_quote].rstrip('\\"')
                clean_url = url_raw.replace('\\/', '/').replace(r'\u0026', '&')

            if clean_url:
                caption = f"Instagram Reel ({shortcode})"
                cap_m = re.search(r'<div class="Caption">.*?<span>(.*?)</span>', html, re.DOTALL)
                if cap_m:
                    caption = re.sub(r'<[^>]+>', '', cap_m.group(1)).strip()[:100]

                return {
                    'title': caption,
                    'name': caption,
                    'url': clean_url,
                    'streamUrl': clean_url,
                    'thumbnail': f"https://www.instagram.com/p/{shortcode}/media/?size=m",
                    'duration': 'N/A',
                    'duration_string': 'N/A',
                    'uploader': 'Instagram',
                    'artist': 'Instagram',
                    'videoId': shortcode,
                    'id': shortcode,
                    'ext': 'mp4',
                    'webpage_url': f"https://www.instagram.com/reel/{shortcode}/",
                    'source': 'instagram'
                }
    except Exception as e:
        print(f"Instagram embed extraction note: {e}")
    return None

def extract_tiktok_direct(url: str, quality: str = 'audio') -> dict:
    """
    Direct high-speed extraction for TikTok videos and audio tracks.
    Bypasses datacenter IP TLS bot blocks and curl-cffi requirements.
    """
    import urllib.request
    import urllib.parse
    clean_url = url.split('?')[0].strip()
    api_url = f"https://www.tikwm.com/api/?url={urllib.parse.quote(clean_url)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            if res.get('code') == 0 and res.get('data'):
                data = res['data']
                v_id = str(data.get('id', 'tiktok_media'))
                title = data.get('title') or f"TikTok Video {v_id}"

                if quality in ['audio', 'audio_high', 'saver', 'low']:
                    stream_url = data.get('music') or data.get('play')
                    ext = 'mp3'
                elif quality in ['480p', '360p', 'sd', 'video']:
                    stream_url = data.get('play') or data.get('wmplay')
                    ext = 'mp4'
                else:
                    stream_url = data.get('hdplay') or data.get('play') or data.get('wmplay')
                    ext = 'mp4'

                uploader = (data.get('author') or {}).get('nickname') or (data.get('author') or {}).get('unique_id') or 'TikTok Creator'
                dur_sec = data.get('duration', 0)
                dur_str = f"{dur_sec // 60}:{dur_sec % 60:02d}" if dur_sec else "N/A"
                cover = data.get('cover') or (data.get('author') or {}).get('avatar') or ""

                track = {
                    'id': v_id,
                    'videoId': v_id,
                    'title': title,
                    'name': title,
                    'url': stream_url,
                    'streamUrl': stream_url,
                    'thumbnail': cover,
                    'duration': dur_str,
                    'duration_string': dur_str,
                    'uploader': uploader,
                    'artist': uploader,
                    'ext': ext,
                    'webpage_url': clean_url,
                    'source': 'tiktok'
                }
                return {
                    'is_playlist': False,
                    'tracks': [track],
                    'source': 'tiktok'
                }
    except Exception as e:
        print(f"TikTok direct extraction note: {e}")
    return None

def extract_generic_media(url: str, quality: str = 'audio') -> dict:
    """
    Universal multi-stage media extractor for non-YouTube platforms
    (Instagram, TikTok, Twitter/X, SoundCloud, Reddit, Vimeo, Bandcamp, etc.).
    Preserves all original YouTube extraction routines untouched.
    """
    python_bin = get_python_binary()
    format_spec = GENERIC_QUALITY_MAP.get(quality, 'bestaudio/best')

    # Clean tracking query parameters from social URLs
    clean_url = url.strip()
    if any(p in clean_url for p in ["instagram.com", "tiktok.com", "twitter.com", "x.com"]):
        clean_url = clean_url.split('?')[0]

    # Direct high-speed bypass for TikTok (No cookies or curl-cffi required)
    if "tiktok.com" in clean_url:
        tt_data = extract_tiktok_direct(clean_url, quality=quality)
        if tt_data:
            return tt_data

    # Check for optional platform cookie files (ig_cookies.txt, or existing cookies.txt)
    cookie_to_use = None
    ig_cookie_path = os.path.join(BASE_DIR, "ig_cookies.txt")
    general_cookie = get_cookie_file_path()
    if os.path.exists(ig_cookie_path) and os.path.getsize(ig_cookie_path) > 0:
        cookie_to_use = ig_cookie_path
    elif general_cookie and os.path.exists(general_cookie) and os.path.getsize(general_cookie) > 0:
        cookie_to_use = general_cookie

    last_error = ""

    # Stage 1 & 2: Primary format then fallback format
    format_attempts = [format_spec, "b/ba/best"] if format_spec != "b/ba/best" else ["b/ba/best"]

    for fmt in format_attempts:
        command = [
            python_bin, "-m", "yt_dlp",
            clean_url,
            "--no-cache-dir",
            "--no-check-certificate",
            "--dump-single-json",
            "--no-playlist",
            "-f", fmt
        ]
        if cookie_to_use:
            command.extend(["--cookies", cookie_to_use])

        try:
            proc = subprocess.run(command, capture_output=True, text=True, check=True)
            info = json.loads(proc.stdout)
            title = info.get('title') or (info.get('description', 'Media')[:60] if info.get('description') else 'Media Item')
            stream_url = info.get('url')
            if not stream_url and info.get('formats'):
                stream_url = info['formats'][-1].get('url')

            uploader = info.get('uploader') or info.get('channel') or info.get('creator') or info.get('extractor') or 'Creator'
            dur = info.get('duration_string') or (f"{int(info.get('duration')//60)}:{int(info.get('duration')%60):02d}" if info.get('duration') else 'N/A')
            m_id = str(info.get('id', 'media'))
            thumb = info.get('thumbnail') or ''

            track = {
                'title': title,
                'name': title,
                'url': stream_url,
                'streamUrl': stream_url,
                'thumbnail': thumb,
                'duration': dur,
                'duration_string': dur,
                'uploader': uploader,
                'artist': uploader,
                'id': m_id,
                'videoId': m_id,
                'webpage_url': clean_url,
                'source': info.get('extractor', 'web')
            }
            return {
                'is_playlist': False,
                'tracks': [track],
                'source': info.get('extractor', 'web')
            }
        except subprocess.CalledProcessError as e:
            last_error = e.stderr.strip()
            print(f"Generic yt-dlp extraction ({fmt}): {last_error[:120]}")
        except Exception as e:
            last_error = str(e)

    # Stage 3: Public Embed Fallback for Instagram
    if "instagram.com" in clean_url:
        ig_data = extract_instagram_embed_direct(clean_url)
        if ig_data:
            return {
                'is_playlist': False,
                'tracks': [ig_data],
                'source': 'instagram'
            }

    # Contextual error diagnostic feedback
    if "HTTP Error 429" in last_error or "login" in last_error.lower():
        raise RuntimeError("Instagram rate-limited datacenter IP (HTTP 429). An Instagram session cookie (ig_cookies.txt) is required on this server.")
    if "impersonation" in last_error.lower() or "tiktok" in clean_url:
        raise RuntimeError("TikTok bot challenge detected. TLS browser impersonation (curl-cffi) is required on datacenter IPs.")

    raise RuntimeError(f"Could not extract media from URL: {last_error[:150] or 'No compatible media streams found'}")

def download_youtube_tracks(tracks, save_dir, is_playlist=False, playlist_name=None):
    downloaded_files = []
    download_info = []
    total_tracks = len(tracks)

    os.makedirs(save_dir, exist_ok=True)
    print(f"📁 Download directory confirmed: {save_dir}")

    python_bin = get_python_binary()

    for i, track in enumerate(tracks):
        print("-" * 50)
        print(f"Processing track {i+1}/{total_tracks}: {track.get('artist')} - {track.get('name')}")
        
        video_id = track.get('videoId')
        target_url = track.get('webpage_url') or track.get('url') or ''
        
        # Check if this is a YouTube track
        is_youtube = ("youtube.com" in str(target_url)) or ("youtu.be" in str(target_url)) or (track.get('source') == 'youtube') or (video_id and len(str(video_id)) == 11 and not target_url)

        if not video_id and not target_url:
            print(f"Skipping '{track.get('name')}' - No videoId or media URL found.")
            continue

        sanitized_name = re.sub(r'[\\/*?:"<>|]', "", track.get('name', 'Unknown Track'))
        if track.get('artist') and track.get('artist') != 'Unknown Artist':
            sanitized_artist = re.sub(r'[\\/*?:"<>|]', "", track.get('artist'))
            final_filename = f"{sanitized_artist} - {sanitized_name}.mp3"
        else:
            final_filename = f"{sanitized_name}.mp3"

        final_filepath = os.path.join(save_dir, final_filename)
        temp_id = video_id or track.get('id') or 'media'
        temp_output_template = os.path.join(save_dir, f"{temp_id}.%(ext)s")

        if is_youtube:
            # ORIGINAL UNTOUCHED YOUTUBE COMMAND
            youtube_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else target_url
            cookie_path = get_cookie_file_path()
            command = [
                python_bin, "-m", "yt_dlp",
                "--extractor-args", "youtube:player_client=android",
                "--remote-components", "ejs:github",
                "--no-playlist",
                "-f", "18/140/ba/b/bestaudio/best",
                "-x", "--audio-format", "mp3",
                "--no-cache-dir",
                "--output", temp_output_template,
                youtube_url,
            ]
        else:
            # Check if we already have direct CDN stream URL (e.g. from TikTok or direct embed)
            direct_stream = track.get('url') or track.get('streamUrl')
            if direct_stream and ("tiktokcdn" in direct_stream or "cdninstagram" in direct_stream or direct_stream.endswith(('.mp3', '.mp4', '.m4a'))):
                import urllib.request
                try:
                    print(f"Direct stream download: {direct_stream[:60]}...")
                    req = urllib.request.Request(direct_stream, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
                    })
                    out_ext = track.get('ext', 'mp3')
                    out_file = os.path.join(save_dir, f"{sanitized_artist + ' - ' if track.get('artist') and track.get('artist') != 'Unknown Artist' else ''}{sanitized_name}.{out_ext}")
                    with urllib.request.urlopen(req, timeout=30) as resp, open(out_file, 'wb') as f_out:
                        shutil.copyfileobj(resp, f_out)
                    if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                        downloaded_files.append(out_file)
                        if not is_playlist:
                            folder_name = os.path.basename(save_dir)
                            file_size_mb = round(os.path.getsize(out_file) / (1024 * 1024), 2)
                            temp_download_url = create_temp_link_for_file(out_file, folder_name, os.path.basename(out_file))
                            if temp_download_url:
                                download_info.append({
                                    'name': os.path.basename(out_file),
                                    'size': file_size_mb,
                                    'download_url': temp_download_url,
                                    'path': os.path.join(folder_name, os.path.basename(out_file))
                                })
                                add_to_recent_downloads(os.path.basename(out_file), temp_download_url, file_size_mb)
                        continue
                except Exception as direct_err:
                    print(f"Direct stream download note: {direct_err}")

            # UNIVERSAL MULTI-PLATFORM COMMAND (Instagram, TikTok, Twitter/X, SoundCloud, Vimeo, etc.)
            media_url = target_url or f"https://www.youtube.com/watch?v={video_id}"
            command = [
                python_bin, "-m", "yt_dlp",
                "--no-playlist",
                "-f", "bestaudio/best",
                "-x", "--audio-format", "mp3",
                "--no-cache-dir",
                "--output", temp_output_template,
                media_url,
            ]
            ig_cookie = os.path.join(BASE_DIR, "ig_cookies.txt")
            if os.path.exists(ig_cookie) and os.path.getsize(ig_cookie) > 0:
                command.extend(["--cookies", ig_cookie])

        try:
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                encoding='utf-8', 
                errors='ignore', 
                bufsize=1
            )

            captured_destination = ""
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line: 
                    continue
                if '[ExtractAudio] Destination:' in line or 'Destination:' in line:
                    captured_destination = line.split('Destination: ')[-1].strip()

            process.wait()

            if process.returncode != 0:
                print(f"Primary audio download exit code {process.returncode}, attempting raw fallback...")
                if is_youtube:
                    fallback_cmd = [
                        python_bin, "-m", "yt_dlp",
                        "--extractor-args", "youtube:player_client=android",
                        "--remote-components", "ejs:github",
                        "--no-playlist",
                        "-f", "18/140/ba/b/bestaudio/best",
                        "--no-cache-dir",
                        "--output", temp_output_template,
                        youtube_url,
                    ]
                else:
                    fallback_cmd = [
                        python_bin, "-m", "yt_dlp",
                        "--no-playlist",
                        "-f", "b/ba/best",
                        "--no-cache-dir",
                        "--output", temp_output_template,
                        media_url,
                    ]
                    ig_cookie = os.path.join(BASE_DIR, "ig_cookies.txt")
                    if os.path.exists(ig_cookie) and os.path.getsize(ig_cookie) > 0:
                        fallback_cmd.extend(["--cookies", ig_cookie])

                f_process = subprocess.run(fallback_cmd, capture_output=True, text=True)
                if f_process.returncode != 0:
                    print(f"Fallback download failed: {f_process.stderr}")
                    continue

            file_found = False
            
            if captured_destination and os.path.exists(captured_destination):
                if captured_destination != final_filepath:
                    shutil.move(captured_destination, final_filepath)
                
                if os.path.exists(final_filepath) and os.path.getsize(final_filepath) > 0:
                    downloaded_files.append(final_filepath)
                    file_found = True
                    print(f"✅ Successfully processed: {final_filename}")
            
            elif os.path.exists(final_filepath) and os.path.getsize(final_filepath) > 0:
                downloaded_files.append(final_filepath)
                file_found = True
            
            elif not file_found:
                for filename in os.listdir(save_dir):
                    if filename.startswith(str(temp_id)):
                        source_path = os.path.join(save_dir, filename)
                        if os.path.exists(source_path) and os.path.getsize(source_path) > 0:
                            if not filename.endswith('.mp3'):
                                new_target = os.path.join(save_dir, f"{os.path.splitext(final_filename)[0]}{os.path.splitext(filename)[1]}")
                                shutil.move(source_path, new_target)
                                final_filepath = new_target
                                final_filename = os.path.basename(new_target)
                            else:
                                shutil.move(source_path, final_filepath)
                            
                            downloaded_files.append(final_filepath)
                            file_found = True
                            print(f"✅ Successfully processed via wildcard: {final_filename}")
                            break

            if not is_playlist and file_found:
                folder_name = os.path.basename(save_dir)
                file_size_mb = round(os.path.getsize(final_filepath) / (1024 * 1024), 2)
                temp_download_url = create_temp_link_for_file(final_filepath, folder_name, final_filename)
                
                if temp_download_url:
                    download_info.append({
                        'name': final_filename,
                        'size': file_size_mb,
                        'download_url': temp_download_url,
                        'path': os.path.join(folder_name, final_filename)
                    })
                    add_to_recent_downloads(final_filename, temp_download_url, file_size_mb)

        except Exception as e:
            print(f"An unexpected error occurred while downloading {track.get('name')}.\nError: {e}")
            continue

        if i < total_tracks - 1:
            time.sleep(random.uniform(1, 3))
    
    if is_playlist and downloaded_files and playlist_name:
        valid_files = [f for f in downloaded_files if os.path.exists(f) and os.path.getsize(f) > 0]
        if not valid_files:
            return [], "No valid files found for playlist archiving.", []
        
        sanitized_playlist_name = re.sub(r'[\\/*?:"<>|]', "", playlist_name)
        archives = create_split_archives(save_dir, f"Playlist - {sanitized_playlist_name}")
        
        if not archives:
            return downloaded_files, f"Successfully processed {len(downloaded_files)} track(s) but archiving failed.", []
        
        archive_info = []
        for archive in archives:
            archive_path = os.path.join(save_dir, archive)
            if os.path.exists(archive_path) and os.path.getsize(archive_path) > 0:
                archive_size_mb = round(os.path.getsize(archive_path) / (1024 * 1024), 2)
                temp_archive_url = create_temp_link_for_file(archive_path, os.path.basename(save_dir), archive)
                
                if temp_archive_url:
                    archive_info.append({
                        'filename': archive,
                        'download_url': temp_archive_url,
                        'size_mb': archive_size_mb,
                        'type': 'archive'
                    })
                    add_to_recent_downloads(archive, temp_archive_url, archive_size_mb)
        
        if archive_info:
            safe_delete_files(save_dir, '.mp3')
            return downloaded_files, f"Successfully processed {len(downloaded_files)} track(s) and created {len(archives)} archive(s).", archive_info
        else:
            return downloaded_files, f"Successfully processed {len(downloaded_files)} track(s) but archiving failed.", []
    
    if not downloaded_files:
        return [], "No audio files were successfully downloaded.", []
        
    return downloaded_files, f"Successfully processed {len(downloaded_files)} track(s).", download_info
