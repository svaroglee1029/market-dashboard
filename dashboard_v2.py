# -*- coding: utf-8 -*-
"""
市场分析综合看板 v2 —— 时间框从 25M1 开始（同比数据完整保留）
独立文件，不修改原 dashboard.py。

运行: streamlit run dashboard_v2.py --server.port 8502
"""
import sys, os, types, re, json
from pathlib import Path
from datetime import datetime

# ====== 让 import dashboard.py 时 st.tabs 等 UI 不报错 ======
import streamlit as st

# ====== 先加载 dashboard.py 的数据和业务函数 ======
DASH = Path(__file__).parent / "dashboard.py"
import importlib.util
spec = importlib.util.spec_from_file_location("dash_core", str(DASH))
dash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dash)

# ====== 现在 dashboard.py 顶层已经跑完了，可以覆盖 UI 变量 ======
# 关键：保留完整 ind_months 用于同比计算，只给 UI 展示层截断

_UI_MIN_YM = "202501"
ind_months_UI = [m for m in dash.ind_months if m >= _UI_MIN_YM]
YM_LABS_UI = [dash.ym_lab(m) for m in ind_months_UI]

# 兜底
if not ind_months_UI:
    ind_months_UI = list(dash.ind_months)
    YM_LABS_UI = list(dash.YM_LABS)

print(f"📌 dashboard_v2.py — 时间框: {YM_LABS_UI[0]} ~ {YM_LABS_UI[-1]} (共 {len(YM_LABS_UI)} 个月)")
print(f"📌 同比计算仍用完整 {len(dash.ind_months)} 个月")

# ====== 页面配置 ======
st.set_page_config(
    page_title="市场分析综合看板",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ====== 顶部标题 ======
_latest = dash.ind_months[-1] if dash.ind_months else dash.all_months[-1]
st.markdown(f"""
<div style="padding: 12px 20px; background: #fff; border-bottom: 1px solid #e8eaed; margin-bottom: 0;">
  <h1 style="font-size: 20px; font-weight: 700; margin: 0; color: #1f2328;">{dash.ym_lab(_latest)} 线下药店市场监测报告</h1>
  <div style="color: #646a73; font-size: 12px; margin-top: 4px;">数据来源: MySQL test 库 · 时间框选择: 25M1 — 最新</div>
</div>
""", unsafe_allow_html=True)

# ====== Tab 导航 ======
tab_a, tab_b = st.tabs(["📊 Tab A · 整体市场表现", "🏷️ Tab B · 重点品类品牌分析"])

# ==================== Tab A ====================
with tab_a:
    # 统一时间选择器（时间框截断为 ≥ 25M1）
    tc1, tc2 = st.columns([0.25, 0.75], gap="small")
    with tc1:
        sel_ym_a = st.selectbox(
            "统计截止月份",
            options=list(reversed(ind_months_UI)),
            index=0,
            label_visibility="collapsed",
            key="v2_tab_a_month",
        )
    with tc2:
        # 滑块 options 已经截断为 ≥ 25M1
        sl_l_a, sl_r_a = st.select_slider(
            "月度数据范围",
            options=YM_LABS_UI,
            value=(YM_LABS_UI[0], YM_LABS_UI[-1]),
            label_visibility="collapsed",
            key="v2_tab_a_range",
        )
        si_a = YM_LABS_UI.index(sl_l_a)
        ei_a = YM_LABS_UI.index(sl_r_a)
        SEL_M_A = ind_months_UI[si_a:ei_a + 1]

    st.caption(f"时间范围: {dash.ym_lab(SEL_M_A[0])} — {dash.ym_lab(SEL_M_A[-1])}  ·  截止: {dash.ym_lab(sel_ym_a)}")
    st.divider()

    # 四个页面复用 dashboard.py 的函数
    dash.page1(sel_ym_a, SEL_M_A)
    dash.page2(sel_ym_a, SEL_M_A)
    dash.page3(sel_ym_a, SEL_M_A)
    dash.page4(sel_ym_a)

# ==================== Tab B ====================
with tab_b:
    st.info("Tab B 沿用原 dashboard.py 时间选择（完整 2021—至今）。如需同样截断请告知。")
    # 这里可以后续补充 Tab B 的时间截断
