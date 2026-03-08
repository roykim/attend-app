# -*- coding: utf-8 -*-
"""
출석 앱 메인 진입점.
인증 후 탭별 UI를 로드합니다. (기능은 tabs/ 및 auth, sheets, photo_utils, config 모듈에 분리)
"""

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from config import SPREADSHEET_NAME
import auth
import sheets
from tabs import (
    render_attendance,
    render_stats,
    render_individual,
    render_newbeliever_register,
    render_newbeliever_status,
    render_class_info,
    render_budget_request,
)


# ------------------------
# 구글 시트 클라이언트
# ------------------------
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope,
)
client = gspread.authorize(creds)

# ------------------------
# 인증 (비밀번호·세션)
# ------------------------
auth.init(client, SPREADSHEET_NAME)
auth.check_password()
auth.show_change_password_if_needed()

if st.session_state.get("show_bookmark_hint"):
    st.info("💡 이 주소를 **북마크**해 두시면 30일 동안 비밀번호 없이 이용할 수 있습니다.")
    del st.session_state.show_bookmark_hint

# ------------------------
# 시트 연결 (탭에서 데이터 로드)
# ------------------------
sheets.init(client, SPREADSHEET_NAME)
sheets.get_sheet()  # 연결 검증 및 세션 캐시

# ------------------------
# 탭 UI (선택 탭을 세션·URL·단말별 저장으로 유지 — 다시 들어와도 마지막 탭 복원)
# ------------------------
TAB_LABELS = [
    "📋 출석 입력",
    "📊 출석 통계",
    "📌 개별 출석 확인",
    "✝️ 새신자 등록",
    "📋 새신자 현황",
    "📂 반정보",
    "💰 예산청구",
]
if "app_tab_index" not in st.session_state:
    # 1) URL에 tab 있으면 사용 (북마크/공유 시 복원)
    tab_param = st.query_params.get("tab")
    if tab_param is not None and str(tab_param).strip() != "":
        try:
            idx = int(str(tab_param).strip())
            st.session_state.app_tab_index = max(0, min(idx, len(TAB_LABELS) - 1))
        except (ValueError, TypeError):
            st.session_state.app_tab_index = 0
    else:
        # 2) 이 단말에서 마지막으로 보던 탭 복원
        fp = auth.get_fingerprint_hash()
        last_idx = sheets.get_last_tab_index(fp)
        if last_idx is not None and 0 <= last_idx < len(TAB_LABELS):
            st.session_state.app_tab_index = last_idx
        else:
            st.session_state.app_tab_index = 0
    # 마지막으로 선택했던 학년·반은 URL 여부와 관계없이 항상 시트에서 복원
    fp = auth.get_fingerprint_hash()
    last_grade, last_class = sheets.get_last_grade_class(fp)
    if last_grade:
        st.session_state["app_last_grade"] = last_grade
    if last_class:
        st.session_state["app_last_class"] = last_class
# 예산청구 탭에서 rerun 시 복귀할 탭 인덱스가 지정된 경우 적용
if "_budget_tab_index" in st.session_state:
    st.session_state.app_tab_index = st.session_state.pop("_budget_tab_index")

# URL에 현재 탭 반영해 두기 (북마크 시 같은 탭으로 복원되도록)
_current_tab = st.session_state.app_tab_index
if str(st.query_params.get("tab", "")) != str(_current_tab):
    st.query_params["tab"] = _current_tab

tab_index = st.session_state.app_tab_index
selected_label = st.radio(
    "메뉴",
    TAB_LABELS,
    index=min(tab_index, len(TAB_LABELS) - 1),
    key="app_tab_radio",
    horizontal=True,
    label_visibility="collapsed",
)
new_index = TAB_LABELS.index(selected_label) if selected_label in TAB_LABELS else 0
if new_index != st.session_state.app_tab_index:
    st.session_state.app_tab_index = new_index
    # URL에 탭 반영 (같은 주소로 다시 들어와도 해당 탭 복원)
    st.query_params["tab"] = new_index
    # 이 단말에서 마지막 탭으로 저장 (다음 접속 시 복원)
    fp = auth.get_fingerprint_hash()
    sheets.set_last_tab_index(fp, new_index)
    st.rerun()

tab_container = st.container()
with tab_container:
    if st.session_state.app_tab_index == 0:
        render_attendance(tab_container)
    elif st.session_state.app_tab_index == 1:
        render_stats(tab_container)
    elif st.session_state.app_tab_index == 2:
        render_individual(tab_container)
    elif st.session_state.app_tab_index == 3:
        render_newbeliever_register(tab_container)
    elif st.session_state.app_tab_index == 4:
        render_newbeliever_status(tab_container)
    elif st.session_state.app_tab_index == 5:
        render_class_info(tab_container)
    else:
        render_budget_request(tab_container)
