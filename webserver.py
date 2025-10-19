from flask import Flask
from threading import Thread
import logging
import os

logger = logging.getLogger('discord_bot')

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/health')
def health():
    return {"status": "online"}, 200

def run():
    try:
        port = int(os.getenv('PORT', '8080'))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Webserver error: {e}")

def keep_alive():
    t = Thread(target=run)
    t.start()
    logger.info("Webserver started on port 8080")
