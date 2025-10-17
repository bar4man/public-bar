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
        "uptime": get_uptime()
    })

@app.route('/health')
def health():
    try:
        bot_ready = bot_instance and bot_instance.is_ready()
        return jsonify({
            "status": "healthy" if bot_ready else "starting",
            "bot_ready": bot_ready,
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

# Render-specific: Must bind to the port they provide
def run():
    try:
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting web server on port {port}")
        
        # Use production WSGI server
        try:
            from waitress import serve
            logger.info("Using Waitress production server")
            serve(app, host='0.0.0.0', port=port, threads=4)
        except ImportError:
            # Fallback
            logger.info("Using Flask development server")
            app.run(host='0.0.0.0', port=port, debug=False)
            
    except Exception as e:
        logger.error(f"Web server failed: {e}")

def keep_alive():
    try:
        # Start in a separate thread
        t = threading.Thread(target=run, daemon=True)
        t.start()
        logger.info("Web server thread started")
        return True
    except Exception as e:
        logger.error(f"Failed to start web server: {e}")
        return False

if __name__ == "__main__":
    keep_alive()
    while True:
        time.sleep(1)
