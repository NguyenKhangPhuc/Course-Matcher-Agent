# Course Matcher Agent API

An AI-powered academic advisor agent built with FastAPI and Supabase Vector Search, designed to map job description technical requirements to university course modules.

## Features & Capabilities
- **Job Description Summarization**: Automatically extracts technical skills, tools, and domain knowledge from job descriptions using LLMs (Groq Cloud/Llama).
- **Semantic Course Matching**: Uses OpenAI Embeddings (`text-embedding-3-small`) and Supabase pgvector cosine similarity search to match technical requirements with university courses.
- **Batch Explanations**: Generates concise, structured academic explanations of why each matched course fits the requirements.
- **SSE Streaming Pipeline**: Leverages Server-Sent Events (SSE) to stream live progress (JD summary -> matched courses -> reasons) to the client.
- **API Rate Limiting**: Protects sensitive route endpoints with a lightweight, IP-based in-memory rate limiter.
- **Robust Environment Variable Validation**: Sanitizes env variables (automatically stripping Windows CRLF carriage returns `\r`) to ensure reliable configuration inside Docker.
- **Caddy Reverse Proxy & Automatic SSL**: Seamlessly integrates with Caddy for production HTTPS certificates.

## Project Structure
- `app/`
  - `client.py`: Supabase, OpenAI, and Groq clients initialization.
  - `config.py`: Environment variable configurations and validation.
  - `main.py`: FastAPI application setup and middleware routing.
  - `core/`
    - `course_search.py`: Supabase vector search logic.
    - `explanation.py`: Groq batch explanation logic.
    - `summarizer.py`: Groq job description summarization.
  - `guard/`
    - `auth.py`: Supabase JWT authentication guard.
    - `rate_limit.py`: In-memory client IP rate limiter.
  - `helper/`
    - `embeddings.py`: OpenAI text embedding helper.
    - `sse.py`: Server-Sent Events chunk formatter.
  - `routers/`
    - `chat.py`: Router for the streaming chat pipeline.
    - `health.py`: App health endpoint.
  - `schemas/`: Pydantic model definitions for requests/responses.
  - `service/`: Streaming orchestration service.
  - `tests/`: Pytest suite for core and guard modules.
- `crawl.py`: Academic guide crawler (crawls Oulu University Peppi Study Guide).
- `Dockerfile`: Production multi-stage Dockerfile running non-root.
- `docker-compose.yml`: Production Docker Compose configuration with Caddy.
- `docker-compose.dev.yml`: Local Docker Compose configuration.
- `Caddyfile`: Reverse proxy and SSL configuration.
- `run.py`: Uvicorn startup entrypoint.

## Logic & Flow
1. **JD Ingestion**: User submits a job description, source ID, and program filters to `/api/chat`.
2. **Authentication**: Supabase JWT is validated in the authorization header.
3. **Rate Limiting**: IP request limit is validated.
4. **Extraction**: The JD is summarized to isolate technical skills.
5. **Embedding & Search**: The summary is embedded and compared with the vector database using a Supabase RPC similarity match.
6. **Explanation**: Matched courses are summarized and matched to requirements using a batch Groq call.
7. **Stream Delivery**: Progress is sent chunk-by-chunk using SSE.

## Tech Stack / Prerequisites
| Technology | Description |
|---|---|
| Python 3.12 | Core programming language |
| FastAPI | High-performance async web framework |
| Supabase | PostgreSQL database, Auth, and Vector search (`pgvector`) |
| OpenAI API | Generating text embeddings (`text-embedding-3-small`) |
| Groq Cloud | LLM inference for JD summarization and course explanations |
| Caddy | Web server for automatic SSL/TLS reverse proxy |
| Docker & Compose | Containerized application deployment |
| Pytest | Automated unit test suite |

## Installation & Setup Instructions

### 1. Local Setup
1. Clone the repository and navigate to the project directory.
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file in the root folder using `.env.example` as a template and fill in your keys:
   ```env
   OPENAI_API_KEY=your_openai_key
   GROQ_API_KEY=your_groq_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_KEY=your_supabase_service_key
   PORT=8000
   ```
5. Run the application:
   ```bash
   python run.py
   ```

### 2. Docker Local Development
1. Run the local development containers:
   ```bash
   docker compose -f docker-compose.dev.yml up -d --build
   ```
2. The API will be available at `http://localhost:8000`.

### 3. Production Deployment
1. Configure Caddyfile with your domain.
2. Build and start containers:
   ```bash
   docker compose up -d --build
   ```
