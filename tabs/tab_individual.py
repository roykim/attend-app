# -*- coding: utf-8 -*-
"""탭 3: 개별 출석 확인."""

import html
from datetime import date

import pandas as pd
import streamlit as st

from sheets import get_attendance_data, get_class_data, get_students_data
from tabs.utils import class_display_label


def render(tab):
    students_data = get_students_data()
    try:
        class_data = get_class_data()
    except Exception:
        class_data = pd.DataFrame()

    with tab:
        st.title("📌 개별 출석 확인")
        grades_t3 = sorted(students_data["학년"].dropna().unique().tolist(), key=str)
        selected_grade_t3 = st.selectbox("학년 선택", grades_t3, key="indiv_grade")
        filtered_t3 = students_data[students_data["학년"] == selected_grade_t3]
        classes_t3 = sorted(filtered_t3["반"].dropna().unique().tolist(), key=str)
        # 선택한 학년에 해당하는 class 시트 행만 넘겨서, 학년 변경 시 반별 교사/부교사가 갱신되도록 함
        class_data_for_grade = (
            class_data[(class_data["학년"].astype(str) == str(selected_grade_t3))]
            if (class_data is not None and not class_data.empty)
            else pd.DataFrame()
        )
        class_options = [
            class_display_label(c, selected_grade_t3, class_data_for_grade if not class_data_for_grade.empty else None)
            for c in classes_t3
        ]
        selected_idx = st.selectbox(
            "반 선택",
            range(len(classes_t3)),
            format_func=lambda i: class_options[i],
            key=f"indiv_class_{selected_grade_t3}",  # 학년 변경 시 반 선택 위젯 갱신
        )
        selected_class_t3 = classes_t3[min(selected_idx, len(classes_t3) - 1)] if classes_t3 else None
        class_students_t3 = filtered_t3[filtered_t3["반"] == selected_class_t3]
        student_names = class_students_t3["이름"].tolist()

        phone_col = None
        for c in ["전화번호", "휴대전화", "연락처"]:
            if c in class_students_t3.columns:
                phone_col = c
                break
        name_to_phone = {}
        if phone_col:
            for _, r in class_students_t3.iterrows():
                name_to_phone[str(r["이름"])] = str(r[phone_col]).strip() if pd.notna(r[phone_col]) else ""

        if not student_names:
            st.info("해당 반에 등록된 학생이 없습니다.")
        else:
            try:
                att_all = get_attendance_data()
            except Exception:
                att_all = pd.DataFrame()

            this_year = date.today().year
            att_all["날짜"] = pd.to_datetime(att_all["날짜"], errors="coerce")
            att_all = att_all.dropna(subset=["날짜"])
            att_all = att_all[
                (att_all["날짜"].dt.year == this_year)
                & (att_all["학년"].astype(str) == str(selected_grade_t3))
                & (att_all["반"].astype(str) == str(selected_class_t3))
            ]
            if not att_all.empty:
                att_all["주일_기준"] = att_all["날짜"].dt.to_period("W-SUN")

            sundays = pd.date_range(start=f"{this_year}-01-01", end=f"{this_year}-12-31", freq="W-SUN")
            all_weeks = [pd.Period(d, freq="W-SUN") for d in sundays]

            attended_by_week = {}
            for _, row in att_all.iterrows():
                if row["출석상태"] != "출석":
                    continue
                name = str(row["이름"])
                w = row["주일_기준"]
                if name not in attended_by_week:
                    attended_by_week[name] = set()
                attended_by_week[name].add(w)

            today = date.today()
            past_weeks = [p for p in all_weeks if p.end_time.date() <= today]
            recent_2_weeks = past_weeks[-2:] if len(past_weeks) >= 2 else []
            recent_2_indices = {
                i for i, p in enumerate(all_weeks) if p.end_time.date() in {q.end_time.date() for q in recent_2_weeks}
            }

            rows = []
            highlight_names = set()
            for name in student_names:
                name_str = str(name)
                row = {"이름": name_str, "전화번호": name_to_phone.get(name_str, "")}
                status_list = []
                for p in all_weeks:
                    if name_str in attended_by_week and p in attended_by_week[name_str]:
                        row[p.end_time.strftime("%m/%d")] = "O"
                        status_list.append(0)
                    else:
                        row[p.end_time.strftime("%m/%d")] = "-"
                        status_list.append(1)
                if len(recent_2_indices) == 2 and all(status_list[i] == 1 for i in recent_2_indices):
                    highlight_names.add(name_str)
                rows.append(row)

            if not rows:
                st.info("이번 해 해당 반 출석 데이터가 없습니다.")
            else:
                st.caption("※ 이름이 **색상으로 강조**된 경우 현재일 기준 최근 2주 연속 결석한 학생입니다.")
                week_cols = [p.end_time.strftime("%m/%d") for p in all_weeks]
                table_html = [
                    "<div class='attendance-table-wrap'>",
                    "<table class='attendance-table'>",
                    "<thead><tr><th>이름</th><th>전화번호</th>" + "".join(f"<th>{html.escape(w)}</th>" for w in week_cols) + "</tr></thead>",
                    "<tbody>",
                ]
                for row in rows:
                    name = row["이름"]
                    name_class = " class='name-highlight'" if name in highlight_names else ""
                    name_escaped = html.escape(str(name))
                    phone_escaped = html.escape(str(row.get("전화번호", "")))
                    cells = "".join(f"<td>{html.escape(str(row.get(w, '-')))}</td>" for w in week_cols)
                    table_html.append(f"<tr><td{name_class}>{name_escaped}</td><td class='phone-cell'>{phone_escaped}</td>{cells}</tr>")
                table_html.append("</tbody></table></div>")

                st.markdown(
                    """
                    <style>
                    .attendance-table-wrap { overflow-x: auto; max-height: 400px; overflow-y: auto; background: #1a1a1a; border-radius: 8px; padding: 1px; }
                    .attendance-table { border-collapse: collapse; min-width: max-content; background: #252525; }
                    .attendance-table th, .attendance-table td { border: 1px solid #3d3d3d; padding: 6px 10px; white-space: nowrap; color: #e8e8e8; }
                    .attendance-table thead th { position: sticky !important; top: 0 !important; z-index: 2 !important; background: #2d3748 !important; color: #f7fafc !important; font-weight: 600; font-size: 0.9em; }
                    .attendance-table thead th:first-child, .attendance-table thead th:nth-child(2) { z-index: 3 !important; background: #1a202c !important; color: #f7fafc !important; }
                    .attendance-table tbody tr:nth-child(even) { background: #2d2d2d; }
                    .attendance-table tbody tr:nth-child(odd) { background: #252525; }
                    .attendance-table th:first-child, .attendance-table td:first-child { position: sticky !important; left: 0 !important; z-index: 1 !important; box-shadow: 2px 0 6px rgba(0,0,0,0.3); min-width: 4.5rem; }
                    .attendance-table th:nth-child(2), .attendance-table td:nth-child(2) { position: sticky !important; left: 4.5rem !important; z-index: 1 !important; box-shadow: 2px 0 6px rgba(0,0,0,0.3); min-width: 7rem; }
                    .attendance-table tbody tr:nth-child(odd) td:first-child, .attendance-table tbody tr:nth-child(odd) td:nth-child(2) { background: #252525 !important; color: #fff !important; }
                    .attendance-table tbody tr:nth-child(even) td:first-child, .attendance-table tbody tr:nth-child(even) td:nth-child(2) { background: #2d2d2d !important; color: #fff !important; }
                    .attendance-table tbody tr td:first-child.name-highlight { background: linear-gradient(135deg, #be185d 0%, #9d174d 100%) !important; color: #fce7f3 !important; font-weight: 600 !important; }
                    </style>
                    """ + "".join(table_html),
                    unsafe_allow_html=True,
                )
