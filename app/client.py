from supabase.client import create_client, Client
from openai import OpenAI
from groq import Groq
from langchain_groq import ChatGroq

from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, GROQ_API_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)