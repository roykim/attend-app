# -*- coding: utf-8 -*-
"""구글 시트 연결 및 워크시트 getter (세션·캐시 활용)."""

import gspread
import pandas as pd
import streamlit as st

from config import SPREADSHEET_NAME


def init(client, spreadsheet_name: str = None):
    """시트 모듈 초기화."""
    global _client, _spreadsheet_name
    _client = client
    _spreadsheet_name = spreadsheet_name or SPREADSHEET_NAME


def get_sheet():
    """세션당 한 번만 시트를 열어 반환. 연결 실패 시 st.stop()."""
    if "sheet" not in st.session_state:
        try:
            st.session_state.sheet = _client.open(_spreadsheet_name)
        except gspread.exceptions.APIError:
            st.error(
                "구글 시트에 연결할 수 없습니다. "
                "시트 이름이 맞는지, **서비스 계정 이메일**에 해당 스프레드시트 공유가 되어 있는지 확인해 주세요. "
                "잠시 후 다시 시도해 보세요."
            )
            st.stop()
    return st.session_state.sheet


@st.cache_data(ttl=120)
def get_students_data():
    """학생 시트 데이터 캐시 (2분)."""
    sheet = get_sheet()
    return pd.DataFrame(sheet.worksheet("students").get_all_records())


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


def ensure_new_believers_photo_column(ws):
    """new_believers 시트에 사진 컬럼 없으면 헤더에 추가."""
    row1 = ws.row_values(1)
    if not row1 or "사진" in row1 or "사진URL" in row1:
        return
    ws.update_cell(1, len(row1) + 1, "사진")


def ensure_students_photo_column(ws):
    """students 시트에 사진/사진URL 컬럼 없으면 헤더에 추가."""
    row1 = ws.row_values(1)
    if not row1 or "사진" in row1 or "사진URL" in row1:
        return
    ws.update_cell(1, len(row1) + 1, "사진")


def ensure_students_extra_columns(ws):
    """students 시트에 생년월일, 성별, 주소, 부모님, 부모님 연락처, 교인여부 없으면 추가."""
    row1 = ws.row_values(1)
    if not row1:
        return
    extra = ["생년월일", "성별", "주소", "부모님", "부모님 연락처", "교인여부"]
    missing = [e for e in extra if e not in row1]
    if not missing:
        return
    start_col = len(row1) + 1
    for i, col_name in enumerate(missing):
        ws.update_cell(1, start_col + i, col_name)


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
