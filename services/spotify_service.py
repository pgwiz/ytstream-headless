import httpx
import asyncio
import base64
import time
import re
import json
import threading
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_API_BASE
from services.ytdlp_service import search_youtube

spotify_access_token = None
spotify_token_expiry = 0
spotify_lock = threading.Lock()

async def get_spotify_access_token():
    """Fetch or return cached Spotify API Client Credentials access token (if configured)."""
    global spotify_access_token, spotify_token_expiry
    with spotify_lock:
        if spotify_access_token and time.time() < spotify_token_expiry:
            return spotify_access_token
    
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    
    try:
        auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("https://accounts.spotify.com/api/token", headers=headers, data=data)
            if resp.status_code == 200:
                res_data = resp.json()
                with spotify_lock:
                    spotify_access_token = res_data.get('access_token')
                    spotify_token_expiry = time.time() + res_data.get('expires_in', 3600) - 60
                return spotify_access_token
    except Exception as e:
        print(f"[Spotify Auth Error]: {e}")
    return None

async def scrape_spotify_embed(spotify_url: str):
    """
    Direct keyless extraction of Spotify metadata (Track, Album, Playlist)
    using Spotify's public embed page (__NEXT_DATA__).
    No Spotify API keys, no cookies, and no third-party gateways required.
    """
    match = re.search(r'(track|album|playlist)/([a-zA-Z0-9]+)', spotify_url)
    if not match:
        return None
    
    media_type, media_id = match.groups()
    embed_url = f"https://open.spotify.com/embed/{media_type}/{media_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(embed_url, headers=headers)
            if resp.status_code != 200:
                return None
            
            json_match = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">(.*?)</script>', resp.text, re.DOTALL)
            if not json_match:
                return None
            
            data = json.loads(json_match.group(1))
            entity = data.get('props', {}).get('pageProps', {}).get('state', {}).get('data', {}).get('entity', {})
            
            if media_type == 'track':
                title = entity.get('name') or entity.get('title') or 'Unknown Track'
                artists = ', '.join([a.get('name', '') for a in entity.get('artists', [])]) or 'Unknown Artist'
                cover = entity.get('coverArt', {}).get('sources', [{}])[0].get('url') if entity.get('coverArt') else f"https://open.spotify.com/embed/track/{media_id}"
                dur_ms = entity.get('duration', 0)
                d_sec = dur_ms // 1000 if dur_ms else 0
                d_str = f"{d_sec // 60}:{d_sec % 60:02d}" if d_sec else "3:30"
                preview = entity.get('audioPreview', {}).get('url')
                
                return {
                    'type': 'track',
                    'id': media_id,
                    'title': title,
                    'name': title,
                    'artist': artists,
                    'playlist_name': None,
                    'is_playlist': False,
                    'total_tracks': 1,
                    'tracks': [{
                        'name': title,
                        'title': title,
                        'artist': artists,
                        'duration': d_str,
                        'duration_string': d_str,
                        'thumbnail': cover,
                        'preview_mp3': preview,
                        'spotify_id': media_id,
                        'source': 'spotify'
                    }]
                }
            else:
                title = entity.get('name') or entity.get('title') or ('Spotify Album' if media_type == 'album' else 'Spotify Playlist')
                track_list = entity.get('trackList', [])
                cover = entity.get('coverArt', {}).get('sources', [{}])[0].get('url') if entity.get('coverArt') else ''
                
                tracks = []
                for t in track_list:
                    dur_ms = t.get('duration', 0)
                    d_sec = dur_ms // 1000 if dur_ms else 0
                    d_str = f"{d_sec // 60}:{d_sec % 60:02d}" if d_sec else "3:30"
                    tracks.append({
                        'name': t.get('title', 'Unknown Track'),
                        'title': t.get('title', 'Unknown Track'),
                        'artist': t.get('subtitle') or 'Unknown Artist',
                        'duration': d_str,
                        'duration_string': d_str,
                        'thumbnail': cover,
                        'preview_mp3': t.get('audioPreview', {}).get('url'),
                        'spotify_id': t.get('id', ''),
                        'source': 'spotify'
                    })
                
                return {
                    'type': media_type,
                    'id': media_id,
                    'title': title,
                    'name': title,
                    'playlist_name': title,
                    'is_playlist': True,
                    'total_tracks': len(tracks),
                    'tracks': tracks
                }
    except Exception as e:
        print(f"[Spotify Embed Scrape Error]: {e}")
        return None

