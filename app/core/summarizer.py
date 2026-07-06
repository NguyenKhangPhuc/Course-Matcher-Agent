from app.client import groq_client
from app.config import SUMMARIZE_MODEL

def summarize_jd(job_description: str) -> str:
    response = groq_client.chat.completions.create(
        model=SUMMARIZE_MODEL,
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