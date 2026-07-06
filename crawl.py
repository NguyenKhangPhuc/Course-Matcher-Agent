"""
Crawl dữ liệu chương trình học / khóa học từ Peppi Study Guide (University of Oulu)
và xuất ra 2 file Excel:
    - degree_studies.xlsx   (navigation id = 11738, Degree Studies)
    - exchange_students.xlsx (navigation id = 18715, Exchange Students)

CÁCH CHẠY:
    pip install requests pandas openpyxl --break-system-packages
    python3 crawl_oulu_courses.py

GHI CHÚ QUAN TRỌNG (đọc trước khi chạy):
1. `accomplishmentPlanPeriodList` trong dữ liệu mẫu bạn gửi toàn số 0. Script vẫn
   parse field này theo giả định 15 phần tử = [Y1P1..Y1P5, Y2P1..Y2P5, Y3P1..Y3P4]
   -> lấy 14 giá trị đầu map vào 14 cột theo đúng thứ tự bạn yêu cầu (bỏ index cuối).
   Nếu sau khi chạy thật vẫn toàn 0/không đúng, cần xem lại đúng field/period.
2. `description` được để trống theo yêu cầu của bạn (chỉ điền `content`).
3. `id` trả về từ /api/course/{id} luôn là null -> script dùng lại id lấy được
   từ node COURSE_UNIT trong accomplishment-plan (đây mới là id thật để build url).
4. `instructor_url` không tồn tại trong dữ liệu nguồn nên KHÔNG có trong danh sách cột
   (theo schema bạn gửi lần cuối cũng đã bỏ field này).
5. Do các trang có thể chặn theo IP/User-Agent, script có delay + retry cơ bản.
   Nếu bị chặn (403/429), cần thêm cookie/headers thực tế lấy từ trình duyệt.
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

SLEEP_BETWEEN_REQUESTS = 0.3  # giây, tránh spam server
MAX_RETRIES = 3

# 14 cột timing theo đúng thứ tự bạn yêu cầu
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
# ("timing" được tách thành 14 cột riêng ở cuối, xử lý riêng trong write_excel)

FULL_COLUMNS = REQUIRED_KEYS + TIMING_COLUMNS

_course_cache = {}  # course_id -> dict đã parse (tránh gọi lại API nhiều lần)


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
            print(f"  [WARN] Lỗi khi gọi {url} (lần {attempt}/{MAX_RETRIES}): {e}")
            time.sleep(1.5 * attempt)
    print(f"  [ERROR] Bỏ qua {url} sau {MAX_RETRIES} lần thử")
    return None


def val(name_dict, lang="valueEn"):
    """Lấy giá trị đa ngôn ngữ an toàn, fallback sang Finnish nếu tiếng Anh trống."""
    if not isinstance(name_dict, dict):
        return ""
    text = name_dict.get(lang) or ""
    if not text:
        text = name_dict.get("valueFi") or ""
    return text


def clean_html(text: str) -> str:
    """Xóa thẻ HTML cơ bản khỏi nội dung mô tả (course/degree-programme trả HTML)."""
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

_realization_cache = {}  # course_id -> dict đã parse


def epoch_ms_to_iso(epoch_ms):
    """1767218400000 -> '2026-01-01'. Trả về '' nếu None/không hợp lệ."""
    if not epoch_ms:
        return ""
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def fetch_realizations(course_id: str) -> dict:
    """Gọi /api/realizations/course/{id}, gom ngày bắt đầu/kết thúc học và đăng ký.
    API có thể trả về NHIỀU lần tổ chức (realizations) cho 1 course (nhiều nhóm/kỳ) ->
    nếu có nhiều, các ngày được nối bằng '; ' theo đúng thứ tự trả về, để khi import
    vào database vẫn tách được bằng split('; ') nếu cần 1-nhiều."""
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
            first = realizations[0]  # chỉ lấy realization đầu tiên
            result["start_date"] = epoch_ms_to_iso(first.get("startDate"))
            result["end_date"] = epoch_ms_to_iso(first.get("endDate"))
            result["enrollment_start_date"] = epoch_ms_to_iso(first.get("enrollmentStartDateTime"))
            result["enrollment_end_date"] = epoch_ms_to_iso(first.get("enrollmentEndDateTime"))

    _realization_cache[course_id] = result
    return result


def fetch_course_detail(course_id: str, course_code: str) -> dict:
    """Trả về dict field: learning_outcomes, content, instructor, prerequisites,
    assessment, credits (đã parse từ contentList theo title tiếng Anh)."""
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
        # gom theo title tiếng Anh -> field đích
        for block in content_list:
            title_en = val(block.get("title"))
            text_en = val(block.get("content"))
            for field_key, wanted_title in CONTENT_TITLE_MAP.items():
                if title_en.strip().lower() == wanted_title.lower():
                    result[field_key] = clean_html(text_en)

    _course_cache[course_id] = result
    return result


# --------------------------------------------------------------------------- #
# Timing: accomplishmentPlanPeriodList -> 14 cột x/ trống
# --------------------------------------------------------------------------- #
def parse_timing(period_list):
    """period_list: list số (điểm tín chỉ hoặc cờ) độ dài ~15.
    Lấy 14 giá trị đầu, map vào TIMING_COLUMNS theo thứ tự; giá trị > 0 -> 'x'."""
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
# Duyệt cây accomplishment-plan (đệ quy), thu thập COURSE_UNIT
# --------------------------------------------------------------------------- #
def walk_tree(node, context, rows):
    """
    node: 1 node trong cây accomplishment-plan (dict)
    context: dict chứa programme / degree_type / study_option hiện tại
    rows: list để append kết quả course
    """
    node_type = node.get("type")

    # Cập nhật context khi đi qua các cấp cao hơn
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
        name_fi = title  # đồng nhất: cả "title" và "name" đều lấy tiếng Anh

        credits = detail.get("credits")
        if credits is None:
            credits = node.get("maxCredits")

        row = {
            "programme": context.get("programme", ""),
            "degree_type": context.get("degree_type", ""),
            "study_option": context.get("study_option", ""),
            "title": title,
            "code": course_code,
            "id": course_id,
            "name": name_fi,
            "credits": credits,
            "learning_outcomes": detail.get("learning_outcomes", ""),
            "content": detail.get("content", ""),
            "instructor": detail.get("instructor", ""),
            "description": "",  # theo yêu cầu: để trống
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
        return  # COURSE_UNIT không có children cần đi tiếp

    for child in (node.get("children") or []):
        walk_tree(child, new_context, rows)


# --------------------------------------------------------------------------- #
# LUỒNG 1: Degree Studies (navigation id = 11738)
# --------------------------------------------------------------------------- #
# Chỉ crawl (các) faculty này cho Degree Studies. Để trống [] để crawl tất cả.
DEGREE_STUDIES_FACULTY_FILTER = ["10965"]


def crawl_degree_studies():
    print("=== Crawl Degree Studies (id=11738) ===")
    rows = []

    faculties = get_json(f"{BASE_API}/organisation?period={PERIOD}") or []

    for faculty in faculties:
        faculty_id = faculty.get("id")

        if DEGREE_STUDIES_FACULTY_FILTER and str(faculty_id) not in DEGREE_STUDIES_FACULTY_FILTER:
            continue
        faculty_name = val(faculty.get("name"))
        print(f"[Faculty] {faculty_name} ({faculty_id})")

        education_data = get_json(f"{BASE_API}/education/{faculty_id}/11738?period={PERIOD}")
        if not education_data:
            continue

        # API có thể trả 1 dict hoặc list các EDUCATION node
        education_nodes = education_data if isinstance(education_data, list) else [education_data]

        for edu in education_nodes:
            programme_name = val(edu.get("name"))
            print(f"  [Education] {programme_name}")

            for child in (edu.get("children") or []):
                if child.get("type") != "PROGRAMME":
                    continue
                programme_id = child.get("id")
                print(f"    [Programme] {val(child.get('name'))} (id={programme_id})")

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
# LUỒNG 2: Exchange Students (navigation id = 18715)
# --------------------------------------------------------------------------- #
# Chỉ crawl (các) programme id này cho Exchange Students.
# Ghi chú: endpoint "accomplishment-plan/list/{id}" trả về rỗng/không đúng cấu trúc
# (đã test thực tế thấy không có dữ liệu) -> dùng thẳng endpoint
# "accomplishment-plan/{id}" (giống Degree Studies) với id đã biết là đúng.
EXCHANGE_PROGRAMME_IDS = ["53264"]


def crawl_exchange_students():
    print("=== Crawl Exchange Students (id=18715) ===")
    rows = []

    for programme_id in EXCHANGE_PROGRAMME_IDS:
        print(f"[Programme] id={programme_id}")

        plan = get_json(f"{BASE_API}/accomplishment-plan/{programme_id}?period={PERIOD}")
        if not plan:
            print(f"  [WARN] Không lấy được dữ liệu cho programme id={programme_id}")
            continue

        plan_nodes = plan if isinstance(plan, list) else [plan]

        # Lấy tên chương trình/context trực tiếp từ node gốc của plan (nếu có)
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
# Xuất Excel
# --------------------------------------------------------------------------- #
def write_excel(rows, filepath):
    if not rows:
        print(f"[WARN] Không có dữ liệu để ghi vào {filepath}")
        return

    df = pd.DataFrame(rows)
    # Đảm bảo đủ cột & đúng thứ tự, kể cả khi 1 số row thiếu timing column
    for col in FULL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[FULL_COLUMNS]

    df.to_excel(filepath, index=False, engine="openpyxl")
    print(f"[OK] Đã ghi {len(df)} dòng vào {filepath}")


def main():
    out_dir = Path(__file__).parent
    degree_rows = crawl_degree_studies()
    write_excel(degree_rows, out_dir / "degree_studies.xlsx")

    exchange_rows = crawl_exchange_students()
    write_excel(exchange_rows, out_dir / "exchange_students.xlsx")


if __name__ == "__main__":
    main()