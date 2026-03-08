# -*- coding: utf-8 -*-
"""탭 6: 반정보 (학년/반별 학생 현황·수정·추가)."""

import base64
import io
import time

import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

from config import PHOTO_HEIGHT, PHOTO_WIDTH
from photo_utils import image_to_base64_for_sheet, resize_photo_to_final
from sheets import (
    ensure_students_extra_columns,
    ensure_students_photo_column,
    get_class_data,
    get_students_data,
    get_students_ws,
)
from tabs.utils import class_display_label, get_restored_class_index, get_restored_grade_index, natural_sort_key, save_grade_class_for_restore


def _clear_class_edit_state():
    """수정/취소 후 반정보 탭 세션 정리. 남은 위젯 키가 rerun 시 꼬이는 것 방지."""
    keys_to_del = [k for k in list(st.session_state.keys()) if k.startswith("class_edit")]
    for k in keys_to_del:
        del st.session_state[k]


def render(tab):
    for attempt in range(2):
        try:
            students_data = get_students_data()
            break
        except Exception:
            if attempt == 1:
                with tab:
                    st.warning("학생 데이터를 불러올 수 없습니다. 잠시 후 다시 시도해 보세요.")
                    if st.button("다시 로드", key="class_reload_data"):
                        get_students_data.clear()
                        st.rerun()
                st.stop()
            time.sleep(0.3)

    students_ws = get_students_ws()
    ensure_students_photo_column(students_ws)
    ensure_students_extra_columns(students_ws)
    try:
        class_headers = list(students_data.columns)
        class_all_records = students_data.to_dict("records")
    except Exception:
        with tab:
            st.warning("학생 데이터를 불러올 수 없습니다.")
            if st.button("다시 로드", key="class_reload_data2"):
                get_students_data.clear()
                st.rerun()
        st.stop()

    if not class_headers:
        st.info("학생 시트에 헤더가 없습니다.")
        st.stop()

    with tab:
        st.title("📂 반정보")
        grades_class = sorted(students_data["학년"].dropna().unique().tolist(), key=natural_sort_key)
        default_grade_idx_c = get_restored_grade_index(grades_class)
        selected_grade_class = st.selectbox("학년", grades_class, key="class_info_grade", index=default_grade_idx_c)
        filtered_for_class = students_data[students_data["학년"] == selected_grade_class]
        classes_list = sorted(filtered_for_class["반"].dropna().unique().tolist(), key=natural_sort_key)
        try:
            class_data = get_class_data()
        except Exception:
            class_data = pd.DataFrame()
        class_data_for_grade = (
            class_data[(class_data["학년"].astype(str) == str(selected_grade_class))]
            if (class_data is not None and not class_data.empty)
            else pd.DataFrame()
        )
        class_options = [
            class_display_label(c, selected_grade_class, class_data_for_grade if not class_data_for_grade.empty else None)
            for c in classes_list
        ]
        default_class_idx_c = get_restored_class_index(classes_list)
        selected_class_idx = st.selectbox(
            "반",
            range(len(classes_list)),
            format_func=lambda i: class_options[i],
            key=f"class_info_class_{selected_grade_class}",
            index=default_class_idx_c,
        )
        selected_class_only = classes_list[min(selected_class_idx, len(classes_list) - 1)] if classes_list else None
        save_grade_class_for_restore(selected_grade_class, selected_class_only)

        df_all = pd.DataFrame(class_all_records)
        df_all["_sheet_row"] = list(range(2, 2 + len(class_all_records)))  # 시트 행 번호 (헤더=1)
        df_class = df_all[
            (df_all["학년"].astype(str) == str(selected_grade_class))
            & (df_all["반"].astype(str) == str(selected_class_only))
        ].copy().reset_index(drop=True)

        phone_col = None
        for c in ["전화번호", "휴대전화", "연락처", "전화"]:
            if c in class_headers:
                phone_col = c
                break
        photo_col_class = "사진" if "사진" in class_headers else ("사진URL" if "사진URL" in class_headers else None)

        with st.expander("➕ 학생 추가", expanded=False):
            add_name_c = st.text_input("이름 *", key="class_add_name", placeholder="이름")
            add_phone_c = st.text_input("연락처", key="class_add_phone", placeholder="010-0000-0000")
            add_birth_c = st.text_input("생년월일", key="class_add_birth", placeholder="예: 2010-03-15")
            add_gender_c = st.selectbox("성별", ["", "남", "여"], key="class_add_gender")
            add_address_c = st.text_input("주소", key="class_add_address", placeholder="주소")
            add_parent_c = st.text_input("부모님", key="class_add_parent", placeholder="부모님 성함")
            add_parent_phone_c = st.text_input("부모님 연락처", key="class_add_parent_phone", placeholder="010-0000-0000")
            add_member_c = st.selectbox("교인여부", ["", "예", "아니오"], key="class_add_member")
            st.caption("사진 (선택)")
            add_photo_source = st.radio("사진 입력 방법", ["파일에서 선택", "카메라로 촬영"], key="class_add_photo_src", horizontal=True, label_visibility="collapsed")
            add_photo_bytes_c = None
            add_photo_mime_c = "image/jpeg"
            if add_photo_source == "파일에서 선택":
                add_photo_file_c = st.file_uploader("이미지 선택", type=["png", "jpg", "jpeg", "webp"], key="class_add_photo_file")
                if add_photo_file_c:
                    add_photo_bytes_c = add_photo_file_c.getvalue()
                    add_photo_mime_c = add_photo_file_c.type or "image/jpeg"
            else:
                add_photo_cam_c = st.camera_input("카메라로 촬영", key="class_add_photo_cam")
                if add_photo_cam_c:
                    add_photo_bytes_c = add_photo_cam_c.getvalue()
                    add_photo_mime_c = add_photo_cam_c.type or "image/jpeg"
            add_photo_cropped_c = None
            if add_photo_bytes_c:
                try:
                    img_add = Image.open(io.BytesIO(add_photo_bytes_c))
                    if img_add.mode in ("RGBA", "P"):
                        img_add = img_add.convert("RGB")
                    st.caption("영역을 드래그해 잘라낼 위치와 크기를 선택하세요 (비율 3:4 고정)")
                    cropped_add = st_cropper(img_add, aspect_ratio=(3, 4), realtime_update=True, box_color="#0066cc")
                    if cropped_add is not None:
                        add_photo_cropped_c = resize_photo_to_final(cropped_add)
                        if add_photo_cropped_c:
                            st.caption(f"저장될 사진 ({PHOTO_WIDTH}×{PHOTO_HEIGHT}px)")
                            st.image(add_photo_cropped_c, width=PHOTO_WIDTH)
                except Exception:
                    st.caption("사진을 불러올 수 없습니다.")
            if st.button("추가", key="class_add_btn"):
                if not (add_name_c and add_name_c.strip()):
                    st.error("이름을 입력해 주세요.")
                else:
                    try:
                        photo_b64_c = ""
                        if add_photo_cropped_c:
                            photo_b64_c = base64.b64encode(add_photo_cropped_c).decode("ascii")
                        elif add_photo_bytes_c:
                            photo_b64_c = image_to_base64_for_sheet(add_photo_bytes_c, add_photo_mime_c)
                        row_map = {
                            "학년": selected_grade_class, "반": selected_class_only, "이름": add_name_c.strip(),
                            "생년월일": add_birth_c.strip() if add_birth_c else "", "성별": add_gender_c or "",
                            "주소": add_address_c.strip() if add_address_c else "",
                            "부모님": add_parent_c.strip() if add_parent_c else "",
                            "부모님 연락처": add_parent_phone_c.strip() if add_parent_phone_c else "",
                            "교인여부": add_member_c or "",
                        }
                        if phone_col:
                            row_map[phone_col] = add_phone_c.strip() if add_phone_c else ""
                        if photo_col_class:
                            row_map[photo_col_class] = photo_b64_c
                        if "사진" in class_headers and "사진URL" in class_headers:
                            row_map["사진"] = photo_b64_c
                            row_map["사진URL"] = photo_b64_c
                        student_row = [str(row_map.get(h, "")) for h in class_headers]
                        students_ws.append_row(student_row)
                        get_students_data.clear()
                        st.success("학생이 추가되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"추가 실패: {e}")

        if st.session_state.get("class_edit_sheet_row") is not None:
            edit_row_c = st.session_state["class_edit_sheet_row"]
            edit_data_c = st.session_state.get("class_edit_data") or {}
            st.subheader(f"✏️ 수정: {edit_data_c.get('이름', '')}")
            edit_grade_val = str(edit_data_c.get("학년") or "").strip()
            try:
                idx_grade = next(i for i, g in enumerate(grades_class) if str(g).strip() == edit_grade_val)
            except StopIteration:
                idx_grade = 0
            e_grade_c = st.selectbox("학년", grades_class, index=idx_grade, key="class_edit_grade")
            e_class_list_c = sorted(students_data[students_data["학년"].astype(str) == str(e_grade_c)]["반"].dropna().astype(str).unique().tolist(), key=natural_sort_key)
            edit_class_val = str(edit_data_c.get("반") or "").strip()
            try:
                e_class_idx_c = next(i for i, c in enumerate(e_class_list_c) if str(c).strip() == edit_class_val)
            except StopIteration:
                e_class_idx_c = 0
            e_class_c = st.selectbox("반", e_class_list_c, index=min(e_class_idx_c, len(e_class_list_c) - 1), key="class_edit_class")
            e_name_c = st.text_input("이름 *", value=str(edit_data_c.get("이름") or ""), key="class_edit_name")
            e_phone_c = st.text_input("연락처", value=str(edit_data_c.get(phone_col) or "") if phone_col else "", key="class_edit_phone")
            e_birth_c = st.text_input("생년월일", value=str(edit_data_c.get("생년월일") or ""), key="class_edit_birth", placeholder="예: 2010-03-15")
            e_gender_c = st.selectbox("성별", ["", "남", "여"], index=["", "남", "여"].index(str(edit_data_c.get("성별") or "")) if str(edit_data_c.get("성별") or "") in ["", "남", "여"] else 0, key="class_edit_gender")
            e_address_c = st.text_input("주소", value=str(edit_data_c.get("주소") or ""), key="class_edit_address")
            e_parent_c = st.text_input("부모님", value=str(edit_data_c.get("부모님") or ""), key="class_edit_parent")
            e_parent_phone_c = st.text_input("부모님 연락처", value=str(edit_data_c.get("부모님 연락처") or ""), key="class_edit_parent_phone")
            e_member_c = st.selectbox("교인여부", ["", "예", "아니오"], index=["", "예", "아니오"].index(str(edit_data_c.get("교인여부") or "")) if str(edit_data_c.get("교인여부") or "") in ["", "예", "아니오"] else 0, key="class_edit_member")
            st.caption("사진 변경 (선택, 비우면 기존 유지)")
            e_photo_source = st.radio("사진 입력 방법", ["파일에서 선택", "카메라로 촬영"], key="class_edit_photo_src", horizontal=True, label_visibility="collapsed")
            e_photo_bytes_c = None
            e_photo_mime_c = "image/jpeg"
            if e_photo_source == "파일에서 선택":
                e_photo_file_c = st.file_uploader("이미지 선택", type=["png", "jpg", "jpeg", "webp"], key="class_edit_photo_file")
                if e_photo_file_c:
                    e_photo_bytes_c = e_photo_file_c.getvalue()
                    e_photo_mime_c = e_photo_file_c.type or "image/jpeg"
            else:
                e_photo_cam_c = st.camera_input("카메라로 촬영", key="class_edit_photo_cam")
                if e_photo_cam_c:
                    e_photo_bytes_c = e_photo_cam_c.getvalue()
                    e_photo_mime_c = e_photo_cam_c.type or "image/jpeg"
            e_photo_cropped_c = None
            if e_photo_bytes_c:
                try:
                    img_edit = Image.open(io.BytesIO(e_photo_bytes_c))
                    if img_edit.mode in ("RGBA", "P"):
                        img_edit = img_edit.convert("RGB")
                    st.caption("영역을 드래그해 잘라낼 위치와 크기를 선택하세요 (비율 3:4 고정)")
                    cropped_edit = st_cropper(img_edit, aspect_ratio=(3, 4), realtime_update=True, box_color="#0066cc")
                    if cropped_edit is not None:
                        e_photo_cropped_c = resize_photo_to_final(cropped_edit)
                        if e_photo_cropped_c:
                            st.caption(f"저장될 사진 ({PHOTO_WIDTH}×{PHOTO_HEIGHT}px)")
                            st.image(e_photo_cropped_c, width=PHOTO_WIDTH)
                except Exception:
                    st.caption("사진을 불러올 수 없습니다.")
            col_save_c, col_cancel_c = st.columns(2)
            with col_save_c:
                if st.button("저장", key="class_edit_save"):
                    if not (e_name_c and e_name_c.strip()):
                        st.error("이름을 입력해 주세요.")
                    else:
                        try:
                            photo_b64_edit = edit_data_c.get("사진") or edit_data_c.get("사진URL") or ""
                            if e_photo_cropped_c:
                                photo_b64_edit = base64.b64encode(e_photo_cropped_c).decode("ascii")
                            elif e_photo_bytes_c:
                                photo_b64_edit = image_to_base64_for_sheet(e_photo_bytes_c, e_photo_mime_c)
                            row_map_edit = {h: str(edit_data_c.get(h, "")) for h in class_headers}
                            row_map_edit["학년"] = str(e_grade_c)
                            row_map_edit["반"] = str(e_class_c)
                            row_map_edit["이름"] = e_name_c.strip()
                            row_map_edit["생년월일"] = e_birth_c.strip() if e_birth_c else ""
                            row_map_edit["성별"] = e_gender_c or ""
                            row_map_edit["주소"] = e_address_c.strip() if e_address_c else ""
                            row_map_edit["부모님"] = e_parent_c.strip() if e_parent_c else ""
                            row_map_edit["부모님 연락처"] = e_parent_phone_c.strip() if e_parent_phone_c else ""
                            row_map_edit["교인여부"] = e_member_c or ""
                            if phone_col:
                                row_map_edit[phone_col] = e_phone_c.strip() if e_phone_c else ""
                            if photo_col_class:
                                row_map_edit[photo_col_class] = photo_b64_edit
                            if "사진" in class_headers and "사진URL" in class_headers:
                                row_map_edit["사진"] = photo_b64_edit
                                row_map_edit["사진URL"] = photo_b64_edit
                            row_vals_c = [str(row_map_edit.get(h, "")) for h in class_headers]
                            n_col = len(class_headers)
                            col_letter = ""
                            while n_col > 0:
                                n_col, r = divmod(n_col - 1, 26)
                                col_letter = chr(65 + r) + col_letter
                            col_letter = col_letter or "A"
                            range_str = f"A{edit_row_c}:{col_letter}{edit_row_c}"
                            students_ws.update(range_str, [row_vals_c])
                            _clear_class_edit_state()
                            get_students_data.clear()
                            st.success("수정되었습니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"수정 실패: {e}")
            with col_cancel_c:
                if st.button("취소", key="class_edit_cancel"):
                    _clear_class_edit_state()
                    st.rerun()
            st.divider()

        st.caption(f"{selected_grade_class}학년 {selected_class_only}반 · {len(df_class)}명")
        if df_class.empty:
            st.info("이 반에 등록된 학생이 없습니다. 위에서 학생을 추가해 보세요.")
        else:
            st.markdown("""
            <style>
            [data-testid="stVerticalBlock"] > div { padding-top: 0 !important; padding-bottom: 0 !important; }
            [data-testid="column"] { padding-top: 2px !important; padding-bottom: 2px !important; }
            </style>
            """, unsafe_allow_html=True)
            for i, (_, row_c) in enumerate(df_class.iterrows()):
                col_photo_c, col_info_c, col_btn_c = st.columns([1, 4, 1])
                with col_photo_c:
                    val_c = (row_c.get(photo_col_class) or "") if photo_col_class else ""
                    if isinstance(val_c, str) and len(val_c) > 100 and not val_c.startswith("http"):
                        try:
                            raw_c = base64.b64decode(val_c)
                            st.image(io.BytesIO(raw_c), width=PHOTO_WIDTH)
                        except Exception:
                            st.caption("—")
                    else:
                        st.caption("—")
                with col_info_c:
                    st.markdown(f"**{row_c.get('이름', '')}**")
                    # 첫째줄: 성별 · 전화번호 · 생년월일
                    line1 = []
                    if row_c.get("성별"):
                        line1.append(str(row_c.get("성별")))
                    if phone_col and row_c.get(phone_col):
                        line1.append(str(row_c.get(phone_col)))
                    if row_c.get("생년월일"):
                        line1.append(str(row_c.get("생년월일")))
                    if line1:
                        st.caption(" · ".join(line1))
                    # 둘째줄: 주소
                    if row_c.get("주소"):
                        st.caption(str(row_c.get("주소")))
                    # 셋째줄: 부모님 · 부모님연락처 · 교인여부
                    line3 = []
                    if row_c.get("부모님"):
                        line3.append(f"부모님 {row_c.get('부모님')}")
                    if row_c.get("부모님 연락처"):
                        line3.append(f"부모님연락처 {row_c.get('부모님 연락처')}")
                    if row_c.get("교인여부"):
                        line3.append(f"교인 {row_c.get('교인여부')}")
                    if line3:
                        st.caption(" · ".join(line3))
                with col_btn_c:
                    sheet_row_c = int(row_c.get("_sheet_row", 0))
                    if st.button("수정", key=f"class_edit_btn_{sheet_row_c}"):
                        st.session_state["class_edit_sheet_row"] = sheet_row_c
                        st.session_state["class_edit_data"] = row_c.drop(labels=["_sheet_row"], errors="ignore").to_dict()
                        st.rerun()
                if i < len(df_class) - 1:
                    st.divider()
