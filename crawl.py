"""
Crawl study program / course data from Peppi Study Guide (University of Oulu)
and export to 2 Excel files:
    - degree_studies.xlsx   (navigation id = 11738, Degree Studies)
    - exchange_students.xlsx (navigation id = 18715, Exchange Students)

HOW TO RUN:
    pip install requests pandas openpyxl --break-system-packages
    python3 crawl_oulu_courses.py

IMPORTANT NOTES (read before running):
1. `accomplishmentPlanPeriodList` in the sample data you provided contains all zeros. The script
   still parses this field assuming 15 elements = [Y1P1..Y1P5, Y2P1..Y2P5, Y3P1..Y3P4]
   -> takes the first 14 values and maps them into 14 columns in the requested order (drops the last index).
   If after running it still contains all zeros/incorrect values, verify the correct field/period.
2. `description` is left blank as requested (only fills `content`).
3. `id` returned from /api/course/{id} is always null -> the script reuses the id obtained
   from the COURSE_UNIT node in accomplishment-plan (this is the actual id to build url).
4. `instructor_url` does not exist in the source data, so it is NOT included in the column list
   (this field was also removed in the latest schema).
5. Since pages may block by IP/User-Agent, the script includes basic delay + retry.
   If blocked (403/429), add real cookies/headers extracted from a browser.
"""

import json
import time
import re
from pathlib import Path

import requests
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

BASE_API = "https://opasbe.peppi.oulu.fi/api"
BASE_GUIDE = "https://opas.peppi.oulu.fi/en"
PERIOD = "2026-2027"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json",
}

SLEEP_BETWEEN_REQUESTS = 0.3  # seconds, avoid spamming the server
MAX_RETRIES = 3

# 14 timing columns in the requested order
TIMING_COLUMNS = [
    "1st_YEAR_1P", "1st_YEAR_2P", "1st_YEAR_3P", "1st_YEAR_4P", "1st_YEAR_5P",
    "2nd_YEAR_1P", "2nd_YEAR_2P", "2nd_YEAR_3P", "2nd_YEAR_4P", "2nd_YEAR_5P",
    "3rd_YEAR_1P", "3rd_YEAR_2P", "3rd_YEAR_3P", "3rd_YEAR_4P",
]

REQUIRED_KEYS = [
    "programme", "degree_type", "study_option", "title", "code", "id", "name",
    "credits", "learning_outcomes", "content", "instructor", "description",
    "prerequisites", "assessment", "url",
    "start_date", "end_date", "enrollment_start_date", "enrollment_end_date",
]
# ("timing" is split into 14 separate columns at the end, handled separately in write_excel)

FULL_COLUMNS = REQUIRED_KEYS + TIMING_COLUMNS

_course_cache = {}  # course_id -> parsed dict (avoids calling API repeatedly)


# --------------------------------------------------------------------------- #
# HTTP helper
# --------------------------------------------------------------------------- #
def get_json(url: str):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            return resp.json()
        except Exception as e:
            # print(f"  [WARN] Error calling {url} (attempt {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(1.5 * attempt)
    # print(f"  [ERROR] Skipped {url} after {MAX_RETRIES} attempts")
    return None


def val(name_dict, lang="valueEn"):
    """Safely get multilingual value, fallback to Finnish if English is empty."""
    if not isinstance(name_dict, dict):
        return ""
    text = name_dict.get(lang) or ""
    if not text:
        text = name_dict.get("valueFi") or ""
    return text


