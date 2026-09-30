import base64
import re
import httpx
from flask import Response, jsonify
from config import url_cache, cache_lock, cache_stream_url

def proxy_audio_stream(cache_id, encoded_url, request_headers):
    """Proxy direct audio bytes to client with Range header support and automatic fallback extraction."""
    stream_url = None
    stored_video_id = None

    if cache_id:
        with cache_lock:
            item = url_cache.get(cache_id)
            if item:
                stream_url = item[0]
                if len(item) > 2:
                    stored_video_id = item[2]
        
        # Dynamic Fallback: If cache_id is missing from in-memory cache (e.g. Passenger worker restart)
        if not stream_url:
            try:
                from services.ytdlp_service import extract_media_info
                target_url = None
                
                # YouTube video IDs are EXACTLY 11 characters long
                if cache_id and re.match(r'^[\w-]{11}$', cache_id):
                    target_url = f"https://www.youtube.com/watch?v={cache_id}"
                elif stored_video_id and re.match(r'^[\w-]{11}$', stored_video_id):
                    target_url = f"https://www.youtube.com/watch?v={stored_video_id}"
                elif encoded_url:
                    target_url = encoded_url

                if target_url:
                    info = extract_media_info(target_url)
                    if info and info.get('tracks') and len(info['tracks']) > 0:
                        stream_url = info['tracks'][0].get('url')
                        if stream_url:
                            cache_stream_url(stream_url, video_id=cache_id if re.match(r'^[\w-]{11}$', cache_id) else None)
            except Exception as e:
                print(f"Fallback proxy stream resolution failed: {e}")

    elif encoded_url:
        try:
            stream_url = base64.b64decode(encoded_url).decode('utf-8')
        except Exception:
            stream_url = encoded_url

    if not stream_url:
        return jsonify({"error": "Missing or invalid stream ID or URL parameter."}), 400

    req_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.youtube.com/'
    }
    if request_headers.get('Range'):
        req_headers['Range'] = request_headers.get('Range')

    try:
        client = httpx.Client(timeout=35.0, follow_redirects=True)
        upstream_resp = client.send(
            client.build_request("GET", stream_url, headers=req_headers),
            stream=True
        )

        def generate():
            try:
                for chunk in upstream_resp.iter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                upstream_resp.close()
                client.close()

        res_headers = {}
        for h in ['Content-Type', 'Content-Length', 'Accept-Ranges', 'Content-Range']:
            if h in upstream_resp.headers:
                res_headers[h] = upstream_resp.headers[h]

        res_headers['Access-Control-Allow-Origin'] = '*'
        res_headers['Cache-Control'] = 'public, max-age=3600'
        res_headers['X-Accel-Buffering'] = 'no'

        return Response(
            generate(),
            status=upstream_resp.status_code,
            headers=res_headers
        )
    except Exception as e:
        return jsonify({"error": f"Proxy stream failed: {str(e)}"}), 500
