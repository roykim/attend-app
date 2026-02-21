#!/usr/bin/env python3
"""
PersonListDetail.cshtml 페이지 크롤링 → CSV 저장 (단독 실행)
- 로그인 후 해당 페이지가 보이면 엔터를 눌러 크롤링합니다.
- 내용이 iframe 안에 있거나 동적 로딩이면 자동 대응합니다.
"""
import csv
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ------------ 설정 ------------
URL = "http://v6.saeeden.kr/WebMobile/WebSchool/Student/PersonListDetail.cshtml"
OUTPUT_CSV = Path(__file__).resolve().parent / "person_list_detail.csv"
WAIT_TIMEOUT = 15
USE_EXISTING_BROWSER = False
CHROME_USER_DATA = Path.home() / "Library/Application Support/Google/Chrome"
# True 로 두면 HTML 덤프와 추출 통계를 출력해 디버깅에 도움이 됩니다.
DEBUG = True


def get_driver():
    opts = Options()
    if USE_EXISTING_BROWSER and CHROME_USER_DATA.exists():
        opts.add_argument(f"--user-data-dir={CHROME_USER_DATA}")
        opts.add_argument("--profile-directory=Default")
    else:
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print("Chrome 드라이버 실행 실패:", e)
        print("pip install selenium 후 Chrome 설치/경로 확인")
        raise
    return driver


def ensure_content_loaded(driver):
    """iframe 이 있으면 해당 프레임으로 전환하고, 본문이 보일 때까지 대기."""
    # iframe 확인
    iframes = driver.find_elements(By.CSS_SELECTOR, "iframe")
    for i, f in enumerate(iframes):
        try:
            driver.switch_to.frame(f)
            # iframe 안에 테이블이나 본문이 있는지 확인
            body = driver.find_element(By.TAG_NAME, "body")
            if body.text.strip():
                if DEBUG:
                    print(f"[DEBUG] iframe #{i} 로 전환 (내용 있음)")
                return
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
            continue
    driver.switch_to.default_content()
    # 동적 로딩 대기: 테이블 또는 본문 텍스트가 나올 때까지
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            lambda d: (
                d.find_elements(By.CSS_SELECTOR, "table") or
                (d.find_element(By.TAG_NAME, "body").text.strip() and True)
            )
        )
    except Exception:
        pass
    time.sleep(1.5)


def get_cell_text(cell):
    """셀에서 텍스트 추출 (Selenium .text 가 비어도 innerText 시도)."""
    t = (cell.text or "").strip()
    if not t:
        t = (cell.get_attribute("innerText") or "").strip()
    if not t:
        t = (cell.get_attribute("textContent") or "").strip()
    return t


def extract_tables_selenium(driver):
    """Selenium으로 table 행/열 추출 (셀 텍스트는 get_cell_text 사용)."""
    tables = driver.find_elements(By.CSS_SELECTOR, "table")
    if not tables:
        return []
    all_rows = []
    for table in tables:
        for tr in table.find_elements(By.TAG_NAME, "tr"):
            cells = tr.find_elements(By.XPATH, ".//td | .//th")
            row = [get_cell_text(c) for c in cells]
            if any(row):
                all_rows.append(row)
    return all_rows


def _get_current_html(driver):
    """현재 컨텍스트(메인 또는 iframe)의 HTML. iframe 안이면 해당 문서만 반환."""
    try:
        return driver.execute_script("return document.documentElement.outerHTML;")
    except Exception:
        return driver.page_source


def extract_tables_bs4(driver):
    """BeautifulSoup으로 현재 문서 HTML 파싱해 테이블 추출 (동적/스타일 이슈 회피)."""
    try:
        html = _get_current_html(driver)
        if DEBUG:
            dump_path = Path(__file__).resolve().parent / "person_list_detail_debug.html"
            dump_path.write_text(html, encoding="utf-8")
            print(f"[DEBUG] HTML 덤프: {dump_path}")
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        if DEBUG:
            print("[DEBUG] BeautifulSoup 파싱 실패:", e)
        return []
    rows = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            row = [c.get_text(separator=" ", strip=True) for c in cells]
            if any(row):
                rows.append(row)
    return rows


def extract_any_list_like(driver):
    """테이블이 없을 때 리스트/그리드 형태에서 텍스트 수집."""
    html = _get_current_html(driver)
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # ul > li, .list .item, [role="row"] 등
    for selector in ["tr", "[role='row']", "ul li", ".list-item", "[class*='row']"]:
        for el in soup.select(selector):
            parts = el.get_text(separator="|", strip=True).split("|")
            parts = [p.strip() for p in parts if p.strip()]
            if parts and parts not in rows:
                rows.append(parts)
    return rows


def extract_body_lines(driver):
    """본문 텍스트를 한 줄씩 행으로."""
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        raw = body.text or body.get_attribute("innerText") or ""
    except Exception:
        raw = ""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return [[line] for line in lines[:500]]


def normalize_to_columns(rows):
    if not rows:
        return [], []
    ncols = max(len(r) for r in rows)
    normalized = [list(r) + [""] * (ncols - len(r)) for r in rows]
    return normalized[0], normalized[1:] if len(normalized) > 1 else []


def main():
    driver = None
    try:
        driver = get_driver()
        driver.get(URL)
        if not USE_EXISTING_BROWSER:
            input("브라우저에서 로그인한 뒤, PersonListDetail 페이지가 보이면 여기서 엔터를 누르세요...")
        else:
            time.sleep(2)
        ensure_content_loaded(driver)
        rows = extract_tables_selenium(driver)
        if not rows or not any(any(cell for cell in r) for r in rows):
            rows = extract_tables_bs4(driver)
        if not rows:
            rows = extract_any_list_like(driver)
        if not rows:
            rows = extract_body_lines(driver)
        if DEBUG and rows:
            print(f"[DEBUG] 추출 행 수: {len(rows)}, 첫 행 샘플: {rows[0][:5] if rows[0] else []}")
        header, data_rows = normalize_to_columns(rows)
        if not header and data_rows:
            header = [f"col_{i}" for i in range(len(data_rows[0]))]
        out_path = OUTPUT_CSV
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if header:
                w.writerow(header)
            w.writerows(data_rows)
        print(f"저장 완료: {out_path} (헤더 1행 + 데이터 {len(data_rows)}행)")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
