# ytstream-headless ⚡

> High-Speed, Lightweight Universal Media & Audio Extraction Headless REST API. Powered by Python, Flask, and yt-dlp.

Designed specifically for headless deployments, microservices, mobile applications, and decoupled frontends (Next.js, React, Cloudflare Pages, Svelte, Vue) with **Universal CORS enabled**.

---

## ⭐️ Key Features

- **Headless & Microservice Ready**: Zero HTML template overhead, minimal memory footprint (~50 MB per worker), optimized for resource-constrained hosting (e.g. CloudLinux LVE, cPanel, Docker, VPS).
- **Universal CORS Out-of-the-Box**: Ready to be consumed by any client application, mobile app, or external web frontend.
- **100% Keyless Spotify Extraction**: Automatically parses Spotify tracks, albums, and playlists via native embed state parsing and resolves matching YouTube audio streams without requiring Spotify developer API keys.
- **YouTube SABR & Cipher Bypass**: Employs optimized `mweb` player clients and GitHub-based challenge solvers for reliable, high-speed audio resolution.
- **Multi-Platform Support**: Direct CDN audio/video extraction for:
  - **YouTube**: Videos, Shorts, Playlists, and Smart Radio Mixes.
  - **Spotify**: 100% keyless tracks, albums, and playlists.
  - **TikTok**: Keyless direct progressive MP4/MP3 extraction (no cookies or `curl-cffi` needed).
  - **Instagram**: Public Reels and Posts (with optional `ig_cookies.txt` support).
  - **SoundCloud, Bandcamp, Twitter / X, Reddit, Vimeo**.
- **Dual Stream Modes**:
  - **Mode A (Direct CDN URLs - Recommended)**: Returns high-speed CDN URLs directly to the client audio player, releasing server connections in < 1 second.
  - **Mode B (Audio Proxy)**: Pipes audio chunks via `/stream/play` with full HTTP `Range` header support for seeking.

---

## 🚀 API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | API status, health overview, and endpoints index (JSON) |
| `GET` | `/get?ytl={url}&quality={preset}&limit=5` | Extract stream metadata and playable CDN URLs |
| `GET` | `/stream/:id?quality={preset}` | Direct stream metadata for YouTube video ID or Spotify URL |
| `GET` | `/stream/play?id={cacheId}` | Proxied audio stream with Range header support |
| `GET` | `/api/search/youtube?query={q}&limit=10` | Search YouTube for tracks and music videos |
| `GET` | `/api/search/spotify?query={q}&type=track` | Search Spotify for tracks, albums, and playlists |
| `GET` | `/api/spotify/playlist/:id` | Resolve Spotify playlist items into YouTube video IDs |
| `POST` | `/download` | Trigger track or playlist audio download (`{"url": "..."}`) |
| `GET` | `/api/downloads` | List stored MP3 files and ZIP archives |
| `GET` | `/docs.md` | Token-efficient raw Markdown specifications |
| `GET` | `/health` | Health check and monitoring endpoint |

---

## 💻 Quick Start & Usage Examples

### 1. Extract Stream (Spotify Track or YouTube Video)
```bash
curl -s "https://ytapi.pgwiz.qzz.io/get?ytl=https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT&quality=audio"
```

### 2. Search Tracks on YouTube
```bash
curl -s "https://ytapi.pgwiz.qzz.io/api/search/youtube?query=Daft+Punk&limit=5"
```

### 3. Fetch Raw Markdown Documentation for AI Agents
```bash
curl -s "https://ytapi.pgwiz.qzz.io/docs.md"
```

---

## 🛠 Local Development

```bash
git clone https://github.com/pgwiz/ytstream-headless.git
cd ytstream-headless
python3 -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r req.txt
python application.py
```

The API will be available at `http://localhost:5000`.

---

## ☁️ Cloud Platform Deployment & Runner Procedures (Render, Railway, Fly.io)

### 1. Environment Configuration
Copy `.env.example` to `.env` or configure variables in your PaaS dashboard:
```bash
cp .env.example .env
```
Key variables:
- `PORT`: Automatically set by Render/Railway (e.g. `10000`).
- `HOST`: Set to `0.0.0.0` for containerized environments.
- `YTDLP_COOKIES`: Raw Netscape cookie content string (for serverless environments without persistent files).
- `TELEGRAM_TOKEN`: Optional Telegram bot token to run the extractor as an interactive bot.

### 2. Render Web Service (Uvicorn Procedure)
- **Build Command**: `pip install -r req.txt`
- **Start Command (Uvicorn ASGI)**:
  ```bash
  uvicorn application:asgi_app --host 0.0.0.0 --port $PORT
  ```
  *(Alternatively: `gunicorn application:app --bind 0.0.0.0:$PORT`)*

### 3. Universal Platform Runner (`python -m bot.main`)
To run on platforms like Render where you may want Web API only, Telegram Bot worker, or both combined in a single service:
- **Start Command**:
  ```bash
  python -m bot.main
  ```
- **Behavior Matrix**:
  - `PORT` set, `TELEGRAM_TOKEN` unset: Starts Uvicorn API on `$PORT`.
  - `PORT` unset, `TELEGRAM_TOKEN` set: Starts Telegram Bot polling worker.
  - Both `PORT` and `TELEGRAM_TOKEN` set: Runs Uvicorn Web Server in background thread (fulfilling Render's port binding health-check) and Telegram Bot worker in main thread.

---

## 📜 License

MIT License. Open source and free for personal, developer, and research use.

