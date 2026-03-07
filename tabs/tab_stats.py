# -*- coding: utf-8 -*-
"""탭 2: 출석 통계 (주일)."""

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from sheets import get_attendance_data, get_new_believers_data
from tabs.utils import natural_sort_key


def _y_dtick(max_val: float) -> int:
    """명수 축: 자동 스케일이되 최소 간격은 1 이상. max_val 기준으로 적당한 dtick 반환."""
    if max_val <= 0:
        return 1
    if max_val <= 10:
        return 1
    if max_val <= 30:
        return 5
    if max_val <= 100:
        return 10
    return 20


def render(tab):
    with tab:
        st.title("📊 출석 통계 (주일)")
        try:
            attendance_raw = get_attendance_data()
        except Exception:
            st.warning("출석 데이터를 불러올 수 없습니다. 출석 입력을 먼저 진행해 주세요.")
            st.stop()

        if attendance_raw.empty or "날짜" not in attendance_raw.columns:
            st.info("아직 출석 데이터가 없습니다. 출석 입력 탭에서 데이터를 입력해 주세요.")
            st.stop()

        attendance_raw["날짜"] = pd.to_datetime(attendance_raw["날짜"], errors="coerce")
        attendance_raw = attendance_raw.dropna(subset=["날짜"])
        df_att = attendance_raw[attendance_raw["출석상태"] == "출석"].copy()

        if df_att.empty:
            st.info("출석 기록이 없습니다.")
            st.stop()

        df_att["주일_기준"] = df_att["날짜"].dt.to_period("W-SUN")
        df_att["주일"] = df_att["주일_기준"].apply(lambda p: p.end_time.strftime("%m/%d"))
        # 오늘보다 미래 주일은 제외
        today = date.today()
        df_att = df_att[df_att["주일_기준"].apply(lambda p: p.end_time.date() <= today)]

        st.subheader("1. 전체 출석자 (주일)")
        # 같은 주에 동일 인원이 여러 번 세어지지 않도록 (이름, 학년, 반) 기준 중복 제거 후 집계
        df_att_unique = df_att.drop_duplicates(subset=["주일_기준", "이름", "학년", "반"])
        weekly_total = df_att_unique.groupby("주일_기준").size().reset_index(name="출석인원")
        weekly_total["주일"] = weekly_total["주일_기준"].apply(lambda p: p.end_time.strftime("%m/%d"))
        weekly_total = weekly_total.sort_values("주일_기준")
        if weekly_total.empty:
            st.caption("표시할 주일별 데이터가 없습니다.")
        else:
            max1 = weekly_total["출석인원"].max()
            x_categories = weekly_total["주일"].unique().tolist()
            fig1 = px.line(weekly_total, x="주일", y="출석인원", markers=True)
            fig1.update_traces(hovertemplate="주일: %{x}<br>출석인원: %{y:.0f}명<extra></extra>")
            fig1.update_layout(
                xaxis_tickangle=-45, margin=dict(b=80), xaxis_title="", yaxis_title="출석인원",
                yaxis=dict(dtick=_y_dtick(max1), tickformat=".0f"),
                xaxis=dict(categoryorder="array", categoryarray=x_categories),
                dragmode=False,
            )
            st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

        st.subheader("2. 학년별 출석 (주일)")
        # 학년별 주당 출석 인원 = 같은 주·같은 학년에서 동일 학생 1명으로만 집계
        weekly_by_grade = df_att.groupby(["주일_기준", "학년"])["이름"].nunique().reset_index(name="출석인원")
        weekly_by_grade["주일"] = weekly_by_grade["주일_기준"].apply(lambda p: p.end_time.strftime("%m/%d"))
        weekly_by_grade = weekly_by_grade.sort_values(["주일_기준", "학년"])
        if weekly_by_grade.empty:
            st.caption("표시할 학년별 데이터가 없습니다.")
        else:
            max2 = weekly_by_grade["출석인원"].max()
            # x축 날짜 순서 고정: 주일_기준 정렬 순서대로 유지
            x_categories = weekly_by_grade["주일"].unique().tolist()
            fig2 = px.line(weekly_by_grade, x="주일", y="출석인원", color="학년", markers=True)
            fig2.update_traces(hovertemplate="주일: %{x}<br>학년: %{fullData.name}<br>출석인원: %{y:.0f}명<extra></extra>")
            fig2.update_layout(
                xaxis_tickangle=-45, margin=dict(b=80), xaxis_title="", yaxis_title="출석인원", legend_title="학년",
                yaxis=dict(dtick=_y_dtick(max2), tickformat=".0f"),
                xaxis=dict(categoryorder="array", categoryarray=x_categories),
                dragmode=False,
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

        st.subheader("3. 학년별 반별 출석 (주일)")
        grades_list = sorted(df_att["학년"].dropna().unique().tolist(), key=natural_sort_key)
        for grade in grades_list:
            grade_df = df_att[df_att["학년"] == grade]
            # 반별 주당 출석 인원 = 같은 주·같은 반에서 동일 학생 1명으로만 집계
            weekly_by_class = grade_df.groupby(["주일_기준", "반"])["이름"].nunique().reset_index(name="출석인원")
            weekly_by_class["주일"] = weekly_by_class["주일_기준"].apply(lambda p: p.end_time.strftime("%m/%d"))
            # 반을 1,2,…,10 순으로 정렬 (문자열 정렬이면 1,10,2,… 가 됨)
            weekly_by_class = weekly_by_class.copy()
            weekly_by_class["_반순서"] = weekly_by_class["반"].apply(natural_sort_key)
            weekly_by_class = weekly_by_class.sort_values(["주일_기준", "_반순서"]).drop(columns=["_반순서"])
            if weekly_by_class.empty:
                st.caption(f"{grade}학년 — 데이터 없음")
                continue
            max_cls = weekly_by_class["출석인원"].max() if not weekly_by_class.empty else 0
            x_categories_cls = weekly_by_class["주일"].unique().tolist()
            fig = px.line(weekly_by_class, x="주일", y="출석인원", color="반", markers=True)
            fig.update_traces(hovertemplate="주일: %{x}<br>반: %{fullData.name}<br>출석인원: %{y:.0f}명<extra></extra>")
            fig.update_layout(
                title=f"{grade}학년 반별",
                xaxis_tickangle=-45, xaxis_title="", yaxis_title="출석인원",
                margin=dict(b=80, t=40), legend_title="반",
                yaxis=dict(dtick=_y_dtick(max_cls), tickformat=".0f"),
                xaxis=dict(categoryorder="array", categoryarray=x_categories_cls),
                dragmode=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})

        # 4. 날짜별(주일) 새신자 등록자 수 (맨 아랫쪽)
        st.subheader("4. 주일별 새신자 등록자 수")
        try:
            nb_records = get_new_believers_data()
            if not nb_records or "등록일" not in (nb_records[0] if nb_records else {}):
                st.caption("새신자 등록 데이터가 없습니다.")
            else:
                df_nb = pd.DataFrame(nb_records)
                df_nb["등록일"] = pd.to_datetime(df_nb["등록일"], errors="coerce")
                df_nb = df_nb.dropna(subset=["등록일"])
                if df_nb.empty:
                    st.caption("등록일 기준 새신자 데이터가 없습니다.")
                else:
                    df_nb["주일_기준"] = df_nb["등록일"].dt.to_period("W-SUN")
                    df_nb["주일"] = df_nb["주일_기준"].apply(lambda p: p.end_time.strftime("%m/%d"))
                    today = date.today()
                    df_nb = df_nb[df_nb["주일_기준"].apply(lambda p: p.end_time.date() <= today)]
                    weekly_nb = df_nb.groupby("주일_기준").size().reset_index(name="새신자 등록")
                    weekly_nb["주일"] = weekly_nb["주일_기준"].apply(lambda p: p.end_time.strftime("%m/%d"))
                    weekly_nb = weekly_nb.sort_values("주일_기준")
                    if weekly_nb.empty:
                        st.caption("표시할 주일별 새신자 데이터가 없습니다.")
                    else:
                        max_nb = weekly_nb["새신자 등록"].max()
                        x_categories_nb = weekly_nb["주일"].unique().tolist()
                        fig_nb = px.line(weekly_nb, x="주일", y="새신자 등록", markers=True)
                        fig_nb.update_traces(hovertemplate="주일: %{x}<br>새신자 등록: %{y:.0f}명<extra></extra>")
                        fig_nb.update_layout(
                            xaxis_tickangle=-45, margin=dict(b=80), xaxis_title="", yaxis_title="새신자 등록(명)",
                            yaxis=dict(dtick=_y_dtick(max_nb), tickformat=".0f"),
                            xaxis=dict(categoryorder="array", categoryarray=x_categories_nb),
                            dragmode=False,
                        )
                        st.plotly_chart(fig_nb, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
        except Exception:
            st.caption("새신자 데이터를 불러올 수 없습니다.")
