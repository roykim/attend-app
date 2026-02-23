# -*- coding: utf-8 -*-
"""비밀번호·세션(URL 토큰·단말 지문) 인증."""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta

import streamlit as st
from cryptography.fernet import Fernet

from config import SESSION_DAYS, BUDGET_SPREADSHEET_NAME


def init(client, spreadsheet_name: str):
    """인증 모듈 초기화. app에서 client·스프레드시트 이름 설정."""
    global _client, _spreadsheet_name
    _client = client
    _spreadsheet_name = spreadsheet_name


def _get_fernet():
    """Secrets의 encryption_key로 Fernet 인스턴스 생성."""
    raw = st.secrets.get("encryption_key")
    if not raw:
        raise ValueError("Secrets에 encryption_key를 설정해 주세요. (Streamlit Cloud: 설정 → Secrets)")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def _get_config_worksheet():
    """출석용 스프레드시트 안의 'config' 시트 반환. 없으면 생성."""
    import gspread
    sheet = _client.open(_spreadsheet_name)
    try:
        return sheet.worksheet("config")
    except gspread.exceptions.WorksheetNotFound:
        sheet.add_worksheet(title="config", rows=2, cols=2)
        return sheet.worksheet("config")


def _get_budget_config_worksheet():
    """예산청구 전용 스프레드시트 안의 'config' 시트 반환. 없으면 생성. (결재/조회 비밀번호, 결재자 정보). 최소 6행 3열 보장."""
    import gspread
    sheet = _client.open(BUDGET_SPREADSHEET_NAME)
    try:
        ws = sheet.worksheet("config")
    except gspread.exceptions.WorksheetNotFound:
        sheet.add_worksheet(title="config", rows=6, cols=3)
        return sheet.worksheet("config")
    if ws.row_count < 6:
        ws.add_rows(6 - ws.row_count)
    if ws.col_count < 3:
        ws.add_cols(3 - ws.col_count)
    return ws


def get_stored_password():
    """config 시트 A1에 저장된 암호화 비밀번호를 읽어 복호화. 없으면 None."""
    try:
        ws = _get_config_worksheet()
        enc = ws.acell("A1").value
        if not enc or not enc.strip():
            return None
        return _get_fernet().decrypt(enc.strip().encode()).decode()
    except Exception:
        return None


def set_stored_password(plain_password: str):
    """비밀번호를 암호화해 config 시트 A1에 저장."""
    enc = _get_fernet().encrypt(plain_password.encode()).decode()
    _get_config_worksheet().update_acell("A1", enc)


def _get_approval_config_year():
    """결재 설정이 저장된 연도. B5. 없거나 현재 연도와 다르면 None (매년 1월 1일 리셋)."""
    try:
        ws = _get_budget_config_worksheet()
        y = ws.acell("B5").value
        if not y:
            return None
        return str(y).strip()
    except Exception:
        return None


