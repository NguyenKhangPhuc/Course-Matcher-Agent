from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    job_description: str
    source_id: str
    company_name: Optional[str] = "Unknown"
    position: Optional[str] = None
    programme: str