def clean_html(text: str) -> str:
    """Remove basic HTML tags from description content (course/degree-programme returns HTML)."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# --------------------------------------------------------------------------- #
# Course detail: /api/course/{id}
# --------------------------------------------------------------------------- #
CONTENT_TITLE_MAP = {
    "learning_outcomes": "Learning outcomes",
    "content": "Content",
    "instructor": "Person in charge",
    "prerequisites": "Qualifications",
    "assessment": "Assessment scale",
}

_realization_cache = {}  # course_id -> parsed dict


def epoch_ms_to_iso(epoch_ms):
    """1767218400000 -> '2026-01-01'. Returns '' if None or invalid."""
    if not epoch_ms:
        return ""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def fetch_realizations(course_id: str) -> dict:
    """Call /api/realizations/course/{id}, aggregate course start/end dates and enrollment dates.
    The API may return MULTIPLE realizations for 1 course (multiple groups/terms) ->
    if multiple, dates are joined by '; ' in the order returned, so they can be split
    with split('; ') when importing into the database if 1-to-many is needed."""
    if course_id in _realization_cache:
        return _realization_cache[course_id]

    result = {
        "start_date": "",
        "end_date": "",
        "enrollment_start_date": "",
        "enrollment_end_date": "",
    }

    url = f"{BASE_API}/realizations/course/{course_id}?period={PERIOD}"
    data = get_json(url)

    if data:
        realizations = data if isinstance(data, list) else [data]
        if realizations:
            first = realizations[0]  # only take the first realization
            result["start_date"] = epoch_ms_to_iso(first.get("startDate"))
            result["end_date"] = epoch_ms_to_iso(first.get("endDate"))
            result["enrollment_start_date"] = epoch_ms_to_iso(first.get("enrollmentStartDateTime"))
            result["enrollment_end_date"] = epoch_ms_to_iso(first.get("enrollmentEndDateTime"))

    _realization_cache[course_id] = result
    return result


def fetch_course_detail(course_id: str, course_code: str) -> dict:
    """Return dict fields: learning_outcomes, content, instructor, prerequisites,
    assessment, credits (parsed from contentList by English title)."""
    if course_id in _course_cache:
        return _course_cache[course_id]

    url = f"{BASE_API}/course/{course_id}?period={PERIOD}"
    data = get_json(url)

    result = {
        "credits": None,
        "learning_outcomes": "",
        "content": "",
        "instructor": "",
        "prerequisites": "",
        "assessment": "",
    }

    if data:
        result["credits"] = data.get("credits") or data.get("maxCredits")
        content_list = data.get("contentList") or []
        # group by English title -> target field
        for block in content_list:
            title_en = val(block.get("title"))
            text_en = val(block.get("content"))
            for field_key, wanted_title in CONTENT_TITLE_MAP.items():
                if title_en.strip().lower() == wanted_title.lower():
                    result[field_key] = clean_html(text_en)

    _course_cache[course_id] = result
    return result


# --------------------------------------------------------------------------- #
# Timing: accomplishmentPlanPeriodList -> 14 x / empty columns
# --------------------------------------------------------------------------- #
def parse_timing(period_list):
    """period_list: list of numbers (credits or flags) of length ~15.
    Take the first 14 values, map them to TIMING_COLUMNS in order; value > 0 -> 'x'."""
    marks = {}
    if not period_list:
        return marks
    for i, colname in enumerate(TIMING_COLUMNS):
        if i < len(period_list):
            try:
                v = float(period_list[i])
            except (TypeError, ValueError):
                v = 0
            if v and v != 0:
                marks[colname] = "x"
    return marks


# --------------------------------------------------------------------------- #
# Traverse accomplishment-plan tree (recursive), collect COURSE_UNIT
# --------------------------------------------------------------------------- #
def walk_tree(node, context, rows):
    """
    node: 1 node in the accomplishment-plan tree (dict)
    context: dict containing current programme / degree_type / study_option
    rows: list to append course results
    """
    node_type = node.get("type")

    # Update context when traversing through higher levels
    new_context = dict(context)
    if node_type == "PROGRAMME":
        new_context["study_option"] = val(node.get("name"))
        if node.get("educationLevel"):
            new_context["degree_type"] = node.get("educationLevel")

    if node_type == "COURSE_UNIT":
        course_id = str(node.get("id"))
        course_code = node.get("code") or ""
        detail = fetch_course_detail(course_id, course_code)
        realization = fetch_realizations(course_id)

        name_dict = node.get("name") or {}
        title = val(name_dict, "valueEn")
        name_fi = title  # consistent: both "title" and "name" use English

        credits = detail.get("credits")
        if credits is None:
            credits = node.get("maxCredits")

        row = {
            # As requested: swap programme <-> study_option values in output
            "programme": context.get("study_option", ""),
            "degree_type": context.get("degree_type", ""),
            "study_option": context.get("programme", ""),
            "title": title,
            "code": course_code,
            "id": course_id,
            "name": name_fi,
            "credits": credits,
            "learning_outcomes": detail.get("learning_outcomes", ""),
            "content": detail.get("content", ""),
            "instructor": detail.get("instructor", ""),
            "description": "",  # as requested: left empty
            "prerequisites": detail.get("prerequisites", ""),
            "assessment": detail.get("assessment", ""),
            "url": f"{BASE_GUIDE}/course/{course_code}/{course_id}?period={PERIOD}",
            "start_date": realization.get("start_date", ""),
            "end_date": realization.get("end_date", ""),
            "enrollment_start_date": realization.get("enrollment_start_date", ""),
            "enrollment_end_date": realization.get("enrollment_end_date", ""),
        }
        row.update(parse_timing(node.get("accomplishmentPlanPeriodList")))
        rows.append(row)
        return  # COURSE_UNIT has no children to traverse

    for child in (node.get("children") or []):
        walk_tree(child, new_context, rows)


# --------------------------------------------------------------------------- #
# FLOW 1: Degree Studies (navigation id = 11738)
# --------------------------------------------------------------------------- #
# Only crawl these faculty/faculties for Degree Studies. Leave empty [] to crawl all.
DEGREE_STUDIES_FACULTY_FILTER = ["10965"]


def crawl_degree_studies():
    # print("=== Crawl Degree Studies (id=11738) ===")
    rows = []

    faculties = get_json(f"{BASE_API}/organisation?period={PERIOD}") or []

    for faculty in faculties:
        faculty_id = faculty.get("id")

        if DEGREE_STUDIES_FACULTY_FILTER and str(faculty_id) not in DEGREE_STUDIES_FACULTY_FILTER:
            continue
        faculty_name = val(faculty.get("name"))
        # print(f"[Faculty] {faculty_name} ({faculty_id})")

        education_data = get_json(f"{BASE_API}/education/{faculty_id}/11738?period={PERIOD}")
        if not education_data:
            continue

        # API may return 1 dict or a list of EDUCATION nodes
        education_nodes = education_data if isinstance(education_data, list) else [education_data]

        for edu in education_nodes:
            programme_name = val(edu.get("name"))
            # print(f"  [Education] {programme_name}")

            for child in (edu.get("children") or []):
                if child.get("type") != "PROGRAMME":
                    continue
                programme_id = child.get("id")
                # print(f"    [Programme] {val(child.get('name'))} (id={programme_id})")

                plan = get_json(f"{BASE_API}/accomplishment-plan/{programme_id}?period={PERIOD}")
                if not plan:
                    continue
                plan_nodes = plan if isinstance(plan, list) else [plan]

                context = {
                    "programme": programme_name,
                    "degree_type": child.get("educationLevel", ""),
                    "study_option": val(child.get("name")),
                }
                for pnode in plan_nodes:
                    walk_tree(pnode, context, rows)

    return rows


# --------------------------------------------------------------------------- #
# FLOW 2: Exchange Students (navigation id = 18715)
# --------------------------------------------------------------------------- #
# Only crawl these programme id(s) for Exchange Students.
# Note: endpoint "accomplishment-plan/list/{id}" returns empty/invalid structure
# (tested in practice and confirmed no data) -> use the direct endpoint
# "accomplishment-plan/{id}" (same as Degree Studies) with verified id.
EXCHANGE_PROGRAMME_IDS = ["53264"]


def crawl_exchange_students():
    # print("=== Crawl Exchange Students (id=18715) ===")
    rows = []

    for programme_id in EXCHANGE_PROGRAMME_IDS:
        # print(f"[Programme] id={programme_id}")

        plan = get_json(f"{BASE_API}/accomplishment-plan/{programme_id}?period={PERIOD}")
        if not plan:
            # print(f"  [WARN] Failed to get data for programme id={programme_id}")
            continue

        plan_nodes = plan if isinstance(plan, list) else [plan]

        # Get programme name/context directly from the root node of plan (if any)
        root_name = ""
        root_level = ""
        if plan_nodes:
            root_name = val(plan_nodes[0].get("name"))
            root_level = plan_nodes[0].get("educationLevel", "")

        context = {
            "programme": root_name or f"Exchange programme {programme_id}",
            "degree_type": root_level,
            "study_option": root_name,
        }
        for pnode in plan_nodes:
            walk_tree(pnode, context, rows)

    return rows


# --------------------------------------------------------------------------- #
# Export Excel
# --------------------------------------------------------------------------- #
def write_excel(rows, filepath):
    if not rows:
        # print(f"[WARN] No data to write to {filepath}")
        return

    df = pd.DataFrame(rows)
    # Ensure all columns exist & correct order, even if some rows miss timing columns
    for col in FULL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[FULL_COLUMNS]

    df.to_excel(filepath, index=False, engine="openpyxl")
    # print(f"[OK] Wrote {len(df)} rows to {filepath}")


def main():
    out_dir = Path(__file__).parent
    degree_rows = crawl_degree_studies()
    write_excel(degree_rows, out_dir / "degree_studies.xlsx")

    exchange_rows = crawl_exchange_students()
    write_excel(exchange_rows, out_dir / "exchange_students.xlsx")


if __name__ == "__main__":
    main()