async def resolve_track_to_youtube(track: dict) -> dict:
    """Resolve a single track dict to a YouTube videoId and watch URL."""
    if track.get('videoId'):
        return track
    
    query = f"{track.get('artist', '')} - {track.get('name') or track.get('title', '')}".strip(' -')
    try:
        yt_results = await search_youtube(query, limit=1)
        if yt_results:
            top = yt_results[0]
            v_id = top.get('videoId')
            track['videoId'] = v_id
            track['url'] = f"https://www.youtube.com/watch?v={v_id}"
            if not track.get('thumbnail') or 'spotify' in track.get('thumbnail', ''):
                track['thumbnail'] = top.get('thumbnail') or f"https://img.youtube.com/vi/{v_id}/mqdefault.jpg"
            if track.get('duration') in ['Unknown', '--:--', '']:
                track['duration'] = top.get('duration', '3:30')
                track['duration_string'] = top.get('duration', '3:30')
    except Exception as e:
        print(f"Error resolving YouTube match for {query}: {e}")
    return track

async def fetch_spotify_tracks(spotify_url: str, limit: int = None, resolve_youtube: bool = True):
    """
    Fetch track data from Spotify with automated YouTube video ID resolution.
    1. First uses native keyless embed parsing (Zero API keys, zero cookies).
    2. Resolves each track to a YouTube videoId via YouTube search.
    3. Falls back to gateway only if embed scraping fails.
    """
    # 1. Primary: Native Embed Scraper
    embed_data = await scrape_spotify_embed(spotify_url)
    if embed_data and embed_data.get('tracks'):
        raw_tracks = embed_data['tracks']
        if limit:
            raw_tracks = raw_tracks[:limit]
            
        if resolve_youtube:
            # Resolve YouTube video IDs
            tasks = [resolve_track_to_youtube(t) for t in raw_tracks]
            resolved_tracks = await asyncio.gather(*tasks)
            embed_data['tracks'] = resolved_tracks
            embed_data['valid_tracks'] = len([t for t in resolved_tracks if t.get('videoId')])
        else:
            embed_data['tracks'] = raw_tracks
            embed_data['valid_tracks'] = len(raw_tracks)
            
        return embed_data

    # 2. Secondary Fallback: Gateway API (if configured)
    if SPOTIFY_API_BASE:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                api_url = f"{SPOTIFY_API_BASE}/"
                params = {'spotifyUrl': spotify_url}
                response = await client.get(api_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    tracks = data.get('tracks', [])
                    playlist_name = data.get('playName', None)
                    is_playlist = data.get('isPlaylist', False)
                    
                    converted_tracks = []
                    for track in (tracks[:limit] if limit else tracks):
                        video_id = track.get('videoId')
                        if video_id:
                            converted_tracks.append({
                                'videoId': video_id,
                                'name': track.get('name', 'Unknown Title'),
                                'title': track.get('name', 'Unknown Title'),
                                'artist': track.get('artist', 'Unknown Artist'),
                                'thumbnail': track.get('thumbnail', f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"),
                                'duration': '3:30',
                                'duration_string': '3:30',
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'spotify_id': track.get('id', ''),
                                'source': 'spotify'
                            })
                    
                    return {
                        'tracks': converted_tracks,
                        'playlist_name': playlist_name,
                        'title': playlist_name or 'Spotify Tracks',
                        'is_playlist': is_playlist,
                        'total_tracks': len(tracks),
                        'valid_tracks': len(converted_tracks)
                    }
        except Exception as e:
            print(f"[Spotify Fallback Gateway Error]: {e}")

    return None

async def get_spotify_playlist(playlist_id: str, limit: int = 25, resolve_youtube: bool = True):
    """Fetch Spotify playlist track list by ID (Keyless Embed first)."""
    spotify_url = f"https://open.spotify.com/playlist/{playlist_id}"
    data = await fetch_spotify_tracks(spotify_url, limit=limit, resolve_youtube=resolve_youtube)
    if data:
        return {
            "status": "success",
            "id": playlist_id,
            "name": data.get('playlist_name') or data.get('title') or 'Spotify Playlist',
            "title": data.get('playlist_name') or data.get('title') or 'Spotify Playlist',
            "description": "Keyless Spotify Playlist Extractor",
            "owner": "Spotify",
            "thumbnail": data['tracks'][0].get('thumbnail') if data.get('tracks') else '',
            "totalTracks": data.get('total_tracks', len(data.get('tracks', []))),
            "tracks": data.get('tracks', [])
        }
    return None

async def search_spotify(query: str, search_type: str = 'track', limit: int = 10):
    """
    Search Spotify for tracks, albums, playlists.
    Uses official credentials if present, otherwise returns structured YouTube results formatted for Spotify playback.
    """
    token = await get_spotify_access_token()
    if token:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            params = {"q": query, "type": search_type, "limit": str(limit)}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("https://api.spotify.com/v1/search", headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    type_key = search_type + 's'
                    raw_items = data.get(type_key, {}).get('items', [])
                    results = []
                    for item in raw_items:
                        if search_type == 'track':
                            results.append({
                                "id": item.get('id'),
                                "name": item.get('name'),
                                "title": item.get('name'),
                                "artist": ", ".join([a.get('name') for a in item.get('artists', [])]),
                                "album": item.get('album', {}).get('name', 'Unknown'),
                                "duration": f"{item.get('duration_ms', 0)//60000}:{(item.get('duration_ms', 0)//1000)%60:02d}",
                                "thumbnail": item.get('album', {}).get('images', [{}])[0].get('url', ''),
                                "spotifyUrl": item.get('external_urls', {}).get('spotify', ''),
                                "previewUrl": item.get('preview_url')
                            })
                        elif search_type == 'album':
                            results.append({
                                "id": item.get('id'),
                                "name": item.get('name'),
                                "title": item.get('name'),
                                "artist": ", ".join([a.get('name') for a in item.get('artists', [])]),
                                "totalTracks": item.get('total_tracks'),
                                "releaseDate": item.get('release_date'),
                                "thumbnail": item.get('images', [{}])[0].get('url', ''),
                                "spotifyUrl": item.get('external_urls', {}).get('spotify', '')
                            })
                        elif search_type == 'playlist':
                            results.append({
                                "id": item.get('id'),
                                "name": item.get('name'),
                                "title": item.get('name'),
                                "description": item.get('description', ''),
                                "owner": item.get('owner', {}).get('display_name', 'Unknown'),
                                "totalTracks": item.get('tracks', {}).get('total', 0),
                                "thumbnail": item.get('images', [{}])[0].get('url', ''),
                                "spotifyUrl": item.get('external_urls', {}).get('spotify', '')
                            })
                    return {
                        "query": query,
                        "type": search_type,
                        "limit": limit,
                        "total_results": len(results),
                        "results": results
                    }
        except Exception as e:
            print(f"[Spotify Direct Search Error]: {e}")

    # Fallback to smart YouTube music search formatted for Spotify client
    try:
        yt_items = await search_youtube(f"{query} audio", limit=limit)
        results = []
        for item in yt_items:
            results.append({
                "id": item.get('videoId'),
                "videoId": item.get('videoId'),
                "name": item.get('name'),
                "title": item.get('title'),
                "artist": item.get('artist'),
                "album": "YouTube Music Stream",
                "duration": item.get('duration', '3:30'),
                "thumbnail": item.get('thumbnail'),
                "url": item.get('url'),
                "source": "youtube_matched"
            })
        return {
            "query": query,
            "type": search_type,
            "limit": limit,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        print(f"[Spotify Universal Search Fallback Error]: {e}")

    return {"query": query, "type": search_type, "limit": limit, "total_results": 0, "results": []}