def get_budget_config():
    """예산 조회/결재 설정을 한 번의 시트 읽기로 반환. B1:B5, C1 사용.
    반환: {"year_ok": bool, "approval_password": str|None, "view_password": str|None, "approver_info": dict|None}
    """
    try:
        ws = _get_budget_config_worksheet()
        # B1:B5, C1 한 번에 읽기 (B1~B5가 1열, C1은 2열 첫 행)
        rows = ws.get("B1:C5")
        if not rows or len(rows) < 5:
            return {"year_ok": False, "approval_password": None, "view_password": None, "approver_info": None}
        current_year = str(datetime.now().year)
        year_val = (rows[4][0] if len(rows[4]) > 0 else None) or ""
        year_ok = str(year_val).strip() == current_year
        if not year_ok:
            return {"year_ok": False, "approval_password": None, "view_password": None, "approver_info": None}
        approval_pw = None
        view_pw = None
        fernet = _get_fernet()
        b1_enc = (rows[0][0] if len(rows[0]) > 0 else None) or ""
        if b1_enc and str(b1_enc).strip():
            try:
                approval_pw = fernet.decrypt(str(b1_enc).strip().encode()).decode()
            except Exception:
                pass
        c1_enc = (rows[0][1] if len(rows[0]) > 1 else None) or ""
        if c1_enc and str(c1_enc).strip():
            try:
                view_pw = fernet.decrypt(str(c1_enc).strip().encode()).decode()
            except Exception:
                pass
        dept = (rows[1][0] if len(rows[1]) > 0 else None) or ""
        name = (rows[2][0] if len(rows[2]) > 0 else None) or ""
        title = (rows[3][0] if len(rows[3]) > 0 else None) or ""
        dept, name, title = str(dept).strip(), str(name).strip(), str(title).strip()
        approver_info = {"부서": dept, "이름": name, "직책": title} if (dept or name or title) else None
        return {"year_ok": True, "approval_password": approval_pw, "view_password": view_pw, "approver_info": approver_info}
    except Exception:
        return {"year_ok": False, "approval_password": None, "view_password": None, "approver_info": None}


def get_approval_password():
    """결재(승인)용 비밀번호. B1. 저장 연도가 현재 연도가 아니면 None(리셋)."""
    try:
        current_year = str(datetime.now().year)
        if _get_approval_config_year() != current_year:
            return None
        ws = _get_budget_config_worksheet()
        enc = ws.acell("B1").value
        if not enc or not enc.strip():
            return None
        return _get_fernet().decrypt(enc.strip().encode()).decode()
    except Exception:
        return None


def set_approval_password(plain_password: str):
    """결재 비밀번호를 B1에 암호화 저장, B5에 현재 연도 저장."""
    enc = _get_fernet().encrypt(plain_password.encode()).decode()
    ws = _get_budget_config_worksheet()
    ws.update_acell("B1", enc)
    ws.update_acell("B5", str(datetime.now().year))


def get_approver_info():
    """결재자 정보 (부서, 이름, 직책). B2,B3,B4. 저장 연도가 현재가 아니면 None."""
    try:
        current_year = str(datetime.now().year)
        if _get_approval_config_year() != current_year:
            return None
        ws = _get_budget_config_worksheet()
        dept = (ws.acell("B2").value or "").strip()
        name = (ws.acell("B3").value or "").strip()
        title = (ws.acell("B4").value or "").strip()
        if not dept and not name and not title:
            return None
        return {"부서": dept, "이름": name, "직책": title}
    except Exception:
        return None


def set_approver_info(dept: str, name: str, title: str):
    """결재자 정보를 B2,B3,B4에 저장, B5에 현재 연도 저장."""
    ws = _get_budget_config_worksheet()
    dept_s, name_s, title_s = (dept or "").strip(), (name or "").strip(), (title or "").strip()
    ws.update("B2:B5", [[dept_s], [name_s], [title_s], [str(datetime.now().year)]])


def check_approval_password(plain_password: str) -> bool:
    """입력한 비밀번호가 결재 비밀번호와 일치하는지 확인. 결재 비밀번호 미설정 시 False."""
    expected = get_approval_password()
    if expected is None:
        return False
    return plain_password == expected


def get_view_password():
    """조회용 비밀번호. C1. 저장 연도가 현재 연도가 아니면 None."""
    try:
        current_year = str(datetime.now().year)
        if _get_approval_config_year() != current_year:
            return None
        ws = _get_budget_config_worksheet()
        enc = ws.acell("C1").value
        if not enc or not enc.strip():
            return None
        return _get_fernet().decrypt(enc.strip().encode()).decode()
    except Exception:
        return None


def set_view_password(plain_password: str):
    """조회 비밀번호를 C1에 암호화 저장."""
    enc = _get_fernet().encrypt(plain_password.encode()).decode()
    _get_budget_config_worksheet().update_acell("C1", enc)


