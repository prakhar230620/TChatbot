import os
import random
import logging
from typing import Optional
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIKeyManager:
    """
    Stateless API Key Manager for Serverless Functions (e.g., Vercel).
    Since lambda functions don't share in-memory state, we distribute load probabilistically 
    by picking a random key from the active pool and naturally re-retrying upon failures inside Chatbot.py.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIKeyManager, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if not self.initialized:
            self.api_keys = []
            self.load_api_keys()
            self.initialized = True

    def load_api_keys(self):
        """Load API keys from .env.api file"""
        if not os.path.exists('.env.api'):
            logger.warning(".env.api file not found, trying standard environment variables")
        else:
            load_dotenv('.env.api')
            
        self.api_keys = []
        i = 1
        while True:
            key = os.getenv(f'GROQ_API_KEY{i}')
            if not key:
                break
            if key.strip():
                self.api_keys.append(key)
            i += 1
        
        if not self.api_keys:
            # Fallback for general GROQ_API_KEY if numbered ones don't exist
            single_key = os.getenv('GROQ_API_KEY')
            if single_key and single_key.strip():
                self.api_keys.append(single_key)
                
        if not self.api_keys:
            logger.error("No valid GROQ API keys found in the environment!")
        else:
            logger.info(f"Loaded {len(self.api_keys)} API keys for Serverless distribution.")

    def get_api_key(self, exclude_keys: Optional[list] = None) -> str:
        """Get a random available API key, occasionally excluding known temporarily rate-limited ones for the current req"""
        if not self.api_keys:
            self.load_api_keys()
            
        if not self.api_keys:
            raise Exception("No API keys available")
            
        available_keys = self.api_keys
        if exclude_keys:
            available_keys = [k for k in self.api_keys if k not in exclude_keys]
            # If all keys are rate limited, fallback to waiting/picking any to retry
            if not available_keys:
                available_keys = self.api_keys
                
        return random.choice(available_keys)

    def mark_key_error(self, key: str):
        """Stateless architectures handle retries in the request loop."""
        logger.warning("API key returned an error. Request-level loop will rotate.")
        pass
