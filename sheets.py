# -*- coding: utf-8 -*-
"""구글 시트 연결 및 워크시트 getter (세션·캐시 활용)."""

import time

import gspread
import pandas as pd
import streamlit as st

from config import SPREADSHEET_NAME, BUDGET_SPREADSHEET_NAME


def init(client, spreadsheet_name: str = None):
    """시트 모듈 초기화."""
    global _client, _spreadsheet_name
    _client = client
    _spreadsheet_name = spreadsheet_name or SPREADSHEET_NAME


def get_sheet():
    """세션당 한 번만 시트를 열어 반환. 429 시 잠시 대기 후 1회 재시도."""
    if "sheet" not in st.session_state:
        last_err = None
        for attempt in range(2):
            try:
                st.session_state.sheet = _client.open(_spreadsheet_name)
                last_err = None
                break
            except gspread.exceptions.APIError as e:
                last_err = e
                resp = getattr(e, "response", None)
                if resp is not None and getattr(resp, "status_code", None) == 429 and attempt == 0:
                    time.sleep(8)
                    continue
                break
        if last_err is not None:
            st.error(
                "구글 시트에 연결할 수 없습니다. "
                "시트 이름이 맞는지, **서비스 계정 이메일**에 해당 스프레드시트 공유가 되어 있는지 확인해 주세요. "
                "읽기 한도(429)가 나온 경우 잠시 후 다시 시도해 보세요."
            )
            st.stop()
    return st.session_state.sheet


def get_budget_sheet():
    """예산청구 전용 스프레드시트. 세션당 한 번만 열어 반환. 429 시 잠시 대기 후 1회 재시도."""
    if "budget_sheet" not in st.session_state:
        last_err = None
        for attempt in range(2):
            try:
                st.session_state.budget_sheet = _client.open(BUDGET_SPREADSHEET_NAME)
                last_err = None
                break
            except gspread.exceptions.SpreadsheetNotFound:
                last_err = None
                st.error(
                    f"**예산청구용 스프레드시트를 찾을 수 없습니다.**\n\n"
                    f"다음을 확인해 주세요:\n"
                    f"1. 구글 드라이브에 **이름이 `{BUDGET_SPREADSHEET_NAME}` 인** 스프레드시트를 만드세요.\n"
                    f"2. 해당 스프레드시트를 **편집 권한**으로 **서비스 계정 이메일**과 공유하세요.\n"
                    f"   (서비스 계정 이메일은 GCP/Secrets 설정에서 확인할 수 있습니다.)"
                )
                st.stop()
            except gspread.exceptions.APIError as e:
                last_err = e
                resp = getattr(e, "response", None)
                if resp is not None and getattr(resp, "status_code", None) == 429 and attempt == 0:
                    time.sleep(8)
                    continue
                break
        if last_err is not None:
            st.error(
                "예산청구용 구글 시트에 연결할 수 없습니다. "
                "시트 이름이 맞는지, **서비스 계정 이메일**에 해당 스프레드시트 공유가 되어 있는지 확인해 주세요."
            )
            st.stop()
    return st.session_state.budget_sheet


@st.cache_data(ttl=300)
def get_students_data():
    """학생 시트 데이터 캐시 (5분). API 읽기 한도 절약."""
    sheet = get_sheet()
    return pd.DataFrame(sheet.worksheet("students").get_all_records())


@st.cache_data(ttl=300)
def get_attendance_data():
    """출석 시트 데이터 캐시 (5분). API 읽기 한도 절약."""
    return pd.DataFrame(get_attendance_ws().get_all_records())


@st.cache_data(ttl=300)
def get_new_believers_data():
    """새신자 시트 데이터 캐시 (5분)."""
    return get_new_believers_ws().get_all_records()


def invalidate_sheets_cache():
    """시트에 쓰기 후 캐시 무효화. 저장/수정 직후 호출."""
    st.cache_data.clear()


def get_attendance_ws():
    """출석 시트 반환 (세션 캐시)."""
    if "attendance_ws" not in st.session_state:
        st.session_state.attendance_ws = get_sheet().worksheet("attendance")
    return st.session_state.attendance_ws


def get_students_ws():
    """students 시트 반환 (세션 캐시)."""
    if "students_ws" not in st.session_state:
        st.session_state.students_ws = get_sheet().worksheet("students")
    return st.session_state.students_ws


def _ensured_key(ws_name: str, suffix: str) -> str:
    return f"sheets_ensured_{ws_name}_{suffix}"


def ensure_new_believers_photo_column(ws):
    """new_believers 시트에 사진 컬럼 없으면 헤더에 추가. 세션당 1회만 API 읽기."""
    key = _ensured_key("new_believers", "photo")
    if st.session_state.get(key):
        return
    row1 = ws.row_values(1)
    if not row1 or "사진" in row1 or "사진URL" in row1:
        st.session_state[key] = True
        return
    ws.update_cell(1, len(row1) + 1, "사진")
    st.session_state[key] = True


