#!/usr/bin/env python3
"""
저장해 둔 HTML 파일에서 학생 기본 데이터(생년월일, 전화번호, 주소)를 추출해 CSV로 저장합니다.
브라우저에서 해당 페이지를 '다른 이름으로 저장' 한 .html 파일을 지정하면 됩니다.

사용법:
  python extract_from_saved_html.py                    # 기본 파일 사용
  python extract_from_saved_html.py 내가저장한페이지.html
"""
import csv
import sys
from pathlib import Path
from typing import List

from bs4 import BeautifulSoup

# ------------ 설정 ------------
DEFAULT_HTML = Path(__file__).resolve().parent / "person_list_detail_saved.html"
OUTPUT_CSV = Path(__file__).resolve().parent / "students_basic_data.csv"

# CSV 컬럼 (필요 시 수정)
OUTPUT_COLUMNS = ["이름", "생년월일", "전화번호", "주소"]

# 헤더 매칭용 키워드 (한글 라벨로 컬럼 인덱스 찾기)
LABEL_KEYWORDS = {
    "이름": ["이름", "성명", "학생명", "학생"],
    "생년월일": ["생년월일", "생일", "생년", "출생"],
    "전화번호": ["전화", "연락처", "휴대", "핸드폰", "tel", "phone"],
    "주소": ["주소", "주소지", "거주지", "address"],
}


def normalize_text(s):
    if not s:
        return ""
    return " ".join(s.split()).strip()


def find_column_index(headers, field_name):
    """헤더 리스트에서 field_name 에 해당하는 컬럼 인덱스 반환 (없으면 None)."""
    keywords = LABEL_KEYWORDS.get(field_name, [field_name])
    for i, h in enumerate(headers):
        h_norm = normalize_text(h).lower()
        for kw in keywords:
            if kw in h_norm or kw.lower() in h_norm:
                return i
    return None


def extract_from_table(soup):
    """
    테이블에서 헤더(첫 행)를 기준으로 이름/생년월일/전화번호/주소 컬럼을 찾아 행 단위로 반환.
    """
    results = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        # 첫 행을 헤더로
        header_cells = rows[0].find_all(["th", "td"])
        headers = [normalize_text(c.get_text()) for c in header_cells]
        col_map = {f: find_column_index(headers, f) for f in OUTPUT_COLUMNS}
        if all(v is None for v in col_map.values()):
            # 헤더가 없거나 매칭 실패 시 첫 행도 데이터로
            data_start = 0
            ncols = len(header_cells)
            col_map = {f: i for f, i in zip(OUTPUT_COLUMNS, range(min(len(OUTPUT_COLUMNS), ncols)))}
        else:
            data_start = 1
        for tr in rows[data_start:]:
            cells = tr.find_all(["td", "th"])
            vals = [normalize_text(c.get_text()) for c in cells]
            if not any(vals):
                continue
            row = {}
            for field in OUTPUT_COLUMNS:
                idx = col_map.get(field)
                if idx is not None and idx < len(vals):
                    row[field] = vals[idx]
                else:
                    row[field] = ""
            results.append(row)
    return results


