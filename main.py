"""
Course Matcher Agent — Streaming Version
-----------------------------------------
Changes from previous version:
- Groq llama-3.3-70b-instant replaces GPT-4o inside summarize tool (faster)
- search_matching_courses now generates a per-course explanation via Groq
- /api/chat streams each course as an SSE JSON chunk as soon as it is ready
- Frontend receives: { type: "requirements", data: "..." }
                     { type: "course", data: { ...course, explanation: "..." } }
                     { type: "done", data: { summary: "...", total: N } }
                     { type: "error", data: "..." }
"""

import os
import json
import asyncio
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from supabase.client import create_client, Client
from openai import OpenAI
from groq import Groq

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

load_dotenv()

# =====================================================================
# CLIENTS
# =====================================================================

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Groq client for fast summarization + explanation (used inside tools)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Agent model — also Groq for speed
agent_model = ChatGroq(
    model="llama-3.3-70b-versatile",   # versatile handles tool use better than instant
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
)

# =====================================================================
# STREAMING HELPERS
# =====================================================================

def sse(event_type: str, data) -> str:
    """Format a single Server-Sent Event JSON chunk."""
    return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"


# =====================================================================
# CORE LOGIC (called directly in the streaming generator, not via agent)
# =====================================================================

def summarize_jd(job_description: str) -> str:
    """
    Use Groq llama-3.3-70b-instant to extract only technical requirements
    from a raw job description. Returns a concise technical summary string.
    """
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": f"""Extract ONLY the technical skills, tools, frameworks, 
programming languages, and domain knowledge from this job description.

Ignore: salary, location, company culture, soft skills, benefits.

Return a single concise paragraph (max 120 words). No preamble, no headers.

Job Description:
{job_description}"""
            }
        ],
        max_tokens=300,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def generate_batch_course_explanations(courses: list[dict], technical_requirements: str) -> dict:
    """
    Gom cụm toàn bộ khóa học và yêu cầu Groq trả về JSON chứa giải thích theo ID.
    """
    # Tạo một danh sách thu gọn gồm ID và thông tin cốt lõi để tiết kiệm Token context
    courses_summary = []
    for c in courses:
        courses_summary.append({
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "learning_outcomes": (c.get('learning_outcomes') or '')[:300]
        })

    prompt = f"""You are an academic advisor. Analyze the following job requirements and the list of university courses.
For EACH course, provide a 1-2 sentence explanation of why it matches the job requirements.

Job Requirements:
{technical_requirements}

Courses List (JSON format):
{json.dumps(courses_summary)}

