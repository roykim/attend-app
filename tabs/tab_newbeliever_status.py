# -*- coding: utf-8 -*-
"""탭 5: 새신자 현황 (조회·추가·수정)."""

import base64
import io
from datetime import date

import pandas as pd
import streamlit as st

from config import PHOTO_WIDTH
from photo_utils import image_to_base64_for_sheet
from sheets import (
    ensure_students_photo_column,
    get_new_believers_ws,
    get_students_data,
    get_students_ws,
)


def _parse_date(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return date.today()
    if hasattr(v, "year"):
        return v
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return date.today()


def render(tab):
    students_data = get_students_data()
    try:
        nb_ws = get_new_believers_ws()
        nb_records = nb_ws.get_all_records()
    except Exception:
        st.warning("새신자 데이터를 불러올 수 없습니다.")
        st.stop()

    nb_grade_list = sorted(students_data["학년"].dropna().unique().tolist(), key=str)
    nb_grade_options = ["(미배정)"] + [str(x) for x in nb_grade_list]
    nb_class_options_by_grade = {}
    for g in nb_grade_list:
        fc = students_data[students_data["학년"] == g]
        nb_class_options_by_grade[str(g)] = ["(미배정)"] + [str(x) for x in sorted(fc["반"].dropna().unique().tolist(), key=str)]

    with tab:
        st.title("📋 새신자 현황")

        with st.expander("➕ 새 신자 추가", expanded=False):
            add_reg_date = st.date_input("등록일", value=date.today(), key="nb_add_reg_date")
            add_name = st.text_input("이름 *", key="nb_add_name", placeholder="이름을 입력하세요")
            add_phone = st.text_input("전화", key="nb_add_phone", placeholder="010-0000-0000")
            add_birth = st.text_input("생년월일", key="nb_add_birth", placeholder="예: 1990-01-15")
            add_address = st.text_input("주소", key="nb_add_address", placeholder="주소를 입력하세요")
            add_friend = st.text_input("전도한 친구 이름", key="nb_add_friend", placeholder="전도한 분 이름")
            add_photo_file = st.file_uploader("사진 (선택)", type=["png", "jpg", "jpeg", "webp"], key="nb_add_photo")
            add_sel_grade_idx = st.selectbox("학년", range(len(nb_grade_options)), format_func=lambda i: str(nb_grade_options[i]), key="nb_add_grade")
            add_selected_grade = None if nb_grade_options[add_sel_grade_idx] == "(미배정)" else nb_grade_options[add_sel_grade_idx]
            add_class_list = nb_class_options_by_grade.get(str(add_selected_grade), ["(미배정)"]) if add_selected_grade else ["(미배정)"]
            add_sel_class_idx = st.selectbox("반", range(len(add_class_list)), format_func=lambda i: str(add_class_list[i]), key="nb_add_class")
            add_selected_class = None if not add_class_list or add_class_list[add_sel_class_idx] == "(미배정)" else add_class_list[add_sel_class_idx]
            if st.button("등록하기", key="nb_add_submit"):
                if not (add_name and add_name.strip()):
                    st.error("이름을 입력해 주세요.")
                else:
                    try:
                        photo_b64 = ""
                        if add_photo_file:
                            photo_b64 = image_to_base64_for_sheet(add_photo_file.getvalue(), add_photo_file.type or "image/jpeg")
                        row = [
                            add_reg_date.strftime("%Y-%m-%d"), add_name.strip(),
                            add_phone.strip() if add_phone else "", add_birth.strip() if add_birth else "",
                            add_address.strip() if add_address else "", add_friend.strip() if add_friend else "",
                            str(add_selected_grade) if add_selected_grade else "", str(add_selected_class) if add_selected_class else "",
                            photo_b64,
                        ]
                        nb_ws.append_row(row)
                        if add_selected_grade and add_selected_class:
                            students_ws = get_students_ws()
                            ensure_students_photo_column(students_ws)
                            existing = pd.DataFrame(students_ws.get_all_records())
                            already = (
                                existing["학년"].astype(str).eq(str(add_selected_grade))
                                & existing["반"].astype(str).eq(str(add_selected_class))
                                & existing["이름"].astype(str).eq(add_name.strip())
                            )
                            if not already.any():
                                headers = existing.columns.tolist()
                                row_map = {"학년": add_selected_grade, "반": add_selected_class, "이름": add_name.strip(), "사진": photo_b64, "사진URL": photo_b64}
                                for col in ["전화번호", "휴대전화", "연락처"]:
                                    if col in headers:
                                        row_map[col] = add_phone.strip() if add_phone else ""
                                        break
                                student_row = [str(row_map.get(h, "")) for h in headers]
                                students_ws.append_row(student_row)
                                get_students_data.clear()
                            else:
                                get_students_data.clear()
                        st.success("새신자가 등록되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"등록 실패: {e}")

        if st.session_state.get("nb_edit_sheet_row") is not None:
            edit_row = st.session_state["nb_edit_sheet_row"]
            edit_data = st.session_state.get("nb_edit_data") or {}
            st.subheader(f"✏️ 수정: {edit_data.get('이름', '')}")
            e_reg_date = st.date_input("등록일", value=_parse_date(edit_data.get("등록일")), key="nb_edit_reg_date")
            e_name = st.text_input("이름 *", value=str(edit_data.get("이름") or ""), key="nb_edit_name")
            e_phone = st.text_input("전화", value=str(edit_data.get("전화") or ""), key="nb_edit_phone")
            e_birth = st.text_input("생년월일", value=str(edit_data.get("생년월일") or ""), key="nb_edit_birth")
            e_address = st.text_input("주소", value=str(edit_data.get("주소") or ""), key="nb_edit_address")
            e_friend = st.text_input("전도한 친구 이름", value=str(edit_data.get("전도한친구이름") or ""), key="nb_edit_friend")
            e_photo_file = st.file_uploader("사진 변경 (선택, 비우면 기존 유지)", type=["png", "jpg", "jpeg", "webp"], key="nb_edit_photo")
            g_val = str(edit_data.get("학년") or "")
            c_val = str(edit_data.get("반") or "")
            try:
                e_grade_idx = nb_grade_options.index(g_val) if g_val and g_val in nb_grade_options else 0
            except ValueError:
                e_grade_idx = 0
            e_sel_grade_idx = st.selectbox("학년", range(len(nb_grade_options)), index=min(e_grade_idx, len(nb_grade_options) - 1), format_func=lambda i: str(nb_grade_options[i]), key="nb_edit_grade")
            e_selected_grade = None if nb_grade_options[e_sel_grade_idx] == "(미배정)" else nb_grade_options[e_sel_grade_idx]
            e_class_list = nb_class_options_by_grade.get(str(e_selected_grade), ["(미배정)"]) if e_selected_grade else ["(미배정)"]
            try:
                e_class_idx = e_class_list.index(c_val) if c_val and c_val in e_class_list else 0
            except ValueError:
                e_class_idx = 0
            e_sel_class_idx = st.selectbox("반", range(len(e_class_list)), index=min(e_class_idx, len(e_class_list) - 1), format_func=lambda i: str(e_class_list[i]), key="nb_edit_class")
            e_selected_class = None if not e_class_list or e_class_list[e_sel_class_idx] == "(미배정)" else e_class_list[e_sel_class_idx]
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("저장", key="nb_edit_save"):
                    if not (e_name and e_name.strip()):
                        st.error("이름을 입력해 주세요.")
                    else:
                        try:
                            photo_b64 = (edit_data.get("사진") or edit_data.get("사진URL") or "")
                            if e_photo_file:
                                photo_b64 = image_to_base64_for_sheet(e_photo_file.getvalue(), e_photo_file.type or "image/jpeg")
                            row_vals = [
                                e_reg_date.strftime("%Y-%m-%d"), e_name.strip(),
                                e_phone.strip() if e_phone else "", e_birth.strip() if e_birth else "",
                                e_address.strip() if e_address else "", e_friend.strip() if e_friend else "",
                                str(e_selected_grade) if e_selected_grade else "", str(e_selected_class) if e_selected_class else "",
                                photo_b64,
                            ]
                            nb_ws.update(f"A{edit_row}:I{edit_row}", [row_vals])
                            for key in ("nb_edit_sheet_row", "nb_edit_data"):
                                if key in st.session_state:
                                    del st.session_state[key]
                            st.success("수정되었습니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"수정 실패: {e}")
            with col_cancel:
                if st.button("취소", key="nb_edit_cancel"):
                    for key in ("nb_edit_sheet_row", "nb_edit_data"):
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
            st.divider()

        if not nb_records:
            st.info("올해 등록된 새신자가 없습니다.")
        else:
            df_nb = pd.DataFrame(nb_records)
            if "등록일" not in df_nb.columns:
                st.info("새신자 시트에 등록일 데이터가 없습니다.")
            else:
                df_nb["등록일"] = pd.to_datetime(df_nb["등록일"], errors="coerce")
                df_nb["_sheet_row"] = list(range(2, 2 + len(nb_records)))
                df_nb = df_nb.dropna(subset=["등록일"])
                this_year = date.today().year
                df_nb = df_nb[df_nb["등록일"].dt.year == this_year].copy()
                df_nb = df_nb.sort_values("등록일", ascending=True).reset_index(drop=True)
                photo_col = "사진" if "사진" in df_nb.columns else ("사진URL" if "사진URL" in df_nb.columns else None)
                st.caption(f"올해({this_year}년) 등록된 새신자 {len(df_nb)}명 (등록일 순)")
                st.markdown("""
                <style>
                hr { margin: 2px 0 !important; border: none; border-top: 1px solid rgba(49,51,63,0.2); }
                [data-testid="stVerticalBlock"] > div { padding-top: 0 !important; padding-bottom: 0 !important; }
                [data-testid="column"] { padding-top: 2px !important; padding-bottom: 2px !important; }
                </style>
                """, unsafe_allow_html=True)
                for i, (_, row) in enumerate(df_nb.iterrows()):
                    col_photo, col_info, col_btn = st.columns([1, 4, 1])
                    with col_photo:
                        val = (row.get(photo_col) or "") if photo_col else ""
                        if isinstance(val, str) and len(val) > 100 and not val.startswith("http"):
                            try:
                                raw = base64.b64decode(val)
                                st.image(io.BytesIO(raw), width=PHOTO_WIDTH)
                            except Exception:
                                st.caption("—")
                        else:
                            st.caption("—")
                    with col_info:
                        reg_d = row.get("등록일")
                        reg_d = reg_d.strftime("%Y-%m-%d") if hasattr(reg_d, "strftime") else str(reg_d or "")[:10]
                        st.markdown(f"**{row.get('이름', '')}** · {reg_d}")
                        parts = []
                        if row.get("전화"):
                            parts.append(f"전화 {row.get('전화')}")
                        if row.get("생년월일"):
                            parts.append(f"생년 {row.get('생년월일')}")
                        if row.get("주소"):
                            parts.append(f"주소 {row.get('주소')}")
                        if row.get("전도한친구이름"):
                            parts.append(f"전도한 친구 {row.get('전도한친구이름')}")
                        g, c = row.get("학년"), row.get("반")
                        if g or c:
                            parts.append(f"{g or ''}학년 {c or ''}반".strip())
                        if parts:
                            st.caption(" · ".join(parts))
                    with col_btn:
                        sheet_row = int(row.get("_sheet_row", 0))
                        if st.button("수정", key=f"nb_edit_btn_{sheet_row}"):
                            st.session_state["nb_edit_sheet_row"] = sheet_row
                            st.session_state["nb_edit_data"] = row.drop(labels=["_sheet_row"], errors="ignore").to_dict()
                            st.rerun()
                    if i < len(df_nb) - 1:
                        st.divider()
