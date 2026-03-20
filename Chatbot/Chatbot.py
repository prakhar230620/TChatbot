from groq import Groq
from flask import render_template, request, jsonify, session
from datetime import datetime
import os
import uuid
from dotenv import load_dotenv
from utils.api_key_manager import APIKeyManager
from utils.auth_middleware import validate_session
from config.database import db

load_dotenv()


class ChatbotHandler:
    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.client = None
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

    def create_session(self, user_id, first_message):
        """Create a new chat session in database"""
        chat_id = str(uuid.uuid4())
        title = first_message[:30] + '...' if len(first_message) > 30 else first_message
        session_data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "title": title,
            "messages": [],
            "summary": "",
            "last_interaction": datetime.now()
        }
        db.chatsessions.insert_one(session_data)
        return session_data

    def get_session(self, chat_id, user_id):
        """Get session from database"""
        return db.chatsessions.find_one({"chat_id": chat_id, "user_id": user_id})

    def summarize_history(self, messages, current_summary=""):
        """Summarize conversation history using Groq"""
        try:
            prompt = "Please summarize the following conversation concisely. Focus on the main topics discussed and any important details or facts about the user.\n\n"
            if current_summary:
                prompt += f"Previous Summary: {current_summary}\n\n"
            prompt += "Recent Messages to include in summary:\n"
            for msg in messages:
                if msg["role"] != "system":
                    prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
            
            summary_messages = [
                {"role": "system", "content": "You are a helpful assistant that summarizes conversations accurately and concisely. Keep the summary under 150 words."},
                {"role": "user", "content": prompt}
            ]
            return self.get_groq_response(summary_messages)
        except Exception as e:
            print(f"Error summarizing: {e}")
            return current_summary

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
                    self.api_key_manager.mark_key_error(api_key)
                    print(f"API key rate limited, trying another key...")
                    continue
                else:
                    raise e

    def process_message(self, message, user_id, chat_id=None):
        if not user_id:
            return {"error": "Session expired"}, 401

        if not message:
            return {"error": "No message provided"}, 400

        session_data = None
        if chat_id:
            session_data = self.get_session(chat_id, user_id)
            
        if not session_data:
            # If no chat_id passed, or invalid chat_id, create new
            session_data = self.create_session(user_id, message)
            chat_id = session_data["chat_id"]

        MAX_MESSAGES = 12
        messages = session_data.get("messages", [])
        summary = session_data.get("summary", "")

        messages.append({"role": "user", "content": message})

        api_messages = []
        api_messages.append(self.system_prompt)
        
        if summary:
            api_messages.append({"role": "system", "content": f"Here is a summary of previous context in this conversation: {summary}"})
        
        api_messages.extend(messages)

        try:
            bot_response = self.get_groq_response(api_messages)

            messages.append({"role": "assistant", "content": bot_response})

            if len(messages) > MAX_MESSAGES:
                num_to_summarize = len(messages) - (MAX_MESSAGES // 2)
                messages_to_summarize = messages[:num_to_summarize]
                new_summary = self.summarize_history(messages_to_summarize, summary)
                messages = messages[num_to_summarize:]
                summary = new_summary

            db.chatsessions.update_one(
                {"chat_id": chat_id},
                {"$set": {
                    "messages": messages,
                    "summary": summary,
                    "last_interaction": datetime.now()
                }}
            )

            return {
                "response": bot_response,
                "chat_id": chat_id,
                "session_active": True
            }

        except Exception as e:
            return {"error": str(e)}, 500


def setup_chatbot_routes(app):
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

    @app.route('/api/chat/list', methods=['GET'])
    @validate_session
    def list_chats():
        try:
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({"error": "Not authenticated"}), 401
            
            chats = list(db.chatsessions.find(
                {"user_id": user_id}, 
                {"_id": 0, "chat_id": 1, "title": 1, "last_interaction": 1}
            ).sort("last_interaction", -1))
            
            return jsonify({"chats": chats})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/chat/history', methods=['GET'])
    @validate_session
    def get_chat_history():
        """Get history for a specific chat"""
        try:
            user_id = session.get('user_id')
            chat_id = request.args.get('chat_id')
            
            if not user_id:
                return jsonify({"error": "Not authenticated"}), 401
            if not chat_id:
                return jsonify({"error": "No chat_id provided"}), 400

            chatbot = ChatbotHandler()
            session_data = chatbot.get_session(chat_id, user_id)
            
            if not session_data or not session_data.get('messages'):
                return jsonify({"messages": []})
            
            chat_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in session_data["messages"]
                if msg["role"] != "system"
            ]
            
            return jsonify({"messages": chat_history})
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/chat/delete', methods=['POST'])
    @validate_session
    def delete_chat():
        try:
            user_id = session.get('user_id')
            data = request.get_json()
            chat_id = data.get('chat_id') if data else None
            
            if user_id and chat_id:
                db.chatsessions.delete_one({"chat_id": chat_id, "user_id": user_id})
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/chat', methods=['POST', 'OPTIONS'])
    @validate_session
    def handle_message():
        if request.method == 'OPTIONS':
            return '', 204

        try:
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "No message provided"}), 400

            user_id = session.get('user_id')
            if not user_id:
                return jsonify({"error": "Not authenticated"}), 401

            chat_id = data.get('chat_id')
            chatbot = ChatbotHandler()
            result = chatbot.process_message(data['message'], user_id, chat_id)

            if isinstance(result, tuple):
                return jsonify(result[0]), result[1]

            return jsonify(result)

        except Exception as e:
            print(f"Error in handle_message: {str(e)}")
            return jsonify({"error": str(e)}), 500
