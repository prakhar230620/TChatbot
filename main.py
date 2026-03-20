from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from Chatbot.Chatbot import ChatbotHandler, setup_chatbot_routes
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


def validate_user(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.args.get('user_id')
        if not user_id:
            return redirect('https://toolminesai.in/login')

        user = User.get_user_by_email(user_id)
        if not user:
            return redirect('https://toolminesai.in/login')

        session['user_id'] = user.email
        session['name'] = user.name
        session['is_admin'] = user.is_admin

        return f(*args, **kwargs)

    return decorated_function

# Setup routes
setup_chatbot_routes(app)

wsgi_app = app.wsgi_app

if __name__ == '__main__':
    # Local development wrapper fallback
    app.run(debug=False, port=8001)