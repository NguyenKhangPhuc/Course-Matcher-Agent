import logging
from groq import RateLimitError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.config import SUMMARIZE_MODEL
from app.client import groq_client

logger = logging.getLogger(__name__)

@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s... tối đa 30s
    stop=stop_after_attempt(4),  # thử tối đa 4 lần
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_groq(job_description: str) -> str:
    response = groq_client.chat.completions.create(
        model=SUMMARIZE_MODEL,
        messages=[
            {
                "role": "user",
                "content": f"""Extract ONLY the technical skills, tools, frameworks, 
    programming languages, and domain knowledge from this job description.

    Ignore: salary, location, company culture, soft skills, benefits.

    Return a concise paragraph of approximately 70 to 90 words. No preamble, no headers, no markdown, no bold text, no bullet points, and NO <think> tags or internal monologue. Provide the plain text response directly.

    Job Description:
    {job_description}"""
            }
        ],
        max_tokens=1000,
        temperature=0.2, # Giảm temperature xuống thấp để mô hình tập trung tuyệt đối vào việc tuân thủ lệnh
    )
    return response.choices[0].message.content.strip()


def summarize_jd(job_description: str) -> str:
    try:
        return _call_groq(job_description)
    except RateLimitError as e:
        logger.error(f"Groq rate limit exceeded after retries: {e}")
        raise RuntimeError(
            "AI service is currently busy, please try again in a moment."
        ) from e
    except APIStatusError as e:
        failed_gen = ""
        if hasattr(e, "body") and isinstance(e.body, dict):
            failed_gen = e.body.get("error", {}).get("failed_generation", "")

        logger.error(
            f"Groq API error: status={getattr(e, 'status_code', None)}, message={e}. "
            f"Failed generation: {failed_gen}"
        )
        print(f"\n[Groq API Error] Status: {getattr(e, 'status_code', None)} | Error: {e}")
        if failed_gen:
            print(f"[Groq API Error] Failed generation output from model:\n{failed_gen}\n")
        raise RuntimeError("AI service error, please try again.") from e