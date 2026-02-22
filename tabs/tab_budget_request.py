# -*- coding: utf-8 -*-
"""탭: 예산청구."""

import base64
import io
from datetime import date, datetime

import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

import auth
from config import PHOTO_B64_MAX
from photo_utils import image_to_base64_for_sheet
from sheets import (
    get_budget_request_ws,
    get_budget_requests_data,
    get_last_budget_defaults,
    get_next_budget_reg_no,
    get_students_data,
    invalidate_sheets_cache,
)

# 예산청구 탭 인덱스 (app.py TAB_LABELS 기준). rerun 후에도 이 탭이 선택되도록 함.
BUDGET_TAB_INDEX = 6


def _rerun_keep_tab():
    """결재 등으로 rerun 시 예산청구 탭이 유지되도록 세션에 저장 후 rerun."""
    st.session_state["_budget_tab_index"] = BUDGET_TAB_INDEX
    st.rerun()


# 청구 내용 옵션 (라벨, 시트 저장값)
CLAIM_CONTENT_OPTIONS = [
    "반친회",
    "찬양팀 연습간식",
    "전도축제",
    "새신자용",
    "수련회",
    "기타",
]

# 그룹명: 학년/반 또는 팀
GROUP_TYPE_OPTIONS = ["학년/반", "찬양팀", "미디어팀", "연극팀"]

MAX_EVIDENCES = 10


def _default_account():
    """입금계좌 기본값: 세션 유지 → 마지막 등록 건."""
    if "budget_last_account" in st.session_state and st.session_state.budget_last_account:
        return st.session_state.budget_last_account
    acc, _ = get_last_budget_defaults()
    return acc or ""


def _default_claimer():
    """청구자 기본값: 세션 유지 → 마지막 등록 건."""
    if "budget_last_claimer" in st.session_state and st.session_state.budget_last_claimer:
        return st.session_state.budget_last_claimer
    _, claimer = get_last_budget_defaults()
    return claimer or ""


def _evidence_list():
    if "budget_evidence_list" not in st.session_state:
        st.session_state.budget_evidence_list = []
    return st.session_state.budget_evidence_list


def _render_list_view():
    """조회 화면 1단계: 리스트 (날짜, 청구 내용, 비용, 청구인, 승인 여부). 항목 선택 후 상세보기로 이동."""
    if st.button("← 신청 화면으로", key="budget_back_to_form"):
        st.session_state.budget_view = "form"
        if "budget_view_authenticated" in st.session_state:
            del st.session_state["budget_view_authenticated"]
        if "budget_selected_reg_no" in st.session_state:
            del st.session_state["budget_selected_reg_no"]
        _rerun_keep_tab()

    st.subheader("예산청구 리스트")
    df = get_budget_requests_data()
    if df.empty:
        st.info("등록된 예산 청구가 없습니다.")
        return

    def _fmt_amount(val):
        """숫자를 3자리마다 콤마 포맷 (예: 1000000 -> 1,000,000)."""
        try:
            return f"{int(float(val)):,}"
        except (ValueError, TypeError):
            return str(val) if val else ""

    date_col = "청구날짜" if "청구날짜" in df.columns else "지출날짜"
    n = len(df)
    raw_amounts = df["청구금액"] if "청구금액" in df.columns else pd.Series([""] * n)
    list_df = pd.DataFrame({
        "날짜": df[date_col] if date_col in df.columns else [""] * n,
        "청구 내용": df["청구내용"].astype(str) if "청구내용" in df.columns else [""] * n,
        "그룹명": df["그룹명"].astype(str) if "그룹명" in df.columns else [""] * n,
        "비용": raw_amounts.apply(_fmt_amount),
        "청구인": df["청구자"].astype(str) if "청구자" in df.columns else [""] * n,
        "승인 여부": df["결재상태"].fillna("대기").astype(str).str.strip() if "결재상태" in df.columns else ["대기"] * n,
    })
    st.dataframe(list_df, use_container_width=True, hide_index=True)

    # 항목 선택 후 상세보기 스텝으로
    reg_nos = df["등록번호"].astype(str).tolist()
    dates = list_df["날짜"].astype(str).tolist()
    contents = list_df["청구 내용"].astype(str).tolist()
    groups = list_df["그룹명"].tolist()
    amounts = list_df["비용"].tolist()
    claimers = list_df["청구인"].tolist()
    statuses = list_df["승인 여부"].tolist()

    def _label(i: int) -> str:
        c = str(contents[i] if i < len(contents) else "")
        c = c[:20] + ("…" if len(c) > 20 else "")
        grp = str(groups[i] if i < len(groups) else "")
        amt = amounts[i] if i < len(amounts) else ""
        cl = str(claimers[i] if i < len(claimers) else "")
        return f"등록번호 {reg_nos[i]} | {dates[i]} | {c} | {grp} | {amt}원 | {cl} | {statuses[i]}"

    sel_idx = st.selectbox(
        "상세보기할 건을 선택하세요",
        range(len(reg_nos)),
        key="budget_list_selection",
        format_func=_label,
    )
    if st.button("상세보기", type="primary", key="budget_go_detail"):
        st.session_state.budget_view = "detail"
        st.session_state.budget_selected_reg_no = reg_nos[sel_idx]
        _rerun_keep_tab()