def check_view_or_approval_password(plain_password: str) -> bool:
    """입력한 비밀번호가 조회 비밀번호 또는 결재 비밀번호와 일치하면 True."""
    view_pw = get_view_password()
    approval_pw = get_approval_password()
    return check_view_or_approval_password_given(plain_password, view_pw, approval_pw)


def check_view_or_approval_password_given(plain_password: str, view_password: str | None, approval_password: str | None) -> bool:
    """입력 비밀번호가 조회 비밀번호 또는 결재 비밀번호와 일치하면 True. (API 호출 없음)"""
    if not plain_password:
        return False
    if view_password and plain_password == view_password:
        return True
    if approval_password and plain_password == approval_password:
        return True
    return False


def get_fingerprint_hash() -> str | None:
    """현재 요청의 단말(브라우저) 식별용 해시. 단말별 기본값 저장/로드에 사용."""
    return _get_fingerprint_hash()


def clear_budget_approval_config():
    """예산청구 config 시트의 조회·결재 관련 셀(B1:B5, C1) 초기화."""
    try:
        ws = _get_budget_config_worksheet()
        ws.batch_clear(["B1:B5", "C1"])
    except Exception:
        pass


def _get_sessions_worksheet():
    """'sessions' 시트 반환. 없으면 생성."""
    import gspread
    sheet = _client.open(_spreadsheet_name)
    try:
        return sheet.worksheet("sessions")
    except gspread.exceptions.WorksheetNotFound:
        sheet.add_worksheet(title="sessions", rows=2, cols=3)
        ws = sheet.worksheet("sessions")
        ws.update("A1:C1", [["sid", "exp", "typ"]])
        return ws


