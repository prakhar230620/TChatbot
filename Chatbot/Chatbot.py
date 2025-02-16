from groq import Groq
from flask import render_template, request, jsonify, session
from datetime import datetime
import os
from dotenv import load_dotenv
from utils.api_key_manager import APIKeyManager
from utils.auth_middleware import validate_session

load_dotenv()


class ChatSession:
    def __init__(self):
        self.messages = []
        self.last_interaction = datetime.now()


class ChatbotHandler:
    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.client = None
        self.sessions = {}  # Temporary session storage
        self.system_prompt = {
            "role": "system",
            "content": """
        You are an advanced AI assistant designed to converse like ChatGPT or Claude 3.5 Sonnet. Your key characteristics include:

        1. Adaptive communication style: Adjust your tone and complexity based on the user's level of understanding and preferences.
        2. Deep comprehension: Demonstrate a nuanced understanding of context, subtext, and user intent.
        3. Engaging conversationalist: Foster meaningful dialogues through thoughtful responses and follow-up questions.
        4. Multilingual proficiency: Seamlessly communicate in the user's preferred language.
        5. Intellectual curiosity: Show genuine interest in learning from user interactions.
        6. Creative problem-solving: Offer innovative solutions and perspectives on complex issues.
        7. Emotional intelligence: Recognize and respond appropriately to user emotions and social cues.
        8. Ethical reasoning: Provide guidance while considering moral implications and societal impact.
        9. Clear and concise communication: Always provide context-relevant, clear, and very short answers to maintain efficiency and effectiveness.

        Tailor your responses to enhance the user's understanding and overall experience. Be concise yet thorough, balancing depth with accessibility. Encourage critical thinking and explore topics from multiple angles when appropriate.

        Always maintain a respectful, empathetic, and professional demeanor while engaging users in stimulating and insightful conversations.
        """
        }

    def create_session(self, session_id):
        """Create a new chat session"""
        session = ChatSession()
        session.messages.append(self.system_prompt)
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id):
        """Get or create a session"""
        return self.sessions.get(session_id)

    def get_groq_response(self, messages):
        while True:
            try:
                api_key = self.api_key_manager.get_api_key()
                self.client = Groq(api_key=api_key)

                # Make the API call
                chat_completion = self.client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                    max_tokens=500,
                    temperature=0.8
                )

                return chat_completion.choices[0].message.content

            except Exception as e:
                error_message = str(e).lower()
                if "rate limit" in error_message or "quota exceeded" in error_message:
                    # Mark the current key as having an error
                    self.api_key_manager.mark_key_error(api_key)
                    print(f"API key rate limited, trying another key...")
                    continue
                else:
                    # For other errors, raise them
                    raise e

    def process_message(self, message, session_id):
        if not session_id:
            return {"error": "Session expired"}, 401

        if not message:
            return {"error": "No message provided"}, 400

        # Get or create session
        session = self.get_session(session_id)
        if not session:
            session = self.create_session(session_id)

        # Update session timestamp
        session.last_interaction = datetime.now()

        # Add user message to history
        session.messages.append({"role": "user", "content": message})

        try:
            # Get chat completion from Groq
            bot_response = self.get_groq_response(session.messages)

            # Add bot response to history
            session.messages.append({"role": "assistant", "content": bot_response})

            return {
                "response": bot_response,
                "session_active": True
            }

        except Exception as e:
            return {"error": str(e)}, 500

    def cleanup_old_sessions(self):
        """Remove sessions that are older than 30 minutes"""
        current_time = datetime.now()
        for session_id in list(self.sessions.keys()):
            session = self.sessions[session_id]
            if (current_time - session.last_interaction).total_seconds() > 1800:  # 30 minutes
                del self.sessions[session_id]


# Initialize chatbot instance
chatbot = ChatbotHandler()


def setup_chatbot_routes(app):
    """Set up routes for the chatbot with authentication"""

    @app.route('/')
    @validate_session
    def chatbot_page():
        return render_template('chatbot.html')

    @app.route('/api/chat/status')
    @validate_session
    def check_status():
        try:
            return jsonify({"status": "online"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/chat', methods=['POST', 'OPTIONS'])
    @validate_session
    def handle_message():
        if request.method == 'OPTIONS':
            return '', 204

        try:
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "No message provided"}), 400

            session_id = session.get('user_id')  # Use user_id as session_id
            if not session_id:
                return jsonify({"error": "Not authenticated"}), 401

            chatbot = ChatbotHandler()
            result = chatbot.process_message(data['message'], session_id)

            if isinstance(result, tuple):
                return jsonify(result[0]), result[1]

            return jsonify(result)

        except Exception as e:
            print(f"Error in handle_message: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/chat/reset', methods=['POST', 'OPTIONS'])
    @validate_session
    def reset_chat():
        if request.method == 'OPTIONS':
            return '', 204

        try:
            session_id = session.get('user_id')
            chatbot = ChatbotHandler()
            if session_id and session_id in chatbot.sessions:
                del chatbot.sessions[session_id]
            return jsonify({"status": "success", "message": "Chat session reset"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