def _safe(s: str) -> str:
    """HTML 이스케이프."""
    if s is None or not isinstance(s, str):
        s = str(s) if s is not None else ""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _print_html(reg_no: str, row, ev_b64_list: list) -> str:
    """A4 한 장 인쇄용 예산 청구서 HTML (기준용지 A4, 글씨 검정, 상단 정렬, 증빙 하단 최대 크기)."""
    def v(key):
        x = row.get(key)
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return "-"
        s = str(x).strip()
        return _safe(s) if s and s.lower() != "nan" else "-"

    info = auth.get_approver_info()
    confirmer = (
        f"{info['부서']} {info['이름']} {info['직책']}".strip()
        if info and (info.get("부서") or info.get("이름") or info.get("직책"))
        else "-"
    )

    ev_html = ""
    if ev_b64_list:
        ev_items = []
        for i, b64 in enumerate(ev_b64_list[:6]):
            ev_items.append(f'<div class="print-ev-item"><span class="print-ev-label">증빙 {i+1}</span><img src="data:image/jpeg;base64,{b64}" alt="증빙{i+1}" class="print-ev-img"/></div>')
        ev_html = '<div class="print-ev-section"><p class="print-ev-title">증빙</p><div class="print-ev-row">' + "".join(ev_items) + "</div></div>"
    else:
        ev_html = '<div class="print-ev-section"></div>'

    return f"""
<style id="budget-print-styles">
  /* 화면·인쇄·PDF 동일 비율: A4 210×297mm, 내부 여백 15mm → 내용 영역 180×267mm */
  #budget-print-area {{ width: 210mm; height: 297mm; margin: 0 auto; padding: 15mm; font-family: inherit; background: #fff; box-sizing: border-box; color: #000; display: flex; flex-direction: column; align-items: stretch; vertical-align: top; max-width: 100%; }}
  #budget-print-area * {{ color: #000; box-sizing: border-box; }}
  #budget-print-area .print-top {{ flex: 0 0 auto; vertical-align: top; }}
  #budget-print-area .print-title {{ font-size: 1.8rem; font-weight: 700; text-align: center; margin: 0 0 16px 0; color: #000; }}
  #budget-print-area table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; color: #000; table-layout: fixed; }}
  #budget-print-area th, #budget-print-area td {{ border: 1px solid #000; padding: 6px 10px; vertical-align: top; color: #000; }}
  #budget-print-area th {{ width: 28%; background: #f0f0f0; font-weight: 600; color: #000; text-align: center; }}
  #budget-print-area td {{ text-align: left; }}
  #budget-print-area .print-footer {{ margin: 12px 0 0 0; text-align: right; font-size: 1rem; color: #000; }}
  #budget-print-area .print-ev-section {{ flex: 1; min-height: 0; min-width: 0; width: 100%; margin-top: auto; display: flex; flex-direction: column; justify-content: flex-end; overflow: hidden; }}
  #budget-print-area .print-ev-title {{ flex: 0 0 auto; font-weight: 600; margin: 2px 0 1px 0; font-size: 0.95rem; color: #000; }}
  #budget-print-area .print-ev-row {{ flex: 1; min-height: 0; min-width: 0; width: 100%; display: flex; flex-direction: row; align-items: stretch; justify-content: flex-start; gap: 1mm; overflow: hidden; }}
  #budget-print-area .print-ev-item {{ flex: 1; min-width: 0; padding: 0; display: flex; flex-direction: column; align-items: center; text-align: center; overflow: hidden; border: 1px solid #000; box-sizing: border-box; }}
  #budget-print-area .print-ev-label {{ flex: 0 0 auto; font-size: 0.7rem; color: #000; margin: 0; padding: 0 1px; }}
  #budget-print-area .print-ev-img {{ flex: 1; min-height: 0; min-width: 0; width: 100%; height: 100%; object-fit: contain; object-position: center; display: block; border: none; margin: 0; padding: 0; }}
  .budget-print-sheet {{ box-shadow: 0 2px 12px rgba(0,0,0,0.15); overflow: hidden; }}
  .budget-print-inner {{ display: flex; flex-direction: column; align-items: stretch; flex: 1; min-height: 0; width: 100%; min-width: 0; overflow: hidden; }}
  @media print {{
    @page {{ size: A4; margin: 0; }}
    html, body {{ margin: 0 !important; padding: 0 !important; background: #fff !important; min-height: 0 !important; }}
    body * {{ visibility: hidden; }}
    #budget-print-area, #budget-print-area * {{ visibility: visible; color: #000 !important; }}
    #budget-print-area {{ position: fixed !important; left: 0 !important; top: 0 !important; width: 210mm !important; height: 297mm !important; padding: 15mm !important; overflow: hidden; box-sizing: border-box; background: #fff !important; box-shadow: none; margin: 0 !important; }}
    #budget-print-area .budget-print-inner {{ width: 100% !important; height: 100% !important; transform: none; padding: 0; flex: 1; min-height: 0; }}
    #budget-print-area .print-title {{ font-size: 1.5rem; margin: 0 0 10px 0; color: #000; }}
    #budget-print-area table {{ font-size: 0.8rem; color: #000; }}
    #budget-print-area th, #budget-print-area td {{ padding: 5px 8px; color: #000; vertical-align: top; }}
    #budget-print-area th {{ text-align: center; }}
    #budget-print-area td {{ text-align: left; }}
    #budget-print-area .print-ev-section {{ flex: 1; min-height: 0; min-width: 0; width: 100%; overflow: hidden; }}
    #budget-print-area .print-ev-row {{ flex: 1; min-height: 0; min-width: 0; width: 100%; overflow: hidden; }}
    #budget-print-area .print-ev-item {{ overflow: hidden; }}
    #budget-print-area .print-ev-img {{ flex: 1; min-height: 0; min-width: 0; width: 100%; height: 100%; object-fit: contain; object-position: center; }}
    #budget-print-area .print-footer {{ color: #000; }}
  }}
</style>
<div class="budget-print-sheet" id="budget-print-area">
  <div class="budget-print-inner">
  <div class="print-top">
    <h1 class="print-title">예산 청구서</h1>
    <table>
      <tr><th>등록번호</th><td>{_safe(str(reg_no))}</td></tr>
      <tr><th>지출 날짜</th><td>{v("지출날짜")}</td></tr>
      <tr><th>청구 내용</th><td>{v("청구내용")}</td></tr>
      <tr><th>청구 금액</th><td>{v("청구금액")}</td></tr>
      <tr><th>그룹명</th><td>{v("그룹명")}</td></tr>
      <tr><th>해당 인원수 (명)</th><td>{v("인원수")}</td></tr>
      <tr><th>세부 내역</th><td>{v("세부내역")}</td></tr>
      <tr><th>입금 계좌</th><td>{v("입금계좌")}</td></tr>
      <tr><th>청구 날짜</th><td>{v("청구날짜")}</td></tr>
      <tr><th>청구자</th><td>{v("청구자")}</td></tr>
      <tr><th>결재상태</th><td>{v("결재상태")}</td></tr>
      <tr><th>결재일시</th><td>{v("결재일시")}</td></tr>
    </table>
    <p class="print-footer">확인자: {_safe(confirmer)}</p>
  </div>
  {ev_html}
  </div>
</div>
"""


