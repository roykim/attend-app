# -*- coding: utf-8 -*-
"""탭 1: 출석 입력."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from sheets import get_attendance_data, get_attendance_ws, get_class_data, get_students_data, invalidate_sheets_cache
from tabs.utils import class_display_label, get_restored_class_index, get_restored_grade_index, natural_sort_key, save_grade_class_for_restore


def _last_sunday(t: date) -> date:
    """오늘 포함, 오늘과 가장 가까운 지난 주일(일요일) 반환. (월=0, 일=6)"""
    # weekday(): 월=0 .. 일=6 → 일요일까지 며칠 지났는지 = (weekday + 1) % 7
    days_back = (t.weekday() + 1) % 7
    return t - timedelta(days=days_back)


def _sunday_options(count: int = 52) -> list[date]:
    """기준일(가장 최근 지난 일요일)부터 과거로 count개 주일 목록."""
    start = _last_sunday(date.today())
    return [start - timedelta(days=7 * i) for i in range(count)]


def render(tab):
    students_data = get_students_data()
    sundays = _sunday_options()
    default_index = 0  # 가장 가까운 지난 주일(일요일)

    with tab:
        st.title("📋 출석 입력")
        options = [d.strftime("%Y-%m-%d (일)") for d in sundays]
        sel_label = st.selectbox(
            "출석 날짜 (주일)",
            range(len(options)),
            index=default_index,
            format_func=lambda i: options[i],
            key="date_input",
        )
        selected_date = sundays[sel_label]
        grades = sorted(students_data["학년"].dropna().unique().tolist(), key=natural_sort_key)
        default_grade_idx = get_restored_grade_index(grades)
        selected_grade = st.selectbox("학년 선택", grades, key="grade_select", index=default_grade_idx)
        filtered_class = students_data[students_data["학년"] == selected_grade]
        classes = sorted(filtered_class["반"].dropna().unique().tolist(), key=natural_sort_key)
        try:
            class_data = get_class_data()
        except Exception:
            class_data = pd.DataFrame()
        class_data_for_grade = (
            class_data[(class_data["학년"].astype(str) == str(selected_grade))]
            if (class_data is not None and not class_data.empty)
            else pd.DataFrame()
        )
        class_options = [
            class_display_label(c, selected_grade, class_data_for_grade if not class_data_for_grade.empty else None)
            for c in classes
        ]
        default_class_idx = get_restored_class_index(classes)
        selected_idx = st.selectbox(
            "반 선택",
            range(len(classes)),
            format_func=lambda i: class_options[i],
            key=f"class_select_{selected_grade}",
            index=default_class_idx,
        )
        selected_class = classes[min(selected_idx, len(classes) - 1)] if classes else None
        save_grade_class_for_restore(selected_grade, selected_class)
        class_students = filtered_class[filtered_class["반"] == selected_class]

        date_str = selected_date.strftime("%Y-%m-%d")
        try:
            attendance_all = get_attendance_data()
            if not attendance_all.empty and "날짜" in attendance_all.columns:
                mask = (
                    (attendance_all["날짜"].astype(str) == date_str)
                    & (attendance_all["학년"].astype(str) == str(selected_grade))
                    & (attendance_all["반"].astype(str) == str(selected_class))
                    & (attendance_all["출석상태"].astype(str) == "출석")
                )
                attended_names = set(attendance_all.loc[mask, "이름"].astype(str).tolist())
            else:
                attended_names = set()
        except Exception:
            attended_names = set()

        st.subheader("학생 출석 체크")
        attendance_data = []
        for _, row in class_students.iterrows():
            name = row["이름"]
            default_checked = name in attended_names
            status = st.checkbox(
                name, value=default_checked, key=f"cb_{name}_{selected_grade}_{selected_class}_{date_str}"
            )
            attendance_data.append({
                "날짜": selected_date.strftime("%Y-%m-%d"),
                "학년": selected_grade,
                "반": selected_class,
                "이름": row["이름"],
                "출석상태": "출석" if status else "결석",
                "비고": ""
            })

        if st.button("저장"):
            df_to_save = pd.DataFrame(attendance_data)
            get_attendance_ws().append_rows(df_to_save.values.tolist())
            invalidate_sheets_cache()
            st.success("출석이 저장되었습니다!")