def extract_from_label_value_pairs(soup):
    """
    dl(dt/dd), 테이블 2열(라벨/값), li 등 라벨-값 쌍에서 한 명 단위로 추출.
    """
    results = []
    # 패턴: <tr><th>생년월일</th><td>1990-01-01</td></tr> 또는 dt/dd
    def text_of(el):
        return normalize_text(el.get_text()) if el else ""

    # 1) table: 2열 (th/td 라벨-값)
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        row_data = {}
        for tr in rows:
            cells = tr.find_all(["th", "td"])
            if len(cells) >= 2:
                label = text_of(cells[0])
                value = text_of(cells[1])
                for field, keywords in LABEL_KEYWORDS.items():
                    if any(kw in label for kw in keywords):
                        row_data[field] = value
                        break
            elif len(cells) == 1 and row_data:
                # 한 셀만 있는 행은 구분자로 간주하고, 지금까지 모은 row_data 저장
                results.append(row_data)
                row_data = {}
        if row_data:
            results.append(row_data)

    # 2) dl dt/dd
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        row_data = {}
        for dt, dd in zip(dts, dds):
            label = text_of(dt)
            value = text_of(dd)
            for field, keywords in LABEL_KEYWORDS.items():
                if any(kw in label for kw in keywords):
                    row_data[field] = value
                    break
        if row_data:
            results.append(row_data)

    # 3) div/span 라벨-값 (예: <div><span>생년월일</span> 1990-01-01</div>)
    for block in soup.select("[class*='info'], [class*='detail'], .form-group, .row"):
        text = block.get_text(separator="|", strip=True)
        if not any(kw in text for keywords in LABEL_KEYWORDS.values() for kw in keywords):
            continue
        row_data = {}
        for part in text.split("|"):
            part = part.strip()
            for field, keywords in LABEL_KEYWORDS.items():
                if any(kw in part for kw in keywords):
                    # "생년월일 1990-01-01" 형태면 값만 추출
                    for kw in keywords:
                        if kw in part:
                            value = part.replace(kw, "").strip(" :\t").strip()
                            if value and not value.startswith(":"):
                                row_data[field] = value
                            break
                    break
        if row_data:
            results.append(row_data)

    return results


def extract_from_any_table_rows(soup):
    """
    테이블이 있지만 헤더가 우리 키워드와 다를 때: 모든 테이블 행을 가져와
    컬럼 수에 맞춰 이름/생년월일/전화번호/주소 등으로 매핑 시도.
    """
    results = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        all_cells = []
        for tr in rows:
            cells = tr.find_all(["td", "th"])
            vals = [normalize_text(c.get_text()) for c in cells]
            if vals:
                all_cells.append(vals)
        if not all_cells:
            continue
        # 첫 행을 헤더로 시도
        headers = all_cells[0]
        col_map = {f: find_column_index(headers, f) for f in OUTPUT_COLUMNS}
        if any(v is not None for v in col_map.values()):
            for vals in all_cells[1:]:
                row = {f: (vals[col_map[f]] if col_map.get(f) is not None and col_map[f] < len(vals) else "") for f in OUTPUT_COLUMNS}
                if any(row.values()):
                    results.append(row)
        else:
            # 헤더 매칭 실패 시 컬럼 수만 맞춰서 앞에서부터 이름, 생년월일, 전화, 주소로 넣기
            n = min(len(OUTPUT_COLUMNS), max(len(r) for r in all_cells))
            for vals in all_cells:
                row = {OUTPUT_COLUMNS[i]: (vals[i] if i < len(vals) else "") for i in range(n)}
                if any(row.values()):
                    results.append(row)
    return results


def run(html_path: Path) -> List[dict]:
    """HTML 파일 경로를 받아 추출된 학생 데이터 리스트 반환."""
    if not html_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {html_path}")
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")

    # 1) 테이블 헤더 기반 추출
    results = extract_from_table(soup)
    # 2) 라벨-값 쌍 (dt/dd, 2열 테이블 등)
    if not results:
        results = extract_from_label_value_pairs(soup)
    # 3) 그 외 테이블 행 전부
    if not results:
        results = extract_from_any_table_rows(soup)

    return results


def main():
    if len(sys.argv) >= 2:
        html_path = Path(sys.argv[1]).resolve()
    else:
        html_path = DEFAULT_HTML

    print(f"읽는 파일: {html_path}")
    try:
        rows = run(html_path)
    except FileNotFoundError as e:
        print(e)
        print("\n사용법: 브라우저에서 PersonListDetail 페이지를 연 뒤")
        print("  [파일] → [다른 이름으로 저장] 으로 HTML 저장한 다음")
        print(f"  python extract_from_saved_html.py 저장한파일.html")
        print(f"\n또는 저장한 파일 이름을 {DEFAULT_HTML.name} 로 두고 실행하세요.")
        sys.exit(1)

    if not rows:
        print("추출된 데이터가 없습니다. HTML 구조가 다를 수 있습니다.")
        print("person_list_detail_debug.html 처럼 저장된 HTML 내용을 알려주시면 선택자를 맞춰 드릴 수 있습니다.")
        sys.exit(1)

    out_path = OUTPUT_CSV
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"저장 완료: {out_path} (총 {len(rows)}명)")


if __name__ == "__main__":
    main()
