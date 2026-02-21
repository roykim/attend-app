# -*- coding: utf-8 -*-
"""탭 1: 출석 입력."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from sheets import get_attendance_ws, get_students_data


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
        grades = sorted(students_data["학년"].dropna().unique().tolist(), key=str)
        selected_grade = st.selectbox("학년 선택", grades, key="grade_select")
        filtered_class = students_data[students_data["학년"] == selected_grade]
        classes = sorted(filtered_class["반"].dropna().unique().tolist(), key=str)
        selected_class = st.selectbox("반 선택", classes, key="class_select")
        class_students = filtered_class[filtered_class["반"] == selected_class]

        date_str = selected_date.strftime("%Y-%m-%d")
        try:
            attendance_all = pd.DataFrame(get_attendance_ws().get_all_records())
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
            st.success("출석이 저장되었습니다!")
