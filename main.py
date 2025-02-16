from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from flask_cors import CORS
from Chatbot.Chatbot import ChatbotHandler, ChatSession, setup_chatbot_routes
from config.user import User
from config.database import db
from functools import wraps


def validate_user():
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.args.get('user_id')
        if not user_id:
            return redirect('http://localhost:5000/login')
            
        user = User.get_user_by_email(user_id)
        if not user:
            return redirect('http://localhost:5000/login')
            
        session['user_id'] = user.email
        session['name'] = user.name
        session['is_admin'] = user.is_admin
        
        return f(*args, **kwargs)
    return decorated_function

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = '14701c4d1e765347259951b561146a45'

# Initialize socketio
socketio = SocketIO(app)

# Apply authentication to all chatbot routes
def setup_authenticated_routes(app):
    @app.before_request
    def check_auth():
        # Skip authentication for OPTIONS requests
        if request.method == 'OPTIONS':
            return
            
        # List of paths that don't need authentication
        public_paths = ['/login']
        
        if request.path not in public_paths:
            user_id = session.get('user_id')
            if not user_id:
                user_id = request.args.get('user_id')
                if not user_id:
                    return redirect('http://localhost:5000/login')
                    
                user = User.get_user_by_email(user_id)
                if not user:
                    return redirect('http://localhost:5000/login')
                    
                session['user_id'] = user.email
                session['name'] = user.name
                session['is_admin'] = user.is_admin

# Set up routes with authentication
setup_authenticated_routes(app)
setup_chatbot_routes(app)

if __name__ == '__main__':
    app.run(host="localhost", port=3000, debug=True)