def _hash_session_id(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _add_session_to_sheet(session_id: str, exp_ts: float):
    ws = _get_sessions_worksheet()
    ws.append_row([_hash_session_id(session_id), str(int(exp_ts)), "s"])


def _is_session_valid_in_sheet(session_id: str, exp_ts: float) -> bool:
    if datetime.now().timestamp() >= exp_ts:
        return False
    try:
        ws = _get_sessions_worksheet()
        rows = ws.get_all_values()
        if not rows or len(rows) < 2:
            return False
        h = _hash_session_id(session_id)
        now_ts = int(datetime.now().timestamp())
        for row in rows[1:]:
            if len(row) >= 2 and row[0] == h and (len(row) < 3 or row[2] in ("", "s")):
                try:
                    return int(row[1]) >= now_ts
                except (ValueError, TypeError):
                    return False
        return False
    except Exception:
        return False


def _get_fingerprint_hash() -> str | None:
    try:
        headers = getattr(st.context, "headers", None) or {}
        if not headers and hasattr(st, "request") and hasattr(st.request, "headers"):
            headers = getattr(st.request, "headers", None) or {}
        header_lower = {}
        for k, v in getattr(headers, "items", lambda: [])():
            header_lower[str(k).lower()] = v
        parts = []
        for key in ("user-agent", "accept-language", "sec-ch-ua", "sec-ch-ua-platform"):
            v = header_lower.get(key)
            if v:
                parts.append(str(v).strip())
        if not parts:
            return None
        return hashlib.sha256("|".join(parts).encode()).hexdigest()
    except Exception:
        return None


def _add_fingerprint_to_sheet(fp_hash: str, exp_ts: float):
    ws = _get_sessions_worksheet()
    ws.append_row([fp_hash, str(int(exp_ts)), "f"])


def _is_fingerprint_valid_in_sheet(fp_hash: str) -> bool:
    try:
        ws = _get_sessions_worksheet()
        rows = ws.get_all_values()
        if not rows or len(rows) < 2:
            return False
        now_ts = datetime.now().timestamp()
        for row in rows[1:]:
            if len(row) >= 3 and row[2] == "f" and row[0] == fp_hash:
                try:
                    return int(row[1]) >= now_ts
                except (ValueError, TypeError):
                    return False
        return False
    except Exception:
        return False


def _create_session_token(session_id: str, exp_ts: float) -> str:
    payload = json.dumps({"id": session_id, "exp": exp_ts})
    return _get_fernet().encrypt(payload.encode()).decode()


def _validate_session_token(token_value: str):
    if not token_value or not token_value.strip():
        return None
    try:
        dec = _get_fernet().decrypt(token_value.strip().encode()).decode()
        data = json.loads(dec)
        sid, exp = data.get("id"), data.get("exp")
        if sid is None or exp is None:
            return None
        return (sid, float(exp))
    except Exception:
        return None


def check_password():
    """진입 비밀번호 확인. URL 세션·단말 지문 유효하면 생략. 실패 시 st.stop()."""
    if st.session_state.get("authenticated"):
        return True

    # 구글 시트 접속 전에 먼저 화면을 그려서 "기다리는 화면"만 나오지 않게 함
    with st.spinner("구글 시트에 연결 중..."):
        session_token = st.query_params.get("session")
        if session_token:
            try:
                parsed = _validate_session_token(session_token)
                if parsed:
                    session_id, exp_ts = parsed
                    if _is_session_valid_in_sheet(session_id, exp_ts):
                        st.session_state.authenticated = True
                        st.rerun()
            except Exception:
                pass

        fp_hash = _get_fingerprint_hash()
        if fp_hash and _is_fingerprint_valid_in_sheet(fp_hash):
            st.session_state.authenticated = True
            st.rerun()

        try:
            expected = get_stored_password()
        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception:
            st.error("구글 시트에 연결할 수 없습니다. 시트 이름·공유(서비스 계정)를 확인해 주세요.")
            st.stop()

    is_first_run = expected is None
    if is_first_run:
        expected = st.secrets.get("default_password")
        if not expected:
            st.error("최초 실행입니다. Secrets에 **default_password**를 설정해 주세요. (Streamlit Cloud: 설정 → Secrets)")
            st.stop()

    st.title("🔐 새에덴교회 중등1부 교사 도우미")
    st.markdown("접속하려면 비밀번호를 입력하세요.")
    with st.form("entry_form"):
        pw = st.text_input("비밀번호", type="password", key="entry_password")
        submitted = st.form_submit_button("입장")
    if submitted:
        if pw == expected:
            st.session_state.authenticated = True
            if is_first_run:
                st.session_state.must_change_password = True
            try:
                exp_ts = (datetime.now() + timedelta(days=SESSION_DAYS)).timestamp()
                session_id = secrets.token_urlsafe(32)
                _add_session_to_sheet(session_id, exp_ts)
                token = _create_session_token(session_id, exp_ts)
                st.query_params["session"] = token
                fp_hash = _get_fingerprint_hash()
                if fp_hash:
                    _add_fingerprint_to_sheet(fp_hash, exp_ts)
                st.session_state.show_bookmark_hint = True
            except Exception:
                pass
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()


def show_change_password_if_needed():
    """최초 로그인 후 비밀번호 변경 화면. 완료 시 st.stop() 유지."""
    if not st.session_state.get("must_change_password"):
        return
    st.title("🔐 비밀번호 변경")
    st.markdown("처음 사용이므로 비밀번호를 변경해 주세요.")
    p1 = st.text_input("새 비밀번호", type="password", key="new_pw1")
    p2 = st.text_input("새 비밀번호 확인", type="password", key="new_pw2")
    if st.button("비밀번호 저장"):
        if not p1 or not p2:
            st.error("새 비밀번호를 입력해 주세요.")
        elif p1 != p2:
            st.error("두 비밀번호가 일치하지 않습니다.")
        else:
            try:
                set_stored_password(p1)
                del st.session_state.must_change_password
                st.success("비밀번호가 변경되었습니다. 다음부터 새 비밀번호로 로그인하세요.")
                st.rerun()
            except Exception as e:
                st.error(f"저장 실패: {e}")
    st.stop()