def _render_detail_view(reg_no: str):
    """조회 화면 2단계: 인쇄 보기(청구서 양식) + 승인."""
    st.markdown(
        "<style>.main .block-container { padding: 0 !important; max-width: 100% !important; }</style>",
        unsafe_allow_html=True,
    )
    if st.button("← 목록으로", key="budget_back_to_list"):
        st.session_state.budget_view = "list"
        if "budget_selected_reg_no" in st.session_state:
            del st.session_state["budget_selected_reg_no"]
        _rerun_keep_tab()

    df = get_budget_requests_data()
    match = df[df["등록번호"].astype(str) == str(reg_no)]
    if match.empty:
        st.warning("해당 건을 찾을 수 없습니다.")
        return
    row = match.iloc[0]
    ev_labels = [f"증빙{i}" for i in range(1, MAX_EVIDENCES + 1)]
    ev_b64_list = [row.get(lbl) for lbl in ev_labels if row.get(lbl)]

    st.markdown(_print_html(reg_no, row, ev_b64_list), unsafe_allow_html=True)
    st.caption("**Ctrl+P** (Mac: **Cmd+P**)로 현재 화면을 인쇄하세요.")

    status = str(row.get("결재상태", "")).strip()
    if status in ("", "대기"):
        st.divider()
        st.caption("위 청구서 확인 후 결재 비밀번호를 입력하고 승인하세요.")
        approve_pw = st.text_input("결재 비밀번호", type="password", key="budget_approve_pw_detail", placeholder="결재 비밀번호 입력")
        if st.button("승인 (결재)", key="budget_approve_btn_detail"):
            ok, msg = _do_approve(reg_no, approve_pw or "")
            if ok:
                st.success(msg)
                _rerun_keep_tab()
            else:
                st.error(msg)
    else:
        st.info("이미 승인된 건입니다.")


def _do_approve(reg_no_sel: str, approve_pw: str) -> tuple[bool, str]:
    """해당 등록번호 건을 승인. (성공 여부, 메시지) 반환. 결재 비밀번호 일치 시에만 승인."""
    if not approve_pw:
        return False, "결재 비밀번호를 입력해 주세요."
    if not auth.check_approval_password(approve_pw):
        return False, "결재 비밀번호가 일치하지 않습니다."
    try:
        ws = get_budget_request_ws()
        all_rows = ws.get_all_values()
        if len(all_rows) < 2:
            return False, "데이터를 찾을 수 없습니다."
        headers = all_rows[0]
        try:
            col_status = headers.index("결재상태") + 1
            col_date = headers.index("결재일시") + 1
        except ValueError:
            return False, "시트 형식이 맞지 않습니다."
        for i in range(1, len(all_rows)):
            if str(all_rows[i][0]).strip() == str(reg_no_sel).strip():
                row_num = i + 1
                ws.update_cell(row_num, col_status, "승인")
                ws.update_cell(row_num, col_date, datetime.now().strftime("%Y-%m-%d %H:%M"))
                invalidate_sheets_cache()
                get_budget_requests_data.clear()
                return True, f"등록번호 {reg_no_sel} 건이 승인되었습니다."
        return False, "해당 등록번호를 찾을 수 없습니다."
    except Exception as e:
        return False, f"승인 처리 실패: {e}"


