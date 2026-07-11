from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest
from app.guard.auth import get_current_user
from app.service.streaming_pipeline import run_streaming_agent
from app.core.limiter import limiter

router = APIRouter(prefix="/api", tags=["chat"])
@router.post("/chat")
@limiter.limit("5/minute;50/day")
async def chat(request: Request,bodyRequest: ChatRequest, current_user=Depends(get_current_user)):
    return StreamingResponse(
        run_streaming_agent(
            job_description=bodyRequest.job_description,
            source_id=bodyRequest.source_id,
            company_name=bodyRequest.company_name or "Unknown",
            programme=bodyRequest.programme
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )