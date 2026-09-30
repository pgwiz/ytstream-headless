# Stream Extractor API Specification

High-speed Python/yt-dlp REST API for audio extraction, search, streaming, quality selection, playlist metadata, radio mix generation, downloads, and **100% Keyless Spotify Extraction**.

## Base URL
- Production: `https://ytsp-api.pgwiz.cloud`
- Local: `http://localhost:5000`

---

## Endpoints Summary

### 1. Extract Stream & Track Info (YouTube or Spotify)
- **URL**: `/get`
- **Method**: `GET`
- **Parameters**:
  - `ytl` (string, required): YouTube video/playlist URL, Smart Radio link, or **Spotify URL (track/album/playlist)**.
  - `quality` (string, optional): Format quality preset (`audio`, `audio_high`, `saver`, `360p`, `720p`, `best`). Default: `audio`.
  - `limit` (number, optional): Max tracks to extract for playlists/mixes (default: 5).
- **Features**:
  - Automatically parses Spotify metadata via native embed state with zero API keys.
  - Resolves matching YouTube `videoId` and generates direct playable stream and proxy links.
- **Response**: `200 OK`

---

### 2. Get Video Stream Metadata & Proxy URL
- **URL**: `/stream/:videoId`
- **Method**: `GET`
- **Path Parameter**:
  - `videoId`: Standard 11-char YouTube video ID or full Spotify Track URL (`https://open.spotify.com/track/...`).
- **Query Parameters**:
  - `quality` (string, optional): `audio` (default 128k/360p fallback), `audio_high` (256k AAC/160k Opus), `saver` (64k data saver), `360p`, `720p`, `best`.
- **Response**: `200 OK`
```json
{
  "status": "success",
  "videoId": "dQw4w9WgXcQ",
  "title": "Track Title",
  "uploader": "Artist Name",
  "duration": "3:33",
  "quality": "audio",
  "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
  "proxy_url": "https://ytsp-api.pgwiz.cloud/stream/play?id=cache_id"
}
```

---

### 3. Direct Audio Stream Proxy
- **URL**: `/stream/play`
- **Method**: `GET`
- **Parameters**:
  - `id` (string): Cache ID or 11-char YouTube video ID.
  - `url` (string, optional): Base64 encoded audio stream URL.
- **Headers**: Supports HTTP `Range` headers for seeking (`206 Partial Content`).
- **Response**: Raw MP3/Audio stream bytes (`X-Accel-Buffering: no`).

---

### 4. Extract YouTube Playlist / Album / Mix (Flat Speed)
- **URL**: `/api/youtube/playlist` or `/playlist/:playlist_id`
- **Method**: `GET`
- **Parameters**:
  - `id` / `url` / `playlist_id` (string, required): Playlist ID (`PL...`), Album ID (`OLAK5uy_...`), or Mix ID (`RD...`).
  - `limit` (number, optional): Max tracks to return (default: 15).
- **Response**: `200 OK`

---

### 5. Extract YouTube Smart Radio Mix Recommendations
- **URL**: `/api/youtube/radio/:video_id` or `/api/youtube/radio?id={video_id}`
- **Method**: `GET`
- **Parameters**:
  - `video_id` / `id` (string, required): Seed YouTube video ID.
  - `limit` (number, optional): Max radio recommendations (default: 15).
- **Response**: `200 OK` continuous radio tracks array based on seed video.

---

### 6. Get Spotify Playlist or Album Tracks (Keyless)
- **URL**: `/api/spotify/playlist/:id`
- **Method**: `GET`
- **Parameters**:
  - `id` (string, required): Spotify Playlist ID or Album ID.
  - `limit` (number, optional): Max tracks to return (default: 25).
- **Features**:
  - 100% keyless: Extracts directly from Spotify embed.
  - Automatically resolves each track to a matched YouTube `videoId` for instant streaming & downloading.
- **Response**: `200 OK`

---

### 7. Search Spotify / Music Catalog
- **URL**: `/api/search/spotify`
- **Method**: `GET`
- **Parameters**:
  - `query` (string, required): Search term.
  - `type` (string, optional): `track`, `album`, `playlist`, `artist` (default: `track`).
  - `limit` (number, optional): Max items (default: 10).

---

### 8. Download & Package Audio Tracks (YouTube or Spotify)
- **URL**: `/download`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`
- **Body**:
```json
{
  "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
}
```
- **Features**:
  - Accepts YouTube video/playlist links OR Spotify track/album/playlist links.
  - Resolves Spotify tracks to YouTube `videoId`s and packages MP3s or ZIP archives automatically.
- **Response**: `200 OK` with temporary download URLs.

---

### 9. List Saved Downloads Library
- **URL**: `/api/downloads`
- **Method**: `GET`

---

### 10. Delete Saved Download File
- **URL**: `/api/downloads`
- **Method**: `DELETE`
- **Query Parameters**:
  - `file` (string): Target file path relative to downloads.
  - `clear_all` (boolean, optional): Set `true` to delete all server download files.

---

### 11. Multi-Platform Universal Media Extractor
- **URL**: `/get?ytl={media_url}&quality={preset}` or `/stream/{media_url}?quality={preset}`
- **Method**: `GET`
- **Supported Platforms**:
  - **Bandcamp**: High-quality audio stream and direct MP3 download.
  - **SoundCloud**: Full track metadata and audio stream extraction.
  - **Twitter / X**: Video, GIF, and broadcast stream extraction.
  - **Reddit**: Merged video with audio streams (`v.redd.it`).
  - **Vimeo**: Direct high-resolution progressive streams.
  - **Instagram**: Reels, Posts, IGTV (Conditional on datacenter IPs - see below).
  - **TikTok**: Videos, Soundtracks (Conditional on datacenter IPs - see below).

#### Quality Control Presets:
- `audio` (Default): High-quality progressive audio stream.
- `audio_high`: Highest bitrate audio stream (`bestaudio[abr>=160]`).
- `saver`: Ultra data-saver stream (`worstaudio/worst[height<=360]`).
- `360p`: Low resolution video stream.
- `480p`: Standard definition (SD) stream (`bestvideo[height<=480]`, with seamless fallback to lowest available stream on 720p-only platforms like Instagram).
- `720p`: High definition video stream (`bestvideo[height<=720]+bestaudio`).
- `best`: Maximum available video and audio quality.

---

### 12. Conditional Platforms Guide (Instagram & TikTok on Datacenter IPs)

#### Instagram (⚠️ Conditional)
- **Behavior**: Public Reels and Posts are supported. However, Instagram actively rate-limits and blocks datacenter IP ranges (such as cloud hosting providers and VPS instances) with `HTTP Error 429: Too Many Requests` or redirects to a login wall after a few requests.
- **Automated Fallbacks in the API**:
  1. Primary extraction via `yt-dlp` using clean URL (tracking queries stripped).
  2. Fallback extraction via `b/ba/best` stream selector.
  3. Secondary fallback via direct public embed scraping (`/p/{shortcode}/embed/captioned/`) with desktop browser header simulation.
- **Unlocking Unrestricted Instagram Extraction on Servers**:
  - Export your Instagram session cookies using a browser extension (e.g., *Get cookies.txt LOCALLY* for Chrome/Firefox).
  - Save the cookies file as `ig_cookies.txt` in the root API directory on the server.
  - The API automatically detects `ig_cookies.txt` and passes `--cookies` to bypass all rate limits and login challenges without modifying existing YouTube cookies.

#### TikTok (⚠️ Conditional & Built-in Keyless Bypass)
- **Behavior**: TikTok enforces strict TLS fingerprinting (JA3/JA4) on datacenter IPs. When invoked without browser TLS impersonation, standard scrapers return bot challenge errors (`Unexpected response from webpage request`).
- **Native Keyless Direct Extractor (Built-in)**:
  - The API includes `extract_tiktok_direct` which directly parses watermark-free CDN streams (`play` / `wmplay`) and original MP3 audio without cookies or `curl-cffi`. Works out-of-the-box across all hosting environments (including FreeBSD on Serv00).
- **yt-dlp Fallback Requirements (if used directly)**:
  - Requires `curl-cffi` (`--impersonate chrome`) library.
  - **Linux / Docker / VPS Hosts**: Run `pip install curl-cffi` inside your virtual environment to enable Chrome TLS fingerprint impersonation.
  - **FreeBSD Hosts (e.g. Serv00)**: `curl-cffi` currently only provides precompiled wheels for Linux, macOS, and Windows. The built-in `extract_tiktok_direct` engine bypasses this limitation.

---

### 13. Documentation Formats & AI/LLM Access (Markdown & HTML)

The documentation is accessible in both interactive HTML and token-efficient raw Markdown formats:

| Format / View | URL / Method | Description |
| :--- | :--- | :--- |
| **Interactive HTML** | `GET /docs` (in browser) | Interactive developer playground, endpoint testers, and status cards. |
| **Raw Markdown** | `GET /docs.md` | Full raw Markdown specification for LLMs, code generation, and prompt context. |
| **Raw Markdown (Alias)**| `GET /api/docs.md`, `GET /documentation.md` | Alternate direct paths to raw Markdown documentation. |
| **Markdown Query Param**| `GET /docs?format=md` | Pass `?format=md` or `?format=markdown` to any docs route to receive raw Markdown. |
| **Content Negotiation** | `Accept: text/markdown` | Request `/docs` with a `text/markdown` header to receive Markdown instead of HTML. |
| **Terminal CLI (curl)** | `curl https://ytsp-api.pgwiz.cloud/docs` | Standard `curl` and `wget` requests without an HTML Accept header automatically receive clean raw Markdown. |