CRITICAL: You must return a valid JSON object where the keys are the course IDs and the values are the 1-2 sentence explanations. 
Do not include any markdown formatting, no ```json, no preamble. Just the raw JSON object.
Format Example:
{{
  "id_of_course_1": "Explanation for course 1...",
  "id_of_course_2": "Explanation for course 2..."
}}"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        # Kích hoạt JSON mode để Groq bắt buộc phải trả về format JSON hợp lệ
        response_format={"type": "json_object"} 
    )
    
    try:
        return json.loads(response.choices[0].message.content.strip())
    except Exception:
        # Fallback nếu parse lỗi
        return {}

def embed_text(text: str) -> list[float]:
    """Embed a string using OpenAI text-embedding-3-small."""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def search_courses(technical_requirements: str, source_id: str, limit: int = 9) -> list[dict]:
    """
    Embed the technical requirements and query Supabase pgvector.
    Returns raw course rows (without explanation yet).
    """
    query_vector = embed_text(technical_requirements)
    vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

    result = supabase.rpc("match_courses", {
        "query_embedding": vector_str,
        "source_id": source_id,
        "match_count": limit,
        "match_threshold": 0,
    }).execute()

    return result.data or []


# =====================================================================
# STREAMING GENERATOR
# =====================================================================

async def run_streaming_agent(
    job_description: str,
    source_id: str,
    company_name: str,
) -> AsyncGenerator[str, None]:
    """
    Full pipeline as an async generator — yields SSE chunks:

    1. Summarize JD → yield { type: "requirements", data: "..." }
    2. Embed summary → search Supabase
    3. For each course → generate explanation → yield { type: "course", data: {...} }
    4. Yield { type: "done", data: { total: N } }
    """
    loop = asyncio.get_event_loop()

    try:
        # ── Step 1: Summarize JD ──────────────────────────────────────
        technical_requirements = await loop.run_in_executor(
            None, summarize_jd, job_description
        )
        yield sse("requirements", technical_requirements)

        # ── Step 2: Semantic search ───────────────────────────────────
        courses = await loop.run_in_executor(
            None, search_courses, technical_requirements, source_id
        )

        if not courses:
            yield sse("done", {"total": 0, "summary": "No matching courses found."})
            return

        # ── Step 3: Gọi Batch Groq lấy toàn bộ giải thích cùng lúc ─────
        explanations_dict = await loop.run_in_executor(
            None, generate_batch_course_explanations, courses, technical_requirements
        )

        # ── Step 4: Backend tự update giải thích vào từng course ────────
        final_courses = []
        for course in courses:
            course_id = course.get("id", "")
            # Lấy giải thích từ Groq dựa theo ID, nếu không có thì để chuỗi rỗng
            explanation = explanations_dict.get(course_id, "No explanation provided.")
            
            course_payload = {
                "id": course_id,
                "code": course.get("code", ""),
                "name": course.get("name", ""),
                "title": course.get("title", ""),
                "programme": course.get("programme", ""),
                "degree_type": course.get("degree_type", ""),
                "study_option": course.get("study_option", ""),
                "credits": course.get("credits", ""),
                "description": course.get("description", ""),
                "learning_outcomes": course.get("learning_outcomes", ""),
                "content": course.get("content", ""),
                "prerequisites": course.get("prerequisites", ""),
                "assessment": course.get("assessment", ""),
                "instructor": course.get("instructor", ""),
                "url": course.get("url", ""),
                "timing": course.get("timing", {}),
                "similarity": round(course.get("similarity", 0) * 100, 1),
                "explanation": explanation,   # ← Đã được thêm trực tiếp ở Backend
            }
            yield sse("course", course_payload)

        # Stream CẢ MẢNG KHÓA HỌC HOÀN CHỈNH về Frontend một lần duy nhất
        # yield sse("courses_list", final_courses)

        # ── Step 5: Done ──────────────────────────────────────────────
        yield sse("done", {
            "total": len(final_courses), 
            "summary": f"Found {len(final_courses)} matching courses for {company_name}."
        })
    except Exception as e:
        print(str(e))
        yield sse("error", str(e))


# =====================================================================
# FASTAPI APP
# =====================================================================

app = FastAPI(
    title="Course Matcher Agent API — Streaming",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# AUTH
# =====================================================================

async def get_current_user(authorization: str = Header(...)):
    """Verify Supabase JWT token from Next.js Authorization header."""
    try:
        token = authorization.replace("Bearer ", "").strip()
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return user_response.user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

# =====================================================================
# REQUEST MODEL
# =====================================================================

class ChatRequest(BaseModel):
    """Request body for the streaming chat endpoint."""
    job_description: str
    source_id: str
    company_name: Optional[str] = "Unknown"
    position: Optional[str] = None

# =====================================================================
# ENDPOINTS
# =====================================================================

@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
):
    """
    Streaming chat endpoint.

    Returns a text/event-stream response where each chunk is a JSON SSE:
      { type: "requirements", data: "extracted technical summary" }
      { type: "course",       data: { ...course fields, explanation: "..." } }
      { type: "done",         data: { total: N, summary: "..." } }
      { type: "error",        data: "error message" }

    The client should parse each line starting with "data: " as JSON.
    """
    return StreamingResponse(
        run_streaming_agent(
            job_description=request.job_description,
            source_id=request.source_id,
            company_name=request.company_name or "Unknown",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable Nginx buffering
        }
    )


@app.get("/api/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
