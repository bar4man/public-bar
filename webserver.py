from flask import Flask, jsonify
import logging
import os
import threading
import time
from datetime import datetime, timedelta
import psutil
import sys

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store bot instance globally
bot_instance = None

# Store startup time for uptime calculation
startup_time = datetime.utcnow()

# Health check statistics
health_stats = {
    'total_checks': 0,
    'last_check': None,
    'last_success': None
}

def set_bot(bot):
    """Set the bot instance for status monitoring."""
    global bot_instance
    bot_instance = bot
    logger.info("Bot instance registered with web server")

def get_uptime():
    """Calculate and format uptime."""
    uptime = datetime.utcnow() - startup_time
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"

def get_memory_usage():
    """Get memory usage in MB."""
    try:
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        return round(memory_mb, 2)
    except:
        return "Unknown"

def get_system_stats():
    """Get system statistics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            'cpu_percent': round(cpu_percent, 1),
            'memory_percent': round(memory.percent, 1),
            'memory_used_mb': round(memory.used / 1024 / 1024, 1),
            'disk_percent': round(disk.percent, 1),
            'disk_free_gb': round(disk.free / 1024 / 1024 / 1024, 1)
        }
    except Exception as e:
        logger.warning(f"Could not get system stats: {e}")
        return {}

@app.route('/')
def home():
    """Main status page."""
    return jsonify({
        "status": "online",
        "service": "discord-bot",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": get_uptime(),
        "endpoints": {
            "/health": "Basic health check",
            "/detailed": "Detailed status information",
            "/stats": "Bot statistics",
            "/system": "System information",
            "/ping": "Simple ping response",
            "/up": "Ultra-lightweight health check"
        }
    })

@app.route('/health')
def health():
    """Health check endpoint for monitoring services."""
    start_time = time.time()
    health_stats['total_checks'] += 1
    health_stats['last_check'] = datetime.utcnow().isoformat()
    
    try:
        # Basic health checks
        bot_ready = bot_instance and bot_instance.is_ready()
        bot_status = "connected" if bot_ready else "disconnected"
        
        response_time = round((time.time() - start_time) * 1000, 2)
        health_stats['last_success'] = datetime.utcnow().isoformat()
        
        return jsonify({
            "status": "healthy",
            "bot_status": bot_status,
            "response_time_ms": response_time,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/up')
def up():
    """Ultra-lightweight endpoint for basic uptime checks."""
    return "OK"

@app.route('/detailed')
def detailed_status():
    """Detailed status information for advanced monitoring."""
    try:
        bot_ready = bot_instance and bot_instance.is_ready()
        guild_count = len(bot_instance.guilds) if bot_ready else 0
        latency_ms = round(bot_instance.latency * 1000, 2) if bot_ready and bot_instance.latency else None
        
        # Calculate user count (approximate)
        user_count = 0
        if bot_ready:
            for guild in bot_instance.guilds:
                user_count += guild.member_count
        
        return jsonify({
            "status": "operational",
            "bot": {
                "ready": bot_ready,
                "guild_count": guild_count,
                "user_count": user_count,
                "latency_ms": latency_ms,
                "uptime": get_uptime()
            },
            "system": {
                "memory_usage_mb": get_memory_usage(),
                "python_version": sys.version.split()[0],
                "platform": sys.platform
            },
            "monitoring": {
                "total_health_checks": health_stats['total_checks'],
                "last_successful_check": health_stats['last_success'],
                "startup_time": startup_time.isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Detailed status failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/stats')
def bot_stats():
    """Bot-specific statistics."""
    try:
        bot_ready = bot_instance and bot_instance.is_ready()
        
        if not bot_ready:
            return jsonify({
                "status": "bot_not_ready",
                "message": "Bot is not connected to Discord",
                "timestamp": datetime.utcnow().isoformat()
            }), 503
        
        # Guild information
        guilds_info = []
        for guild in list(bot_instance.guilds)[:10]:  # Limit to first 10 guilds
            guilds_info.append({
                "name": guild.name,
                "id": str(guild.id),
                "member_count": guild.member_count,
                "created_at": guild.created_at.isoformat() if guild.created_at else None
            })
        
        # Command statistics (simplified)
        total_commands = len(bot_instance.commands) if hasattr(bot_instance, 'commands') else 0
        
        return jsonify({
            "bot": {
                "username": str(bot_instance.user),
                "id": str(bot_instance.user.id),
                "guild_count": len(bot_instance.guilds),
                "total_commands": total_commands,
                "latency_ms": round(bot_instance.latency * 1000, 2)
            },
            "guilds_sample": guilds_info,
            "uptime": get_uptime(),
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/system')
def system_info():
    """System resource information."""
    try:
        system_stats = get_system_stats()
        
        return jsonify({
            "status": "operational",
            "resources": system_stats,
            "process": {
                "memory_usage_mb": get_memory_usage(),
                "uptime": get_uptime(),
                "python_version": sys.version.split()[0]
            },
            "environment": {
                "render": os.getenv('RENDER', 'false').lower() == 'true',
                "keep_alive": os.getenv('KEEP_ALIVE', 'true').lower() == 'true',
                "port": os.getenv('PORT', '8080')
            },
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"System info failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }), 500

@app.route('/ping')
def ping():
    """Simple ping endpoint."""
    return "pong"

@app.route('/version')
def version():
    """Version information."""
    return jsonify({
        "service": "discord-bot",
        "version": "1.0.0",
        "flask_version": "2.3.3",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "operational"
    })

@app.route('/monitoring')
def monitoring_status():
    """Monitoring-specific endpoint with lightweight response."""
    health_stats['total_checks'] += 1
    health_stats['last_check'] = datetime.utcnow().isoformat()
    
    try:
        bot_ready = bot_instance and bot_instance.is_ready()
        
        if bot_ready:
            health_stats['last_success'] = datetime.utcnow().isoformat()
            return jsonify({"status": "ok", "bot": "connected"})
        else:
            return jsonify({"status": "warning", "bot": "disconnected"}), 503
            
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# Add CORS headers for better compatibility
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": [
            "/", "/health", "/up", "/detailed", "/stats", 
            "/system", "/ping", "/version", "/monitoring"
        ],
        "timestamp": datetime.utcnow().isoformat()
    }), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({
        "error": "Method not allowed",
        "timestamp": datetime.utcnow().isoformat()
    }), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "error": "Internal server error",
        "timestamp": datetime.utcnow().isoformat()
    }), 500

def run():
    """Run the web server with production settings for Render."""
    try:
        # Use Render's PORT environment variable
        port = int(os.getenv('PORT', 8080))
        host = '0.0.0.0'
        
        logger.info(f"Starting web server on {host}:{port}")
        
        # Try using a production WSGI server first
        try:
            from waitress import serve
            logger.info("Using Waitress production server")
            serve(app, host=host, port=port, threads=4)
        except ImportError:
            # Fallback to Flask development server
            logger.warning("Waitress not available, using Flask development server")
            app.run(host=host, port=port, debug=False, threaded=True)
        
    except Exception as e:
        logger.error(f"Web server error: {e}")

def keep_alive():
    """Start the keep-alive web server in a separate thread."""
    try:
        # Small delay to ensure bot is initialized first
        time.sleep(2)
        
        # Set more descriptive thread name
        t = threading.Thread(target=run, name="WebServer-Thread", daemon=True)
        t.start()
        logger.info("Keep-alive web server started successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to start keep-alive: {e}")
        return False

# For local testing
if __name__ == "__main__":
    print("Starting web server for testing...")
    keep_alive()
    # Keep the main thread alive
    while True:
        time.sleep(1)
