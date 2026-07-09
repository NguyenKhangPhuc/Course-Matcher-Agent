import os
from dotenv import load_dotenv

load_dotenv()

def get_env_stripped(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is not None:
        # Strip trailing/leading whitespaces and carriage returns (\r)
        return val.strip()
    return default

SUPABASE_URL = get_env_stripped("SUPABASE_URL")
SUPABASE_SERVICE_KEY = get_env_stripped("SUPABASE_SERVICE_KEY")
OPENAI_API_KEY = get_env_stripped("OPENAI_API_KEY")
GROQ_API_KEY = get_env_stripped("GROQ_API_KEY")

SUMMARIZE_MODEL = get_env_stripped("SUMMARIZE_MODEL", "llama-3.3-70b-versatile")
EXPLANATION_MODEL = get_env_stripped("EXPLANATION_MODEL", "llama-3.1-8b-instant")
EMBEDDING_MODEL = get_env_stripped("EMBEDDING_MODEL", "text-embedding-3-small")

MATCH_COUNT = int(get_env_stripped("MATCH_COUNT", "9"))
MATCH_THRESHOLD = float(get_env_stripped("MATCH_THRESHOLD", "0"))

ALLOWED_ORIGINS = [orig.strip() for orig in get_env_stripped("ALLOWED_ORIGINS", "*").split(",")]
PORT = int(get_env_stripped("PORT", "8000"))