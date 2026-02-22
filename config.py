# -*- coding: utf-8 -*-
"""앱 전역 설정 상수."""

# 구글 시트
SPREADSHEET_NAME = "middle1_2026_weekly_db"  # 출석·학생·새신자 등
BUDGET_SPREADSHEET_NAME = "middle1_2026_budget"  # 예산청구 전용 (결재 비밀번호 config 포함)

# 인증 (default_password는 .streamlit/secrets.toml 또는 Cloud Secrets에 설정, Git에 넣지 말 것)
SESSION_DAYS = 30

# 시트 셀/이미지 제한
SHEET_CELL_MAX = 50000
PHOTO_B64_MAX = 48000

# 사진 저장 고정 크기 (비율 3:4)
PHOTO_WIDTH = 84
PHOTO_HEIGHT = 112
