from app.client import openai_client
from app.config import EMBEDDING_MODEL

def embed_text(text: str) -> list[float]:
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding