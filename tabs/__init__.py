# -*- coding: utf-8 -*-
"""탭별 UI 렌더링 모듈."""

from tabs.tab_attendance import render as render_attendance
from tabs.tab_stats import render as render_stats
from tabs.tab_individual import render as render_individual
from tabs.tab_newbeliever_register import render as render_newbeliever_register
from tabs.tab_newbeliever_status import render as render_newbeliever_status
from tabs.tab_class_info import render as render_class_info

__all__ = [
    "render_attendance",
    "render_stats",
    "render_individual",
    "render_newbeliever_register",
    "render_newbeliever_status",
    "render_class_info",
]
