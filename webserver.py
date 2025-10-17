from flask import Flask, jsonify
import logging
import os
import threading
from datetime import datetime

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    """Main health check endpoint"""
    return jsonify({
        "status": "online",
        "service": "discord-bot",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": "active"
    })

@app.route('/health')
def health():
    """Health check endpoint for monitoring services"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return "pong"

@app.route('/status')
def status():
    """Detailed status information"""
    return jsonify({
        "status": "operational",
        "memory_usage": f"{os.sys.getsizeof([]) / 1024 / 1024:.2f} MB",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": os.getenv('RENDER', 'development')
    })

def run():
    """Run the web server"""
    try:
        port = int(os.getenv('PORT', 8080))
        host = os.getenv('HOST', '0.0.0.0')
        
        logger.info(f"Starting web server on {host}:{port}")
        app.run(host=host, port=port, debug=False, threaded=True)
        
    except Exception as e:
        logger.error(f"Web server error: {e}")

def keep_alive():
    """Start the keep-alive web server in a separate thread"""
    try:
        # Set more descriptive thread name
        t = threading.Thread(target=run, name="WebServer-Thread", daemon=True)
        t.start()
        logger.info("Keep-alive web server started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start keep-alive: {e}")
        return False

# Optional: Add error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # For local testing
    keep_alive()
