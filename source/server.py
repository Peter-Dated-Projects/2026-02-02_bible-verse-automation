"""
Flask server for Repl.it keep-alive functionality.
"""
from flask import Flask
import threading

app = Flask(__name__)

@app.route('/')
def home():
    """Root endpoint for keep-alive pings."""
    return "Bot is alive", 200

def run_server():
    """Run Flask server in background thread."""
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

def start_server():
    """Start Flask server in a separate thread."""
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("Flask server started on port 8080")
