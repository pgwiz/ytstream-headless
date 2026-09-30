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

## 📜 License

MIT License. Open source and free for personal, developer, and research use.
