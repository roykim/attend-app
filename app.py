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
# 탭 UI (선택 탭을 세션에 유지해 rerun 후에도 같은 탭 유지, 예: 결재 후)
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
    st.session_state.app_tab_index = 0
# 예산청구 탭에서 rerun 시 복귀할 탭 인덱스가 지정된 경우 적용
if "_budget_tab_index" in st.session_state:
    st.session_state.app_tab_index = st.session_state.pop("_budget_tab_index")

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
