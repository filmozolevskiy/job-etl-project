"""
Profile Management UI

Simple Flask web interface for managing job profiles.
"""

from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return "Profile Management UI - Coming Soon"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

