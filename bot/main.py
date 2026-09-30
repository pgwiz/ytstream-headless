#!/usr/bin/env python3
"""
Stream Extractor Platform Universal Entry Point (e.g. Render, Railway, Fly.io, Heroku)
Supports:
1. Uvicorn ASGI Web Service on $PORT
2. Telegram Bot Polling Worker via $TELEGRAM_TOKEN
3. Dual-Mode: Web Service (binds $PORT) + Telegram Bot polling in single process
"""

import os
import sys
import threading
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logging.basicConfig(
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("bot.main")

def start_web_server(host: str, port: int):
    """Start Uvicorn or Flask ASGI/WSGI web server for platform port binding."""
    logger.info(f"🌐 Starting web API server on {host}:{port}...")
    try:
        import uvicorn
        from application import asgi_app
        uvicorn.run(asgi_app, host=host, port=port, log_level="info")
    except Exception as e:
        logger.warning(f"Uvicorn start failed ({e}), falling back to Flask WSGI runner...")
        from application import app
        app.run(host=host, port=port, debug=False)

def run_telegram_bot(token: str):
    """Run Telegram Bot polling loop for stream extraction."""
    logger.info("🤖 Starting Telegram Bot worker...")
    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    except ImportError:
        logger.error(
            "❌ python-telegram-bot is not installed. "
            "Install it via `pip install python-telegram-bot` to enable bot capabilities."
        )
        return

    from services.ytdlp_service import YTDLPService
    from services.spotify_service import SpotifyKeylessService

    ytdl = YTDLPService()
    spotify = SpotifyKeylessService()

    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = (
            "🎵 *Welcome to Stream Extractor Bot!* 🚀\n\n"
            "Send any supported media link to extract audio/video streams:\n"
            "• *Spotify* (Tracks, Albums, Playlists - 100% Keyless)\n"
            "• *YouTube* (Videos, Music, Shorts)\n"
            "• *TikTok & Instagram* (Reels & Direct CDN)\n\n"
            "Just paste the link below!"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

    async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip() if update.message and update.message.text else ""
        if not text.startswith("http://") and not text.startswith("https://"):
            await update.message.reply_text("Please provide a valid HTTP/HTTPS media link.")
            return

        status_msg = await update.message.reply_text("🔍 Resolving stream and metadata...")
        try:
            # Check Spotify
            if "spotify.com" in text:
                meta = spotify.extract_metadata(text)
                if not meta or not meta.get("query"):
                    await status_msg.edit_text("❌ Could not resolve Spotify track metadata.")
                    return
                stream_data = ytdl.extract_stream_url(f"ytsearch:{meta['query']}")
            else:
                stream_data = ytdl.extract_stream_url(text)

            if not stream_data or not stream_data.get("url"):
                await status_msg.edit_text("❌ Failed to extract stream for this link.")
                return

            title = stream_data.get("title", "Audio Stream")
            duration = stream_data.get("duration", "N/A")
            stream_url = stream_data.get("url")

            reply_text = (
                f"🎶 *{title}*\n"
                f"⏱ Duration: {duration}\n\n"
                f"🔗 Direct Stream URL resolved!"
            )
            keyboard = [[InlineKeyboardButton("🎧 Stream Audio", url=stream_url)]]
            await status_msg.edit_text(
                reply_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as err:
            logger.error(f"Error handling URL {text}: {err}")
            await status_msg.edit_text(f"⚠️ Extraction error: {str(err)[:100]}")

    app_bot = Application.builder().token(token).build()
    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    logger.info("✅ Telegram Bot polling initialized.")
    app_bot.run_polling(drop_pending_updates=True)

def main():
    """Universal platform entry point (e.g. Render, Railway, Fly.io)."""
    # Auto-load .env if python-dotenv is present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    port_env = os.environ.get("PORT")
    host = os.environ.get("HOST", "0.0.0.0")
    telegram_token = os.environ.get("TELEGRAM_TOKEN") or os.environ.get("BOT_TOKEN")

    logger.info("==================================================")
    logger.info("   Stream Extractor - Platform Starter Service   ")
    logger.info("==================================================")
    logger.info(f"• PORT: {port_env or 'Not Set (Worker Mode)'}")
    logger.info(f"• TELEGRAM_TOKEN: {'Configured' if telegram_token else 'Not Set'}")

    # Case 1: Both Web Port and Telegram Token are set (Render Web Service with Bot)
    if port_env and telegram_token:
        port = int(port_env)
        logger.info(f"🚀 Dual-Mode Active: Launching Web Server on {host}:{port} and Telegram Bot worker...")
        server_thread = threading.Thread(
            target=start_web_server,
            args=(host, port),
            daemon=True
        )
        server_thread.start()
        run_telegram_bot(telegram_token)

    # Case 2: Only Web Port is set (Render Web Service API only)
    elif port_env:
        port = int(port_env)
        logger.info(f"🚀 Web Service Mode: Launching Uvicorn API on {host}:{port}...")
        start_web_server(host, port)

    # Case 3: Only Telegram Token is set (Render Background Worker)
    elif telegram_token:
        logger.info("🚀 Background Worker Mode: Launching Telegram Bot...")
        run_telegram_bot(telegram_token)

    # Case 4: Default local run
    else:
        default_port = 5000
        logger.info(f"ℹ️ No PORT or TELEGRAM_TOKEN specified. Starting default server on {host}:{default_port}...")
        start_web_server(host, default_port)

if __name__ == "__main__":
    main()
