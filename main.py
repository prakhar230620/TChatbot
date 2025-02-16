from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from flask_cors import CORS
from Chatbot.Chatbot import ChatbotHandler, ChatSession, setup_chatbot_routes
from config.user import User
from config.database import db
from functools import wraps
from utils.auth_middleware import validate_session
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = '14701c4d1e765347259951b561146a45'

# Configure CORS properly for production
CORS(app, resources={
    r"/*": {
        "origins": ["*"],  # In production, replace with your actual domain
        "supports_credentials": True
    }
})

# Initialize socketio with CORS settings
socketio = SocketIO(app, cors_allowed_origins="*")  # In production, replace with your actual domain

# Setup routes
setup_chatbot_routes(app)

# For local development
if __name__ == '__main__':
    app.run(debug=False)