import asyncio
from datetime import date
from functools import partial
from typing import AsyncGenerator, Optional

from app.helper.sse import sse
from app.core.summarizer import summarize_jd
from app.core.course_search import search_courses
from app.core.explanation import generate_batch_course_explanations


def _build_course_payload(course: dict, explanation: str) -> dict:
    return {
        "id": course.get("id", ""),
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
        "start_date": str(course.get("start_date")) if course.get("start_date") else None,
        "end_date": str(course.get("end_date")) if course.get("end_date") else None,
        "enrollment_start_date": str(course.get("enrollment_start_date")) if course.get("enrollment_start_date") else None,
        "enrollment_end_date": str(course.get("enrollment_end_date")) if course.get("enrollment_end_date") else None,
        "similarity": round(course.get("similarity", 0) * 100, 1),
        "explanation": explanation,
    }


async def run_streaming_agent(
    job_description: str,
    source_id: str,
    company_name: str,
    programme: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> AsyncGenerator[str, None]:
    loop = asyncio.get_event_loop()

    try:
        technical_requirements = await loop.run_in_executor(
            None, summarize_jd, job_description
        )
        yield sse("requirements", technical_requirements)

        courses = await loop.run_in_executor(
            None,
            partial(
                search_courses,
                technical_requirements,
                source_id,
                programme,
                start_date=start_date,
                end_date=end_date,
            ),
        )

        if not courses:
            yield sse("done", {"total": 0, "summary": "No matching courses found."})
            return

        explanations_dict = await loop.run_in_executor(
            None, generate_batch_course_explanations, courses, technical_requirements
        )

        total = 0
        for course in courses:
            explanation = explanations_dict.get(course.get("id", ""), "No explanation provided.")
            yield sse("course", _build_course_payload(course, explanation))
            total += 1

        yield sse("done", {
            "total": total,
            "summary": f"Found {total} matching courses for {company_name}."
        })
    except Exception as e:
        yield sse("error", str(e))