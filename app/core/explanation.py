import json
import logging
from groq import RateLimitError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from app.client import groq_client
from app.config import EXPLANATION_MODEL

logger = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s... tối đa 30s
    stop=stop_after_attempt(4),  # thử tối đa 4 lần
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _call_groq_batch_explanations(courses_summary: list[dict], technical_requirements: str) -> str:
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
        model=EXPLANATION_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content.strip()


def generate_batch_course_explanations(courses: list[dict], technical_requirements: str) -> dict:
    courses_summary = [
        {
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "learning_outcomes": (c.get("learning_outcomes") or "")[:300]
        }
        for c in courses
    ]

    try:
        raw_content = _call_groq_batch_explanations(courses_summary, technical_requirements)
    except RateLimitError as e:
        logger.error(f"Groq rate limit exceeded after retries: {e}")
        raise RuntimeError(
            "AI service is currently busy, please try again in a moment."
        ) from e
    except APIStatusError as e:
        logger.error(f"Groq API error: {e}")
        raise RuntimeError("AI service error, please try again.") from e

    try:
        return json.loads(raw_content)
    except Exception:
        logger.error(f"Failed to parse Groq JSON response: {raw_content[:200]}")
        return {}