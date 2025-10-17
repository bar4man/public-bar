from flask import Flask
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello from Render!"

@app.route('/up')
def up():
    return "OK"

@app.route('/health')
def health():
    return "Healthy"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
