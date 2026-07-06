import json
from app.client import groq_client
from app.config import EXPLANATION_MODEL

def generate_batch_course_explanations(courses: list[dict], technical_requirements: str) -> dict:
    courses_summary = [
        {
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "learning_outcomes": (c.get("learning_outcomes") or "")[:300]
        }
        for c in courses
    ]

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

    try:
        return json.loads(response.choices[0].message.content.strip())
    except Exception:
        return {}