def ensure_students_photo_column(ws):
    """students 시트에 사진/사진URL 컬럼 없으면 헤더에 추가. 세션당 1회만 API 읽기."""
    key = _ensured_key("students", "photo")
    if st.session_state.get(key):
        return
    row1 = ws.row_values(1)
    if not row1 or "사진" in row1 or "사진URL" in row1:
        st.session_state[key] = True
        return
    ws.update_cell(1, len(row1) + 1, "사진")
    st.session_state[key] = True


def ensure_students_extra_columns(ws):
    """students 시트에 생년월일, 성별, 주소 등 없으면 추가. 세션당 1회만 API 읽기."""
    key = _ensured_key("students", "extra")
    if st.session_state.get(key):
        return
    row1 = ws.row_values(1)
    if not row1:
        st.session_state[key] = True
        return
    extra = ["생년월일", "성별", "주소", "부모님", "부모님 연락처", "교인여부"]
    missing = [e for e in extra if e not in row1]
    if not missing:
        st.session_state[key] = True
        return
    start_col = len(row1) + 1
    for i, col_name in enumerate(missing):
        ws.update_cell(1, start_col + i, col_name)
    st.session_state[key] = True


def get_new_believers_ws():
    """새신자 시트 반환. 없으면 생성 후 헤더 작성."""
    if "new_believers_ws" not in st.session_state:
        sheet = get_sheet()
        try:
            ws = sheet.worksheet("new_believers")
            ensure_new_believers_photo_column(ws)
            st.session_state.new_believers_ws = ws
        except gspread.exceptions.WorksheetNotFound:
            sheet.add_worksheet(title="new_believers", rows=100, cols=10)
            ws = sheet.worksheet("new_believers")
            ws.append_row(["등록일", "이름", "전화", "생년월일", "주소", "전도한친구이름", "학년", "반", "사진"])
            st.session_state.new_believers_ws = ws
    return st.session_state.new_believers_ws


# ------------------------
# 예산청구 시트
# ------------------------
BUDGET_CLAIM_HEADERS = [
    "등록번호", "지출날짜", "청구내용", "청구금액", "세부내역", "입금계좌", "청구날짜", "청구자",
    "그룹명", "인원수",
    "결재상태", "결재일시",
    "증빙1", "증빙2", "증빙3", "증빙4", "증빙5", "증빙6", "증빙7", "증빙8", "증빙9", "증빙10",
]


def get_budget_request_ws():
    """예산청구 시트 반환. 없으면 생성 후 헤더 작성. (예산 전용 스프레드시트 사용)"""
    if "budget_request_ws" not in st.session_state:
        sheet = get_budget_sheet()
        try:
            ws = sheet.worksheet("예산청구")
            _ensure_budget_request_headers(ws)
            st.session_state.budget_request_ws = ws
        except gspread.exceptions.WorksheetNotFound:
            sheet.add_worksheet(title="예산청구", rows=200, cols=len(BUDGET_CLAIM_HEADERS) + 2)
            ws = sheet.worksheet("예산청구")
            ws.append_row(BUDGET_CLAIM_HEADERS)
            st.session_state.budget_request_ws = ws
    return st.session_state.budget_request_ws


def _ensure_budget_request_headers(ws):
    """예산청구 시트에 필수 헤더가 없으면 1행에 작성. 세션당 1회만 API 읽기."""
    key = _ensured_key("budget_request", "headers")
    if st.session_state.get(key):
        return
    row1 = ws.row_values(1)
    if not row1 or row1[0] != "등록번호":
        ws.update("A1", [BUDGET_CLAIM_HEADERS])
    elif "그룹명" not in row1:
        col = len(row1) + 1
        ws.update_cell(1, col, "그룹명")
        ws.update_cell(1, col + 1, "인원수")
    st.session_state[key] = True


@st.cache_data(ttl=180)
def get_budget_requests_data():
    """예산청구 시트 전체 데이터 (캐시 1분)."""
    ws = get_budget_request_ws()
    rows = ws.get_all_values()
    if not rows or len(rows) < 2:
        return pd.DataFrame(columns=BUDGET_CLAIM_HEADERS)
    return pd.DataFrame(rows[1:], columns=rows[0])


def get_next_budget_reg_no():
    """다음 등록번호 (숫자). 기존 최대값+1, 없으면 1."""
    df = get_budget_requests_data()
    if df.empty or "등록번호" not in df.columns:
        return 1
    try:
        nums = pd.to_numeric(df["등록번호"], errors="coerce").dropna()
        return int(nums.max()) + 1 if len(nums) else 1
    except Exception:
        return 1


def get_last_budget_defaults():
    """마지막 예산청구 행에서 입금계좌, 청구자 반환 (이전 내용 유지용). (입금계좌, 청구자) 또는 (None, None)."""
    df = get_budget_requests_data()
    if df.empty or len(df) == 0:
        return None, None
    row = df.iloc[-1]
    acc = row.get("입금계좌") or row.get("입금 계좌")
    claimer = row.get("청구자")
    return (str(acc).strip() if acc and str(acc).strip() else None), (str(claimer).strip() if claimer and str(claimer).strip() else None)
