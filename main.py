from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from flask_cors import CORS
from Chatbot.Chatbot import ChatbotHandler, ChatSession, setup_chatbot_routes
from config.user import User
from config.database import db
from functools import wraps
from utils.auth_middleware import validate_session


app = Flask(__name__)
app.config['SECRET_KEY'] = '14701c4d1e765347259951b561146a45'

# Configure CORS properly
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5000", "http://localhost:3000"],
        "supports_credentials": True
    }
})

# Initialize socketio with CORS settings
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:5000", "http://localhost:3000"])


if __name__ == '__main__':
    setup_chatbot_routes(app)
    app.run(host="localhost", port=3000, debug=True)