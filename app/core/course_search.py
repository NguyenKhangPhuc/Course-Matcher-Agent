from datetime import date
from typing import Optional
from app.client import supabase
from app.helper.embeddings import embed_text
from app.config import MATCH_COUNT, MATCH_THRESHOLD

def search_courses(
    technical_requirements: str,
    source_id: str,
    programme: str,
    limit: int = MATCH_COUNT,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> list[dict]:
    query_vector = embed_text(technical_requirements)
    vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

    result = supabase.rpc("match_courses", {
        "query_embedding": vector_str,
        "source_id": source_id,
        "match_count": limit,
        "match_threshold": MATCH_THRESHOLD,
        "filter_programme": programme,
        "start_filter": str(start_date) if start_date else None,
        "end_filter": str(end_date) if end_date else None
    }).execute()

    return result.data or []