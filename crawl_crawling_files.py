#!/usr/bin/env python3
"""
crawling_files 폴더의 저장된 HTML(앱교회학교관리.html)에서 학생 정보를 추출해 CSV로 저장합니다.
PersonListDetail 페이지를 "다른 이름으로 저장"한 파일을 분석합니다.
"""
import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup

# ------------ 설정 ------------
CRAWLING_DIR = Path(__file__).resolve().parent / "crawling_files"
DEFAULT_HTML = CRAWLING_DIR / "앱교회학교관리.html"
OUTPUT_CSV = Path(__file__).resolve().parent / "students_from_crawling_files.csv"

# CSV 컬럼
COLUMNS = [
    "이름",
    "회원ID",
    "나이",
    "성별",
    "등록일",
    "상태",
    "휴대전화",
    "전화번호",
    "소속",
    "주소",
]


def normalize(s):
    if not s:
        return ""
    return " ".join(s.split()).strip().replace("\xa0", " ")


def parse_id_from_span(li_main):
    """메인 li에서 회원 ID (39439) 추출."""
    span = li_main.find("span", class_="liResultLiDetailNormal")
    if not span:
        return ""
    text = span.get_text(strip=True)  # "(39439)"
    m = re.search(r"\((\d+)\)", text)
    return m.group(1) if m else ""


def parse_age_sex_regday(li_main):
    """메인 li의 첫 번째 p에서 '13세 남, 등록일:' 형태 파싱."""
    p = li_main.find("p", style=re.compile(r"white-space"))
    if not p:
        return "", "", ""
    text = normalize(p.get_text())
    age, sex, regday = "", "", ""
    # "13세 남, 등록일:" or "13세 남, 등록일: 2020-01-01"
    age_m = re.search(r"(\d+)세", text)
    if age_m:
        age = age_m.group(1)
    if "남" in text:
        sex = "남"
    elif "여" in text:
        sex = "여"
    reg_m = re.search(r"등록일[:\s]*(\S+)", text)
    if reg_m:
        regday = reg_m.group(1).strip(" ,")
    if regday == ":" or not regday.strip():
        regday = ""
    return age, sex, regday


def parse_handphone_tel(p_text):
    """'010-9157-5215 , ' 또는 ' , 02-123-4567' 형태에서 휴대/전화 분리."""
    p_text = normalize(p_text)
    parts = [s.strip() for s in p_text.split(",") if s.strip()]
    handphone, tel = "", ""
    for part in parts:
        if re.match(r"010-\d", part) or re.match(r"01[0-9]-", part):
            handphone = part
        elif part and not handphone:
            handphone = part  # 하나만 있으면 휴대번호로
        elif part:
            tel = part
    if len(parts) == 1 and parts[0]:
        handphone = parts[0]
    elif len(parts) >= 2:
        handphone = parts[0] or ""
        tel = parts[1] if len(parts) > 1 else ""
    return handphone, tel


def extract_students(soup):
    """
    #lvResult ul 안의 li 쌍(메인+상세)에서 학생 한 명씩 추출.
    """
    ul = soup.find(id="lvResult")
    if not ul:
        return []
    lis = ul.find_all("li", recursive=False)
    if len(lis) < 2:
        return []
    students = []
    # 첫 li는 '검색결과 196' 디바이더이므로 1부터, 2개씩 (메인, 상세)
    i = 1
    while i + 1 < len(lis):
        li_main = lis[i]
        li_detail = lis[i + 1]
        # 메인에는 contentName이 있음
        name_el = li_main.find(class_="contentName")
        if not name_el:
            i += 1
            continue
        name = normalize(name_el.get_text())
        member_id = parse_id_from_span(li_main)
        age, sex, regday = parse_age_sex_regday(li_main)

        # 상세 li: p.liResultLiDetailNormal 순서대로 상태, 전화, 소속, 주소
        detail_ps = li_detail.find_all("p", class_="liResultLiDetailNormal")
        state = normalize(detail_ps[0].get_text()) if len(detail_ps) > 0 else ""
        handphone, tel = "", ""
        if len(detail_ps) > 1:
            handphone, tel = parse_handphone_tel(detail_ps[1].get_text())
        group = normalize(detail_ps[2].get_text()) if len(detail_ps) > 2 else ""
        addr = normalize(detail_ps[3].get_text()) if len(detail_ps) > 3 else ""

        students.append({
            "이름": name,
            "회원ID": member_id,
            "나이": age,
            "성별": sex,
            "등록일": regday,
            "상태": state,
            "휴대전화": handphone,
            "전화번호": tel,
            "소속": group,
            "주소": addr,
        })
        i += 2
    return students


def main():
    html_path = DEFAULT_HTML
    if not html_path.exists():
        print(f"파일을 찾을 수 없습니다: {html_path}")
        return 1
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    students = extract_students(soup)
    if not students:
        print("추출된 학생 데이터가 없습니다.")
        return 1
    out_path = OUTPUT_CSV
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(students)
    print(f"저장 완료: {out_path} (총 {len(students)}명)")
    return 0


if __name__ == "__main__":
    exit(main())
