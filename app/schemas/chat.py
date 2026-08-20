from datetime import date
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    job_description: str
    source_id: str
    company_name: Optional[str] = "Unknown"
    position: Optional[str] = None
    programme: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None