def render(tab):
    with tab:
        st.title("💰 예산청구")

        # ----- 설정 한 번에 읽기 (API 호출 1회로 일관된 판단) -----
        config = auth.get_budget_config()
        need_setup = not config["year_ok"] or config["approval_password"] is None
        budget_view = st.session_state.get("budget_view")
        budget_view_authenticated = st.session_state.get("budget_view_authenticated")

        # ----- 비밀번호 미설정 시: 설정 화면 (단, 이미 조회/상세에 인증된 상태면 설정창으로 끌어내지 않음) -----
        if need_setup:
            if budget_view in ("list", "detail") and budget_view_authenticated:
                # 조회·상세에 이미 들어온 상태면 설정창 안 띄우고 그대로 목록/상세 유지
                pass
            else:
                if budget_view in ("list", "detail"):
                    st.session_state.budget_view = "form"
                    if "budget_view_authenticated" in st.session_state:
                        del st.session_state["budget_view_authenticated"]
                    if "budget_selected_reg_no" in st.session_state:
                        del st.session_state["budget_selected_reg_no"]
                    _rerun_keep_tab()
                with st.expander("🔐 비밀번호 및 결재자 정보 설정 (최초 1회 또는 매년 1월)", expanded=True):
                    st.caption("예산 청구 메뉴 사용을 위해 아래를 입력한 뒤 저장하세요. **매년 1월 1일에 초기화**됩니다.")
                    st.markdown("**조회 비밀번호** — 리스트 조회·상세 조회 진입용")
                    view_pw1 = st.text_input("조회 비밀번호", type="password", key="budget_view_pw_1", placeholder="조회 비밀번호")
                    view_pw2 = st.text_input("조회 비밀번호 확인", type="password", key="budget_view_pw_2", placeholder="다시 입력")
                    st.markdown("**결재 비밀번호** — 조회 및 결재(승인)용")
                    app_pw1 = st.text_input("결재 비밀번호", type="password", key="budget_approval_pw_1", placeholder="결재 비밀번호")
                    app_pw2 = st.text_input("결재 비밀번호 확인", type="password", key="budget_approval_pw_2", placeholder="다시 입력")
                    st.markdown("**결재자 정보** — 청구서 하단 확인자 표시용 (예: 중등1부 / 홍길동 / 부장)")
                    app_dept = st.text_input("부서", key="budget_approver_dept", placeholder="예: 중등1부")
                    app_name = st.text_input("이름", key="budget_approver_name", placeholder="예: 홍길동")
                    app_title = st.text_input("직책", key="budget_approver_title", placeholder="예: 부장")
                    if st.button("저장", key="budget_save_config"):
                        err = None
                        if not view_pw1 or not view_pw2:
                            err = "조회 비밀번호를 입력해 주세요."
                        elif view_pw1 != view_pw2:
                            err = "조회 비밀번호가 일치하지 않습니다."
                        elif not app_pw1 or not app_pw2:
                            err = "결재 비밀번호를 입력해 주세요."
                        elif app_pw1 != app_pw2:
                            err = "결재 비밀번호가 일치하지 않습니다."
                        elif not app_dept or not app_name or not app_title:
                            err = "부서, 이름, 직책을 모두 입력해 주세요."
                        if err:
                            st.error(err)
                        else:
                            try:
                                auth.set_approval_password(app_pw1)
                                auth.set_approver_info(app_dept, app_name, app_title)
                                auth.set_view_password(view_pw1)
                                st.session_state.budget_view = "form"
                                st.session_state.budget_view_authenticated = True
                                st.success("설정이 저장되었습니다. 이제 예산 청구 신청과 조회를 사용할 수 있습니다.")
                                _rerun_keep_tab()
                            except Exception as e:
                                st.error(f"저장 실패: {e}")
                st.divider()
                return

        # ----- 조회 진입 시: 조회 비밀번호 또는 결재 비밀번호 입력 (동일 config로 검증) -----
        if budget_view == "list":
            if not budget_view_authenticated:
                view_pw = config["view_password"]
                apw = config["approval_password"]
                if view_pw is None and apw is None:
                    st.warning("비밀번호가 설정되지 않았습니다. 위에서 비밀번호를 설정해 주세요.")
                    if st.button("확인", key="budget_gate_ok"):
                        st.session_state.budget_view = "form"
                        _rerun_keep_tab()
                    return
                st.subheader("예산 청구 조회")
                st.caption("조회 비밀번호 또는 결재 비밀번호를 입력하세요.")
                gate_pw = st.text_input("비밀번호", type="password", key="budget_view_gate_pw", placeholder="비밀번호 입력")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("들어가기", key="budget_view_gate_btn", type="primary"):
                        if auth.check_view_or_approval_password_given(gate_pw or "", view_pw, apw):
                            st.session_state.budget_view_authenticated = True
                            _rerun_keep_tab()
                        else:
                            st.error("비밀번호가 일치하지 않습니다.")
                with col2:
                    if st.button("취소", key="budget_view_gate_cancel"):
                        st.session_state.budget_view = "form"
                        _rerun_keep_tab()
                return
            _render_list_view()
            return
        if st.session_state.get("budget_view") == "detail":
            reg_no = st.session_state.get("budget_selected_reg_no")
            if reg_no:
                _render_detail_view(reg_no)
            else:
                st.session_state.budget_view = "list"
                _rerun_keep_tab()
            return

        st.subheader("예산 청구 신청")

        if st.session_state.pop("budget_show_registered_message", False):
            st.success("등록되었습니다.")
            # 위젯이 이번 런에서 기본값을 쓰도록 session_state에 명시적으로 설정
            st.session_state["budget_expense_date"] = date.today()
            st.session_state["budget_claim_content"] = CLAIM_CONTENT_OPTIONS[0]
            st.session_state["budget_claim_amount"] = 0
            st.session_state["budget_detail"] = ""
            st.session_state["budget_claim_date"] = date.today()
            st.session_state["budget_group_type"] = GROUP_TYPE_OPTIONS[0]
            st.session_state["budget_headcount"] = 0
            if "budget_claim_extra" in st.session_state:
                del st.session_state["budget_claim_extra"]
            if "budget_grade" in st.session_state:
                del st.session_state["budget_grade"]
            if "budget_class" in st.session_state:
                del st.session_state["budget_class"]

        # ----- 폼 필드 -----
        expense_date = st.date_input(
            "지출 날짜",
            value=st.session_state.get("budget_expense_date", date.today()),
            key="budget_expense_date",
            format="YYYY-MM-DD",
        )
        _claim_default = st.session_state.get("budget_claim_content", CLAIM_CONTENT_OPTIONS[0])
        _claim_index = CLAIM_CONTENT_OPTIONS.index(_claim_default) if _claim_default in CLAIM_CONTENT_OPTIONS else 0
        claim_content_sel = st.selectbox(
            "청구 내용",
            CLAIM_CONTENT_OPTIONS,
            index=_claim_index,
            key="budget_claim_content",
        )
        claim_content_extra = ""
        if claim_content_sel == "기타":
            claim_content_extra = st.text_input("기타 내용을 입력하세요", key="budget_claim_extra", placeholder="예: OO 행사 비용")
        claim_content_value = claim_content_extra.strip() if claim_content_sel == "기타" else claim_content_sel

        claim_amount = st.number_input(
            "청구 금액 (원) *",
            min_value=0,
            step=100,
            value=st.session_state.get("budget_claim_amount", 0),
            key="budget_claim_amount",
            help="필수 입력",
        )
        detail_note = st.text_area(
            "구체적인 세부 내역",
            value=st.session_state.get("budget_detail", ""),
            key="budget_detail",
            placeholder="사용처를 구체적으로 기록해 주세요. (예: OO 장소 간식비, OO 비품 구입 등)",
            help="사용처를 구체적으로 기록해 주세요.",
        )
        account = st.text_input(
            "입금 계좌 *",
            value=st.session_state.get("budget_account", _default_account()),
            key="budget_account",
            placeholder="예: 신한 110-xxx-xxxxx 예금주명",
            help="필수 입력",
        )
        claim_date = st.date_input(
            "청구 날짜",
            value=st.session_state.get("budget_claim_date", date.today()),
            key="budget_claim_date",
            format="YYYY-MM-DD",
        )
        claimer = st.text_input(
            "청구자 *",
            value=st.session_state.get("budget_claimer", _default_claimer()),
            key="budget_claimer",
            placeholder="청구자 성함",
            help="필수 입력",
        )

        # ----- 그룹명 (학년/반 또는 팀) -----
        group_type = st.radio("그룹명", GROUP_TYPE_OPTIONS, key="budget_group_type", horizontal=True)
        group_name_value = ""
        if group_type == "학년/반":
            try:
                students_data = get_students_data()
                grade_list = sorted(students_data["학년"].dropna().unique().tolist(), key=str)
                grade_options = [str(g) for g in grade_list]
                if not grade_options:
                    st.caption("학년/반 데이터가 없습니다.")
                else:
                    sel_grade_idx = st.selectbox("학년", range(len(grade_options)), format_func=lambda i: grade_options[i], key="budget_grade")
                    selected_grade = grade_options[sel_grade_idx]
                    filtered = students_data[students_data["학년"].astype(str) == str(selected_grade)]
                    class_list = sorted(filtered["반"].dropna().unique().tolist(), key=str)
                    class_options = [str(c) for c in class_list]
                    if not class_options:
                        group_name_value = f"{selected_grade}학년"
                    else:
                        sel_class_idx = st.selectbox("반", range(len(class_options)), format_func=lambda i: class_options[i], key="budget_class")
                        selected_class = class_options[sel_class_idx]
                        group_name_value = f"{selected_grade}학년 {selected_class}반"
            except Exception:
                pass
        else:
            group_name_value = group_type  # 찬양팀, 미디어팀, 연극팀

        headcount = st.number_input(
            "해당 인원수 (명)",
            min_value=0,
            step=1,
            value=st.session_state.get("budget_headcount", 0),
            key="budget_headcount",
        )

        # ----- 증빙 첨부 (여러 개, 파일/촬영 + crop) -----
        st.subheader("증빙 첨부")
        st.caption("사진을 추가한 뒤, 기본 크기로 표시되는 사각형을 드래그해 위치·크기를 자유롭게 조절하고 유효 영역을 잘라내세요. 여러 장 첨부 가능합니다.")
        ev_list = _evidence_list()
        for i, b64 in enumerate(ev_list):
            col1, col2 = st.columns([3, 1])
            with col1:
                try:
                    raw = base64.b64decode(b64)
                    st.image(raw, caption=f"증빙 {i + 1}", use_container_width=True)
                except Exception:
                    st.caption(f"증빙 {i + 1} (미리보기 불가)")
            with col2:
                if st.button("삭제", key=f"budget_ev_del_{i}"):
                    ev_list.pop(i)
                    _rerun_keep_tab()

        if len(ev_list) < MAX_EVIDENCES:
            with st.expander("➕ 증빙 추가 (파일 또는 촬영 후 영역 선택)", expanded=True):
                ev_source = st.radio("입력 방법", ["파일에서 선택", "카메라로 촬영"], key="budget_ev_source", horizontal=True, label_visibility="collapsed")
                ev_bytes = None
                ev_mime = "image/jpeg"
                if ev_source == "파일에서 선택":
                    ev_file = st.file_uploader("이미지 선택", type=["png", "jpg", "jpeg", "webp"], key="budget_ev_file")
                    if ev_file:
                        ev_bytes = ev_file.getvalue()
                        ev_mime = ev_file.type or "image/jpeg"
                else:
                    ev_cam = st.camera_input("카메라로 촬영", key="budget_ev_camera")
                    if ev_cam:
                        ev_bytes = ev_cam.getvalue()
                        ev_mime = ev_cam.type or "image/jpeg"

                if ev_bytes:
                    try:
                        img = Image.open(io.BytesIO(ev_bytes))
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        st.caption("기본 크기의 사각형이 표시됩니다. 드래그로 위치와 크기를 자유롭게 조절한 뒤, 원하는 영역을 잘라내세요.")
                        cropped = st_cropper(
                            img,
                            aspect_ratio=None,
                            realtime_update=True,
                            box_color="#0066cc",
                        )
                        if cropped is not None and st.button("이 증빙 목록에 추가", key="budget_ev_add_btn"):
                            out = io.BytesIO()
                            cropped.save(out, format="JPEG", quality=85, optimize=True)
                            b64_new = base64.b64encode(out.getvalue()).decode("ascii")
                            if len(b64_new) > PHOTO_B64_MAX:
                                b64_new = image_to_base64_for_sheet(out.getvalue(), "image/jpeg")
                            ev_list.append(b64_new)
                            for k in ("budget_ev_file", "budget_ev_camera", "budget_ev_source"):
                                if k in st.session_state:
                                    del st.session_state[k]
                            _rerun_keep_tab()
                    except Exception:
                        st.caption("사진을 불러올 수 없습니다.")

        st.divider()

        # ----- 예산 청구 등록 버튼 -----
        if st.button("예산 청구 등록", type="primary", key="budget_submit"):
            account_stripped = (account or "").strip()
            claimer_stripped = (claimer or "").strip()
            if claim_amount == 0:
                st.error("청구 금액을 입력해 주세요.")
            elif not account_stripped:
                st.error("입금 계좌를 입력해 주세요.")
            elif not claimer_stripped:
                st.error("청구자를 입력해 주세요.")
            else:
                try:
                    reg_no = get_next_budget_reg_no()
                    ws = get_budget_request_ws()
                    row = [
                        str(reg_no),
                        expense_date.strftime("%Y-%m-%d"),
                        claim_content_value,
                        str(claim_amount),
                        detail_note.strip(),
                        account_stripped,
                        claim_date.strftime("%Y-%m-%d"),
                        claimer_stripped,
                        group_name_value,
                        str(headcount),
                        "대기",
                        "",
                    ]
                    ev_cols = [""] * MAX_EVIDENCES
                    for i, b64 in enumerate(ev_list):
                        if i < MAX_EVIDENCES:
                            ev_cols[i] = b64
                    row.extend(ev_cols)
                    ws.append_row(row)
                    invalidate_sheets_cache()
                    get_budget_requests_data.clear()
                    st.session_state.budget_last_account = account_stripped
                    st.session_state.budget_last_claimer = claimer_stripped
                    # 폼 초기화: 청구 금액·세부내역·그룹명 등 모든 입력창 리셋
                    form_keys = (
                        "budget_expense_date", "budget_claim_content", "budget_claim_extra",
                        "budget_claim_amount", "budget_detail", "budget_account",
                        "budget_claim_date", "budget_claimer", "budget_group_type",
                        "budget_grade", "budget_class", "budget_headcount",
                        "budget_ev_source", "budget_ev_file", "budget_ev_camera",
                        "budget_ev_add_btn", "budget_ev_aspect",
                    )
                    for key in form_keys:
                        st.session_state.pop(key, None)
                    keep = {"budget_last_account", "budget_last_claimer", "budget_view"}
                    for key in list(st.session_state.keys()):
                        if key.startswith("budget_") and key not in keep:
                            del st.session_state[key]
                    st.session_state.budget_evidence_list = []
                    st.session_state.budget_show_registered_message = True
                    _rerun_keep_tab()
                except Exception as e:
                    st.error(f"등록 실패: {e}")

        st.divider()
        if st.button("📋 조회", key="budget_btn_list"):
            st.session_state.budget_view = "list"
            if "budget_selected_reg_no" in st.session_state:
                del st.session_state["budget_selected_reg_no"]
            _rerun_keep_tab()
