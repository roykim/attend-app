# -*- coding: utf-8 -*-
"""탭 공통 유틸 (반 표시 라벨 등)."""

import pandas as pd


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
