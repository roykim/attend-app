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
# 탭 UI
# ------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 출석 입력",
    "📊 출석 통계",
    "📌 개별 출석 확인",
    "✝️ 새신자 등록",
    "📋 새신자 현황",
    "📂 반정보",
])

render_attendance(tab1)
render_stats(tab2)
render_individual(tab3)
render_newbeliever_register(tab4)
render_newbeliever_status(tab5)
render_class_info(tab6)
