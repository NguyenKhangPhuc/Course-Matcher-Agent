import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SUMMARIZE_MODEL = os.getenv("SUMMARIZE_MODEL", "llama-3.3-70b-versatile")
EXPLANATION_MODEL = os.getenv("EXPLANATION_MODEL", "llama-3.1-8b-instant")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

MATCH_COUNT = int(os.getenv("MATCH_COUNT", 9))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0))

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
PORT = int(os.getenv("PORT", 8000))