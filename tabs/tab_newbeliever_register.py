# -*- coding: utf-8 -*-
"""탭 4: 새신자 등록."""

import base64
import io
from datetime import date

import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_cropper import st_cropper

from config import PHOTO_HEIGHT, PHOTO_WIDTH
from photo_utils import image_to_base64_for_sheet, resize_photo_to_final
from sheets import (
    ensure_students_photo_column,
    get_new_believers_ws,
    get_students_data,
    get_students_ws,
)


def render(tab):
    students_data = get_students_data()
    new_grade_list = sorted(students_data["학년"].dropna().unique().tolist(), key=str)
    grade_options = ["(미배정)"] + [str(x) for x in new_grade_list]
    new_class_options_by_grade = {}
    for g in new_grade_list:
        fc = students_data[students_data["학년"] == g]
        new_class_options_by_grade[str(g)] = ["(미배정)"] + [str(x) for x in sorted(fc["반"].dropna().unique().tolist(), key=str)]

    with tab:
        st.title("✝️ 새신자 등록")
        reg_date = st.date_input("등록일", value=date.today(), key="new_reg_date")
        new_name = st.text_input("이름 *", key="new_name", placeholder="이름을 입력하세요")
        new_phone = st.text_input("전화", key="new_phone", placeholder="010-0000-0000")
        new_birth = st.text_input("생년월일", key="new_birth", placeholder="예: 1990-01-15")
        new_address = st.text_input("주소", key="new_address", placeholder="주소를 입력하세요")
        new_friend = st.text_input("전도한 친구 이름", key="new_friend", placeholder="전도한 분 이름")

        st.subheader("사진 (선택)")
        photo_source = st.radio("사진 입력 방법", ["파일에서 선택", "카메라로 촬영"], key="new_photo_source", horizontal=True, label_visibility="collapsed")
        new_photo_bytes = None
        new_photo_mime = None
        if photo_source == "파일에서 선택":
            photo_file = st.file_uploader("이미지 파일 선택 (PNG, JPEG, JPG, WEBP 등)", type=["png", "jpg", "jpeg", "webp"], key="new_photo_file")
            if photo_file:
                new_photo_bytes = photo_file.getvalue()
                new_photo_mime = photo_file.type or "image/jpeg"
        else:
            camera_photo = st.camera_input("카메라로 촬영", key="new_photo_camera")
            if camera_photo:
                new_photo_bytes = camera_photo.getvalue()
                new_photo_mime = camera_photo.type or "image/jpeg"

        new_photo_cropped_bytes = None
        if new_photo_bytes:
            try:
                img = Image.open(io.BytesIO(new_photo_bytes))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                st.caption("영역을 드래그해 잘라낼 위치와 크기를 선택하세요 (비율 3:4 고정)")
                cropped_img = st_cropper(img, aspect_ratio=(3, 4), realtime_update=True, box_color="#0066cc")
                if cropped_img is not None:
                    new_photo_cropped_bytes = resize_photo_to_final(cropped_img)
                    if new_photo_cropped_bytes:
                        st.caption(f"저장될 사진 ({PHOTO_WIDTH}×{PHOTO_HEIGHT}px)")
                        st.image(new_photo_cropped_bytes, width=PHOTO_WIDTH)
            except Exception:
                st.caption("사진을 불러올 수 없습니다.")

        st.subheader("반 할당 (선택)")
        st.caption("반을 할당하면 출석 입력·개별 출석에서 해당 반으로 관리됩니다.")
        sel_grade_idx = st.selectbox("학년", range(len(grade_options)), format_func=lambda i: str(grade_options[i]), key="new_grade")
        selected_new_grade = None if grade_options[sel_grade_idx] == "(미배정)" else grade_options[sel_grade_idx]
        selected_new_class = None
        if selected_new_grade is not None:
            class_list = new_class_options_by_grade.get(str(selected_new_grade), ["(미배정)"])
            sel_class_idx = st.selectbox("반", range(len(class_list)), format_func=lambda i: str(class_list[i]), key="new_class")
            if class_list[sel_class_idx] != "(미배정)":
                selected_new_class = class_list[sel_class_idx]

        if st.button("새신자 등록"):
            if not (new_name and new_name.strip()):
                st.error("이름을 입력해 주세요.")
            else:
                try:
                    photo_b64 = ""
                    if new_photo_cropped_bytes:
                        photo_b64 = base64.b64encode(new_photo_cropped_bytes).decode("ascii")
                    elif new_photo_bytes:
                        photo_b64 = image_to_base64_for_sheet(new_photo_bytes, new_photo_mime)
                    nb_ws = get_new_believers_ws()
                    row = [
                        reg_date.strftime("%Y-%m-%d"), new_name.strip(),
                        new_phone.strip() if new_phone else "", new_birth.strip() if new_birth else "",
                        new_address.strip() if new_address else "", new_friend.strip() if new_friend else "",
                        str(selected_new_grade) if selected_new_grade else "", str(selected_new_class) if selected_new_class else "",
                        photo_b64,
                    ]
                    nb_ws.append_row(row)
                    if selected_new_grade is not None and selected_new_class is not None:
                        students_ws = get_students_ws()
                        ensure_students_photo_column(students_ws)
                        existing = pd.DataFrame(students_ws.get_all_records())
                        already = (
                            existing["학년"].astype(str).eq(str(selected_new_grade))
                            & existing["반"].astype(str).eq(str(selected_new_class))
                            & existing["이름"].astype(str).eq(new_name.strip())
                        )
                        if not already.any():
                            headers = existing.columns.tolist()
                            row_map = {"학년": selected_new_grade, "반": selected_new_class, "이름": new_name.strip(), "사진": photo_b64, "사진URL": photo_b64}
                            phone_val = new_phone.strip() if new_phone else ""
                            for col in ["전화번호", "휴대전화", "연락처"]:
                                if col in headers:
                                    row_map[col] = phone_val
                                    break
                            student_row = [str(row_map.get(h, "")) for h in headers]
                            students_ws.append_row(student_row)
                            get_students_data.clear()
                        else:
                            get_students_data.clear()
                    st.success("새신자가 등록되었습니다." + (" 해당 반에 추가되어 출석 관리됩니다." if selected_new_grade and selected_new_class else ""))
                    for key in ("new_reg_date", "new_name", "new_phone", "new_birth", "new_address", "new_friend", "new_grade", "new_class", "new_photo_source", "new_photo_file", "new_photo_camera"):
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
                except Exception as e:
                    st.error(f"등록 실패: {e}")
