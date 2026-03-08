# -*- coding: utf-8 -*-
"""탭 공통 유틸 (반 표시 라벨, 학년·반 복원 등)."""

import pandas as pd
import streamlit as st

import auth
import sheets


def natural_sort_key(x):
    """반/학년 등 숫자 문자열을 1, 2, …, 10 순으로 정렬하기 위한 키. 문자열이면 1,10,2,… 대신 1,2,…,10 순."""
    try:
        return (0, int(x))
    except (ValueError, TypeError):
        return (1, str(x) if x is not None else "")


def class_display_label(class_name: str, grade: str, class_df: pd.DataFrame | None) -> str:
    """반 이름 옆에 교사·부교사가 있으면 괄호로 표시.

    class_df는 class 시트 DataFrame. 컬럼 후보:
    - 교사: 담당선생님 / 담당 / 교사
    - 부교사: 부교사 / 부교사 선생님
    """
    if class_df is None or class_df.empty:
        return str(class_name)
    teacher_col = (
        "담당선생님" if "담당선생님" in class_df.columns
        else ("담당" if "담당" in class_df.columns else ("교사" if "교사" in class_df.columns else None))
    )
    sub_col = (
        "부교사" if "부교사" in class_df.columns
        else ("부교사 선생님" if "부교사 선생님" in class_df.columns else None)
    )
    row = class_df[
        (class_df["학년"].astype(str) == str(grade))
        & (class_df["반"].astype(str) == str(class_name))
    ]
    if row.empty:
        return str(class_name)
    row = row.iloc[0]
    teacher = (row.get(teacher_col) or "") if teacher_col else ""
    sub = (row.get(sub_col) or "") if sub_col else ""
    teacher = str(teacher).strip() if pd.notna(teacher) else ""
    sub = str(sub).strip() if pd.notna(sub) else ""
    parts = []
    if teacher:
        parts.append(f"교사: {teacher}")
    if sub:
        parts.append(f"부교사: {sub}")
    if not parts:
        return str(class_name)
    return f"{class_name} ({', '.join(parts)})"


def get_restored_grade_index(grades: list) -> int:
    """저장된 마지막 학년이 grades 목록에 있으면 그 인덱스, 없으면 0."""
    last = st.session_state.get("app_last_grade")
    if last is None or not str(last).strip() or not grades:
        return 0
    last_s = str(last).strip()
    for i, g in enumerate(grades):
        if str(g).strip() == last_s:
            return min(i, len(grades) - 1)
    return 0


def get_restored_class_index(classes: list) -> int:
    """저장된 마지막 반이 classes 목록에 있으면 그 인덱스, 없으면 0."""
    last = st.session_state.get("app_last_class")
    if last is None or not str(last).strip() or not classes:
        return 0
    last_s = str(last).strip()
    for i, c in enumerate(classes):
        if str(c).strip() == last_s:
            return min(i, len(classes) - 1)
    return 0


def save_grade_class_for_restore(grade: str | None, class_val: str | None):
    """선택한 학년·반을 저장해 다음 접속 시 복원되도록 함."""
    fp = auth.get_fingerprint_hash()
    sheets.set_last_grade_class(fp, grade, class_val)
    st.session_state["app_last_grade"] = (str(grade).strip() if grade is not None else "") or None
    st.session_state["app_last_class"] = (str(class_val).strip() if class_val is not None else "") or None
