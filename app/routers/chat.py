from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.guard.auth import get_current_user
from app.service.streaming_pipeline import run_streaming_agent

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat")
async def chat(request: ChatRequest, current_user=Depends(get_current_user)):
    return StreamingResponse(
        run_streaming_agent(
            job_description=request.job_description,
            source_id=request.source_id,
            company_name=request.company_name or "Unknown",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )