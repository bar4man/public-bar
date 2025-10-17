from flask import Flask, jsonify
import logging
import os
import threading
import time
from datetime import datetime
import sys

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot_instance = None
startup_time = datetime.utcnow()
web_server_started = False

def set_bot(bot):
    global bot_instance
    bot_instance = bot
    logger.info("Bot instance registered with web server")

def get_uptime():
    uptime = datetime.utcnow() - startup_time
    return str(uptime).split('.')[0]

@app.route('/')
def home():
    return jsonify({
        "status": "online", 
        "service": "discord-bot",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": get_uptime(),
        "web_server": "running"
    })

@app.route('/health')
def health():
    try:
        bot_ready = bot_instance and bot_instance.is_ready()
        return jsonify({
            "status": "healthy" if bot_ready else "starting",
            "bot_ready": bot_ready,
            "web_server": "running",
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/up')
def up():
    return "OK"

@app.route('/ping')
def ping():
    return "pong"

@app.route('/status')
def status():
    return jsonify({
        "bot_ready": bot_instance and bot_instance.is_ready(),
        "web_server": "running",
        "uptime": get_uptime(),
        "timestamp": datetime.utcnow().isoformat()
    })

def run():
    """Run the web server with production settings for Render."""
    global web_server_started
    try:
        # Use Render's PORT environment variable
        port = int(os.getenv('PORT', 8080))
        host = '0.0.0.0'
        
        logger.info(f"🚀 Starting web server on {host}:{port}")
        
        # Try using a production WSGI server first
        try:
            from waitress import serve
            logger.info("✅ Using Waitress production server on port %s", port)
            web_server_started = True
            serve(app, host=host, port=port, threads=4, _quiet=True)
        except ImportError:
            # Fallback to Flask development server
            logger.warning("⚠️ Waitress not available, using Flask development server")
            web_server_started = True
            app.run(host=host, port=port, debug=False, use_reloader=False)
        
    except Exception as e:
        logger.error(f"❌ Web server error: {e}")
        web_server_started = False

def keep_alive():
    """Start the keep-alive web server in a separate thread."""
    try:
        # Start web server immediately in a separate thread
        t = threading.Thread(target=run, name="WebServer", daemon=True)
        t.start()
        
        # Give it a moment to start
        time.sleep(2)
        
        if web_server_started:
            logger.info("✅ Keep-alive web server started successfully")
            return True
        else:
            logger.warning("❌ Web server thread started but may not be running")
            return True  # Still return True since thread started
            
    except Exception as e:
        logger.error(f"❌ Failed to start keep-alive: {e}")
        return False

# For Render health checks - simple immediate response
@app.route('/render-health')
def render_health():
    """Ultra-fast health check for Render's internal monitoring"""
    return "READY"

if __name__ == "__main__":
    print("Starting web server for testing...")
    keep_alive()
    # Keep the main thread alive
    while True:
        time.sleep(1)
