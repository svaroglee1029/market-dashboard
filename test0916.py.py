# ============================================================
# 市场分析综合仪表盘 - 合并版
# Tab 1: 全国药店VDS市场表现 (page1-page4)
# Tab 2: 重点品类汤臣市场表现 (render_first_page/render_brand_analysis/render_sku_analysis)
# ============================================================

# ====================== 1. Imports ======================
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import calendar
import json

st.set_page_config(page_title="市场分析综合仪表盘", layout="wide")

# 隐藏 Streamlit Cloud 右下角浮窗（头像/反馈按钮）
st.markdown("""
<style>
#st-bottom { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
footer { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ====================== 2. Constants ======================
# --- 来自 merged_dashboard 的常量 ---
SALES_COL = "销售额('000 RMB)"
QTY_COL = "销售量-Pack('00))"
DIST_COL = "加权铺货率"
# WD 动销铺货率：优先取“动销铺货率”列，旧数据只有“加权铺货率”时兜底
WD_COL_CANDIDATES = ["动销铺货率", "加权铺货率"]
# ND 数值铺货率：优先取“铺货率”列；该列缺失时回落到“加权铺货率”，保证 ND 虚线有数据
ND_COL = "铺货率"
ND_FALLBACK = "加权铺货率"
# 运行时按实际数据列解析（数据加载后赋值），缺列回退到加权铺货率
WD_COL = DIST_COL

SKU_COLS = ["year_month", "品类", "品牌", "品牌产品", "产品包装", "品名(含属性)", "集团权益", "处方性质", SALES_COL, QTY_COL, DIST_COL, "动销铺货率", ND_COL]
BRAND_COLS = ["year_month", "品类", "品牌", "品牌产品", "处方性质", SALES_COL, QTY_COL, DIST_COL, "动销铺货率", ND_COL]
DIST_COLS = ["year_month", "品牌_NEW", DIST_COL, SALES_COL]
IND_COLS = ["year_month", "品类", "品牌", SALES_COL, QTY_COL]

# --- 来自 combined_dashboard 的颜色常量 ---
C_BG   = "#F5F7FA"
C_TXT  = "#1E293B"
C_ACC  = "#1B4F8E"
C_VDS  = "#2563EB"
C_OTC  = "#F59E0B"

# page2 品牌色
BRAND_COLORS = {
    "汤臣倍健": "#2563EB",
    "老百姓(维诺健)": "#F59E0B",
    "养生堂": "#64748B",
    "健合H&H": "#EAB308",
    "百合股份": "#10B981",
}
DEFAULT_COLORS = ["#2563EB", "#F59E0B", "#64748B", "#EAB308", "#10B981",
                  "#EF4444", "#8B5CF6", "#06B6D4", "#3B82F6", "#F97316"]

# page3 颜色
C_KEY   = "#3B82F6"
C_OTHER = "#93C5FD"
C_SHARE = "#1E40AF"

# page4 颜色
CATEGORY_COLOR = "#059669"
SALES_COLOR_A  = "#B45309"
SALES_COLOR_B  = "#1B4F8E"
TANG_COLOR     = "#1B4F8E"
SHARE_COLOR    = "#1B4F8E"
GREEN = "#10B981"
RED   = "#EF4444"
YELLOW = "#F59E0B"
BAR_A_START = "#FDE68A"
BAR_A_END   = "#F59E0B"
BAR_B_START = "#BFDBFE"
BAR_B_END   = "#3B82F6"

# ====================== 3. Data Directory (Parquet) ======================
import os

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ====================== 4. Data Loading ======================
@st.cache_data(ttl=1800, show_spinner=False)
def load_sku_df():
    """sku_df：全量 sku 表，三个 section 共享。"""
    df = pd.read_parquet(os.path.join(_DATA_DIR, "sku.parquet"))
    df.columns = [str(c).strip() for c in df.columns]
    for col in [SALES_COL, QTY_COL, DIST_COL, "动销铺货率", ND_COL]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["year_month"] = df["year_month"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    df["year"] = df["year_month"].str[:4].astype(int)
    df["mon"] = df["year_month"].str[4:].astype(int)
    df["ym_id"] = df["year"] * 12 + df["mon"]
    df["sales_m"] = df[SALES_COL] / 1000
    df["qty_h"] = df[QTY_COL]
    df["price"] = df[SALES_COL] / df[QTY_COL].replace(0, np.nan) * 10
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def load_table(table_name):
    """brand / brand_distribution_rate 表，按需列读取。"""
    try:
        if table_name == "brand":
            cols = BRAND_COLS
        elif table_name == "brand_distribution_rate":
            cols = DIST_COLS
        else:
            cols = None
        df = pd.read_parquet(os.path.join(_DATA_DIR, f"{table_name}.parquet"))
        if cols:
            df = df[[c for c in cols if c in df.columns]]
    except Exception as e:
        st.error(f"读取 {table_name}.parquet 失败：{e}")
        st.stop()
    df.columns = [str(c).strip() for c in df.columns]
    if "year_month" in df.columns:
        df["year_month"] = df["year_month"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    for col in [SALES_COL, QTY_COL, DIST_COL, "动销铺货率", ND_COL]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def load_industry():
    """industry 表，Part A (page1-page4) 专用。"""
    df = pd.read_parquet(os.path.join(_DATA_DIR, "industry.parquet"))
    if SALES_COL in df.columns:
        df[SALES_COL] = pd.to_numeric(df[SALES_COL], errors="coerce")
    if "year_month" in df.columns:
        df["year_month"] = df["year_month"].astype(str)
    if QTY_COL in df.columns:
        df[QTY_COL] = pd.to_numeric(df[QTY_COL], errors="coerce")
    df["year"] = df["year_month"].str[:4].astype(int)
    df["mon"] = df["year_month"].str[4:].astype(int)
    df["ym_id"] = df["year"] * 12 + df["mon"]
    return df


def _downcast_df(df):
    """压缩 DataFrame 内存：int64→int32, float64→float32, 低基数字符串→category。"""
    for col in df.columns:
        dt = df[col].dtype
        if pd.api.types.is_integer_dtype(dt):
            df[col] = pd.to_numeric(df[col], downcast="integer")
        elif pd.api.types.is_float_dtype(dt):
            df[col] = pd.to_numeric(df[col], downcast="float")
        elif pd.api.types.is_object_dtype(dt):
            nunique = df[col].nunique()
            if nunique > 0 and nunique < len(df) * 0.5:
                df[col] = df[col].astype("category")
    return df


# 模块级加载
sku_df = _downcast_df(load_sku_df())
brand_df = _downcast_df(load_table("brand"))
dist_df = _downcast_df(load_table("brand_distribution_rate"))
df_ind = _downcast_df(load_industry())

# 按实际数据列解析铺货率口径：WD 优先“动销铺货率”，缺列回退“加权铺货率”；ND 取“铺货率”
WD_COL = next((c for c in WD_COL_CANDIDATES if c in sku_df.columns or c in brand_df.columns), DIST_COL)
# ND 数值铺货率可用：存在“铺货率”列，或缺失时存在“加权铺货率”可作回落
ND_AVAILABLE = any(c in df_.columns for df_ in (sku_df, brand_df, dist_df) for c in (ND_COL, ND_FALLBACK))

import gc
gc.collect()

if df_ind.empty:
    st.error("industry 表中没有数据，请检查数据源。")
    st.stop()

# ====================== 5. Shared Utils ======================
def ym_lab(ym):
    return f"{str(ym)[2:4]}M{int(str(ym)[4:])}"


def period_labels(ym_str):
    """Return (ytd_label, ly_label, l3m_label, yy, lyy) for a given YYYYMM string.
    At quarter-end months (M3/M6/M9/M12), labels reflect accumulated periods.
    """
    yr = int(ym_str[:4])
    mo = int(ym_str[4:])
    yy = str(yr)[2:]
    lyy = str(yr - 1)[2:]

    if mo == 3:
        ytd = f"{yy}Q1"; ly = f"{lyy}Q1"; l3m = f"{lyy}Q4"
    elif mo == 6:
        ytd = f"{yy}H1"; ly = f"{lyy}H1"; l3m = f"{yy}Q1"
    elif mo == 9:
        ytd = f"{yy}Q1-Q3"; ly = f"{lyy}Q1-Q3"; l3m = f"{yy}Q2"
    elif mo == 12:
        ytd = f"{yy}H2"; ly = f"{lyy}H2"; l3m = f"{yy}Q3"
    else:
        ytd = "YTD"; ly = "LY"; l3m = "L3M"
    return ytd, ly, l3m, yy, lyy


# ====================== 结论持久化存储 ======================
_CONCLUSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conclusions.json")

# 历史结论月份颜色方案
_MONTH_COLORS = [
    "#1B4F8E", "#2E7D32", "#E65100", "#6A1B9A", "#C62828",
    "#00838F", "#F57F17", "#283593", "#558B2F", "#AD1457",
]

def _parse_conclusion_markup(text):
    """Parse conclusion markup tags to HTML.
    Supports both half-width [r] and full-width brackets.
    [g]text[/g] -> green, [r]text[/r] -> red, [b]text[/b] -> bold, [o]text[/o] -> orange
    """
    import re as _re
    if not text:
        return ""
    # Normalize full-width brackets to half-width before parsing
    text = text.replace('\u3010', '[').replace('\u3011', ']')   # 【 】
    text = text.replace('\uFF3B', '[').replace('\uFF3D', ']')   # full-width [ ]
    text = text.replace('\u3014', '[').replace('\u3015', ']')   # 〔 〕
    # Escape HTML special chars
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Convert literal backslash-n to actual newlines
    text = text.replace('\\n', '\n')
    # Parse markup tags
    text = _re.sub(r'\[g\](.*?)\[/g\]', r'<span style="color:#00B050;font-weight:700">\1</span>', text, flags=_re.DOTALL)
    text = _re.sub(r'\[r\](.*?)\[/r\]', r'<span style="color:#FF0000;font-weight:700">\1</span>', text, flags=_re.DOTALL)
    text = _re.sub(r'\[b\](.*?)\[/b\]', r'<span style="font-weight:700;font-size:1.1em">\1</span>', text, flags=_re.DOTALL)
    text = _re.sub(r'\[o\](.*?)\[/o\]', r'<span style="color:#002060;font-weight:700">\1</span>', text, flags=_re.DOTALL)
    text = _re.sub(r'\[s\](.*?)\[/s\]', r'<span style="font-size:0.85em">\1</span>', text, flags=_re.DOTALL)
    text = _re.sub(r'\[i\](.*?)\[/i\]', r'<span style="font-style:italic">\1</span>', text, flags=_re.DOTALL)
    text = _re.sub(r'\[u\](.*?)\[/u\]', r'<span style="text-decoration:underline">\1</span>', text, flags=_re.DOTALL)
    # Split by \n and wrap each paragraph in a div for visual separation
    paragraphs = text.split('\n')
    html_parts = []
    for i, para in enumerate(paragraphs):
        if i > 0:
            html_parts.append('<div style="margin-top:8px">' + para + '</div>')
        else:
            html_parts.append('<div>' + para + '</div>')
    return ''.join(html_parts)

def _load_conclusions():
    """从 JSON 文件加载所有保存的结论"""
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"):
        try:
            with open(_CONCLUSION_FILE, "r", encoding=enc) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            continue
    return {}

def _save_conclusion(page_key, month, text):
    """保存单条结论到 JSON 文件 - 永不删除已有结论"""
    if not text or not text.strip():
        return  # 空文本不保存也不删除，防止意外清空
    data = _load_conclusions()
    if page_key not in data:
        data[page_key] = {}
    data[page_key][month] = text.strip()
    try:
        with open(_CONCLUSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def render_conclusion(page_key, month):
    """渲染结论输入框（带持久化和历史展示）- 放在内容概况下方，自适应高度"""
    all_conclusions = _load_conclusions()
    page_conclusions = all_conclusions.get(page_key, {})
    current_text = page_conclusions.get(month, "")

    widget_key = f"concl_{page_key}_{month}"
    month_label = ym_lab(month) if month else ""

    # 初始化 session_state
    if widget_key not in st.session_state:
        st.session_state[widget_key] = current_text

    # 动态计算高度：根据文本内容自适应，不需要滑动
    _text_for_height = st.session_state.get(widget_key, current_text)
    if _text_for_height and _text_for_height.strip():
        char_per_line = 42
        _lines = _text_for_height.strip().split('\n')
        total_lines = sum(max(1, (len(line) + char_per_line - 1) // char_per_line) for line in _lines)
        calc_height = max(50, total_lines * 32 + 24)
    else:
        calc_height = 50

    # 已按需求移除“结论 (26M7)”标题，直接展示结论内容框
    # Use latest text from session_state for immediate display update
    display_text = st.session_state.get(widget_key, current_text)
    # Show formatted HTML display if text exists, otherwise show text_area
    if display_text and display_text.strip():
        formatted_html = _parse_conclusion_markup(display_text)
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#FFFBF0,#FFF8E1);border:2px solid #FFB300;'
            'border-radius:8px;padding:8px 14px;font-size:17px;line-height:1.4;color:#002060;font-family:Arial,Microsoft YaHei,微软雅黑,sans-serif;margin:16px 0 14px 0;">'
            f'{formatted_html}</div>',
            unsafe_allow_html=True
        )
        # Editable area inside expander
        with st.expander("编辑结论", expanded=False):
            st.text_area(
                f"结论 ({month_label})",
                height=calc_height,
                key=widget_key,
                placeholder="请输入本页结论...",
                label_visibility="collapsed"
            )
    elif not (display_text and display_text.strip()):
        st.text_area(
            f"结论 ({month_label})",
            height=calc_height,
            key=widget_key,
            placeholder="请输入本页结论...",
            label_visibility="collapsed"
        )

    # 自动保存：仅在非首次渲染时保存（防止页面刷新时清空结论）
    first_render_key = f"_fr_{widget_key}"
    is_first_render = first_render_key not in st.session_state
    st.session_state[first_render_key] = True

    if not is_first_render:
        new_text = st.session_state.get(widget_key, current_text)
        if new_text != current_text and new_text and new_text.strip():
            _save_conclusion(page_key, month, new_text)

    # 历史结论不再显示，只显示当月结论

# ====================== v2 Helper: sparse x-axis labels ======================

def _sparse_text_labels(values, threshold=12):
    """When data points are dense (>threshold), show text labels every other point."""
    n = len(values)
    if n <= threshold:
        return [f"{v}" for v in values]
    return [f"{v}" if i % 2 == 0 else "" for i, v in enumerate(values)]

def _sparse_xaxis(fig, labels, threshold=12):
    """When x-axis labels are too dense (>threshold), show every other one."""
    if len(labels) > threshold:
        tick_text = [l if i % 2 == 0 else "" for i, l in enumerate(labels)]
        fig.update_xaxes(ticktext=tick_text, tickvals=list(range(len(labels))))
    return fig




def fmt_num(v):
    return "-" if pd.isna(v) else f"{v:,.0f}"


# ====================== 6. all_months, ind_months, ym_id_map, YM_LABS ======================
all_months = sorted(sku_df["year_month"].dropna().unique())
ind_months = sorted(df_ind["year_month"].unique())
ym_id_map = dict(zip(sku_df["year_month"], sku_df["ym_id"]))
YM_LABS = [ym_lab(m) for m in ind_months]

# ====================== 7. Merged CSS ======================
st.markdown("""
<style>
    html, body, [class*="css"] { font-size: 14px !important; font-family: "Microsoft YaHei", Arial, sans-serif; }
    .block-container { padding-top: 0.5rem; background: #F7F9FC; max-width: 100% !important; }
    .main .block-container { max-width: 100% !important; padding: 0.6rem 1.35rem 1rem !important; background: #F7F9FC; }
    div.block-container { max-width: 100% !important; padding: 0.5rem 1.5rem !important; }

    /* 侧边栏精致小巧 */
    section[data-testid="stSidebar"] {
        background: #fff;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .block-container {
        padding: 1rem !important;
    }
    section[data-testid="stSidebar"] .stRadio > div {
        gap: 4px;
    }
    section[data-testid="stSidebar"] .stRadio label {
        font-size: 13px !important;
        padding: 6px 10px;
        border-radius: 6px;
        margin: 0;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        background: #F1F5F9;
    }
    section[data-testid="stSidebar"] .stSelectbox label {
        font-size: 12px !important;
        color: #64748B;
        margin-bottom: 2px;
    }
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        min-height: 32px !important;
        padding: 0 10px !important;
    }

    /* 统一表格 dt (Part A) */
    .dt {
        width: 100%; border-collapse: collapse; font-size: 14px;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .dt th, .dt td { border: 1px solid #E4E9F0; padding: 8px 10px; text-align: center; vertical-align: middle; font-family: Arial, "Microsoft YaHei", sans-serif; height: 42px; }
    .dt th { background: #EEF2FA; font-weight: 600; color: #1A1A2E; font-size: 14px; height: 42px; }
    .dt td:first-child { text-align: left; font-weight: 600; }
    .dt tr:hover td { background: #F0F4FF; }

    /* page2 专用表格 */
    .dt-p2 {
        width: 100%; border-collapse: collapse; font-size: 16px;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        table-layout: fixed;
        height: 460px;
    }
    .dt-p2 tr { height: calc(460px / 6); }
    .dt-p2 th { border: 1px solid #E4E9F0; background: #EEF2FA; font-weight: 600; color: #1A1A2E; font-size: 16px; padding: 6px 6px; line-height: 1.2; text-align: center; vertical-align: middle; }
    .dt-p2 td { border: 1px solid #E4E9F0; padding: 6px 10px; text-align: center; vertical-align: middle; font-size: 16px; }
    .dt-p2 td:first-child { text-align: left; font-weight: 600; }
    .dt-p2 tbody tr:hover td { background: #F0F4FF; }

    /* page3 专用表格 */
    .dt-p3 {
        width: 100%; border-collapse: collapse; font-size: 16px;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        table-layout: fixed;
    }
    .dt-p3 th, .dt-p3 td { border: 1px solid #E4E9F0; padding: 6px 4px; text-align: center; vertical-align: middle; font-size: 13px; }
    .dt-p3 th { background: #EEF2FA; font-weight: 600; color: #1A1A2E; font-size: 13px; }
    .dt-p3 td:first-child { text-align: left; font-weight: 600; padding-left: 10px; }
    .dt-p3 th:first-child { text-align: left; padding-left: 10px; }
    .dt-p3 tr:hover td { background: #F0F4FF; }

    /* page4 专用表格 */
    .table-wrapper {
        overflow-x: auto;
        overflow-y: hidden;
        width: 100%;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
    }
    .table-footer-wrapper {
        display: block;
        text-align: left;
        width: 100%;
    }
    .dashboard-table {
        border-collapse: collapse;
        width: 100%;
        font-size: 15px;
        font-family: "Microsoft YaHei", Arial, sans-serif;
        table-layout: auto;
        white-space: nowrap;
        margin: 0 auto;
    }
    .dashboard-table th, .dashboard-table td {
        border: 1px solid #D9D9D9;
        padding: 7px 9px;
        text-align: center;
        vertical-align: middle;
    }
    .top-header th { color: white; font-weight: 600; padding: 7px 5px; line-height: 1.3; font-size: 16px; }
    .cat-header { background: #2E5E3A; }
    .sales-header-a { background: #6B5B2E; }
    .growth-header-a { background: #6B5B2E; }
    .brand-header { background: #1B4F8E; }
    .sales-header-b { background: #1B4F8E; }
    .growth-header-b { background: #1B4F8E; }
    .share-header { background: #1B4F8E; }
    .sub-header th { color: white; font-weight: 600; font-size: 15px; padding: 6px 5px; }
    .dashboard-table tbody tr:nth-child(odd) { background: #FAFBFC; }
    .dashboard-table tbody tr:nth-child(even) { background: #FFFFFF; }
    .dashboard-table tbody tr:hover { background: #F0F4FF; }
    .cat-name { text-align: left; font-weight: 600; color: #2E5E3A; padding-left: 10px !important; width: 120px; }
    .cat-name .sub-no-otc { font-size: 13px; color: #000000; font-weight: bold; margin-left: 3px; }
    .cat-name .sub-yes-otc { font-size: 13px; color: #888888; font-weight: normal; margin-left: 3px; }
    .brand-name { font-weight: 600; color: #1B4F8E; width: 100px; }
    .brand-name .brand-sub { font-size: 13px; color: #1B4F8E; font-weight: normal; margin-left: 2px; }
    .num { font-variant-numeric: tabular-nums; width: 68px; position: relative; font-family: Arial, "Microsoft YaHei", sans-serif; }
    .sales-bold { font-weight: 700; font-family: Arial, "Microsoft YaHei", sans-serif; }
    .bar-cell { position: relative; overflow: hidden; }
    .bar-bg { position: absolute; left: 0; top: 0; bottom: 0; z-index: 1; opacity: 0.75; }
    .bar-text { position: relative; z-index: 2; font-weight: 700; }
    .share-change { display: table-cell; }
    .share-change span { display: inline-block; vertical-align: middle; }

    .footer-note {
        margin-top: 10px;
        font-size: 12px;
        color: #666;
        line-height: 1.5;
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        width: 100%;
        box-sizing: border-box;
    }
    .footer-left { text-align: left; flex: 1; padding-right: 16px; }
    .footer-right { text-align: right; white-space: nowrap; }
    .footer-note p { margin: 2px 0; }
    .legend-circle {
        display: inline-block; width: 10px; height: 10px;
        border-radius: 50%; vertical-align: middle; margin: 0 3px 0 6px;
    }
    .legend-circle.green { background: #00B050; }
    .legend-circle.yellow { background: #FFC000; }
    .legend-circle.red { background: #FF0000; }
    .legend-text.green { color: #00B050; font-weight: 600; }
    .legend-text.red { color: #FF0000; font-weight: 600; }
    .legend-text.yellow { color: #FFC000; font-weight: 600; }

    /* 紧凑分割线 */
    hr {
        margin: 12px 0 !important;
    }

    /* ====== 以下来自 merged_dashboard CSS ====== */
    /* columns 等高拉伸 */
    div[data-testid="stHorizontalBlock"] { align-items: stretch !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: stretch !important;
        justify-content: flex-start !important;
    }
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {
        height: 100% !important;
        flex: 1 1 auto !important;
    }
    div[data-testid="stVerticalBlock"] { height: 100%; }
    /* 页面标题 */
    .page-title { background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%); color: white; padding: 12px 18px; border-radius: 0 0 10px 10px; font-size: 19px; font-weight: 800; letter-spacing: 0.03em; margin-bottom: 12px; }
    /* 品类按钮 */
    .stButton > button { height: 38px !important; border-radius: 11px !important; font-size: 16px !important; letter-spacing: 0.02em !important; transition: all 0.18s ease-in-out !important; }
    .stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #F5A623 0%, #F08A00 100%) !important;
        border: 1px solid rgba(245,166,35,0.95) !important;
        color: white !important;
        font-weight: 800 !important;
        box-shadow: 0 6px 14px rgba(245,166,35,0.28), inset 0 1px 0 rgba(255,255,255,0.35) !important;
    }
    .stButton > button[kind="secondary"], .stButton > button[data-testid="stBaseButton-secondary"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #F7FAFF 100%) !important;
        border: 1px solid #D8E2F0 !important;
        color: #23415F !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px rgba(27,79,142,0.08) !important;
    }
    .stButton > button[kind="secondary"]:hover, .stButton > button[data-testid="stBaseButton-secondary"]:hover {
        background: linear-gradient(180deg, #FFF8E8 0%, #FFF1CC 100%) !important;
        border-color: #F5A623 !important;
        color: #9A5B00 !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 14px rgba(245,166,35,0.16) !important;
    }
    /* 筛选卡 / 注释条 */
    .filter-card { background: white; border: 1px solid #DCE3EF; border-radius: 10px; padding: 10px 14px; margin: 8px 0 10px; box-shadow: 0 2px 8px rgba(27,79,142,0.06); }
    /* first_page 元素 */
    .cat-badge {
        display: inline-flex;
        align-items: center;
        box-sizing: border-box;
        background: #1B4F8E;
        color: white;
        font-size: 14px;
        font-weight: 700;
        padding: 4px 14px;
        border-radius: 4px;
        margin-bottom: 8px;
        height: 28px;
        line-height: 20px;
        white-space: nowrap;
    }
    .phdr {
        background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%);
        color: white;
        border-radius: 10px;
        padding: 4px 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        box-shadow: 0 3px 12px rgba(27,79,142,0.18);
    }
    .phdr h2 { margin: 0; font-size: 15px; color: white; font-weight: 800; letter-spacing: 0.02em; line-height: 1.2; }
    .fcard {
        background: #fff;
        border: 1px solid #DCE3EF;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .frow { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
    /* “编辑结论”折叠框：去外围框线、透明背景、标题文字/箭头与浅蓝背景 #F7F9FC 同色（视觉不可见） */
    [data-testid="stExpander"],
    [data-testid="stExpander"] details,
    [data-testid="stExpander"] summary,
    [data-testid="stExpanderDetails"] {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        background: transparent !important;
    }
    [data-testid="stExpander"] {
        width: 100%;
        margin: 2px 0 0 0 !important;
        padding: 0 !important;
        overflow: visible !important;
    }
    [data-testid="stExpander"] details {
        padding: 0 !important;
        margin: 0 !important;
    }
    [data-testid="stExpander"] summary {
        min-height: 0 !important;
        height: 24px !important;
        line-height: 24px !important;
        padding: 0 4px !important;
        margin: 0 !important;
        gap: 6px !important;
        list-style: none;
        cursor: pointer;
    }
    [data-testid="stExpander"] summary::-webkit-details-marker { display: none !important; }
    [data-testid="stExpander"] summary:hover,
    [data-testid="stExpander"] summary:focus,
    [data-testid="stExpander"] summary:hover *,
    [data-testid="stExpander"] summary:focus * { background: transparent !important; }
    /* 标题文字与箭头：改成浅蓝背景色 #F7F9FC */
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary *,
    [data-testid="stExpander"] [data-testid="stIconMaterial"],
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
        color: #F7F9FC !important;
        fill: #F7F9FC !important;
        background: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        font-size: 13px !important;
        margin: 0 !important;
    }
    [data-testid="stExpanderDetails"] { padding: 4px 2px 2px !important; }
    /* 兼容旧版 Streamlit DOM */
    div.streamlit-expander,
    .streamlit-expanderHeader,
    .streamlit-expanderContent {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }
    .streamlit-expanderHeader,
    .streamlit-expanderHeader * {
        color: #F7F9FC !important;
        fill: #F7F9FC !important;
    }
    .metric-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 17px;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        background: white;
        table-layout: fixed;
        height: 100%;
    }
    .metric-table th, .metric-table td {
        border: 1px solid #E4E9F0;
        padding: 14px 4px;
        text-align: center;
        vertical-align: middle;
        white-space: nowrap;
    }
    .metric-table th { line-height: 1.5; background: #EEF2FA; font-weight: 700; color: #1A1A2E; font-size: 16px; padding: 8px 6px; }
    .metric-table td { line-height: 1.5; padding: 8px 6px; font-size: 16px; }
    .metric-table.compact td { line-height: 1.5; padding: 8px 6px; font-size: 16px; }
    .metric-table td:first-child { text-align: left; font-weight: 700; padding-left: 12px; min-width: 126px; }
    .metric-table .value { font-size: 16px; font-weight: 600; font-variant-numeric: tabular-nums; font-family: Arial, "Microsoft YaHei", sans-serif; }
    .metric-table tbody tr:hover td { background: #F0F4FF; }
    .metric-table .cat-h { background: #F7D794; color: #1A1A2E; }
    .metric-table .otc-h { background: #FFF3CD; color: #1A1A2E; }
    .metric-table .vds-h { background: #FFEBC1; color: #1A1A2E; }
    .metric-table .brand-h { background: #D6EAF8; color: #1A1A2E; }
    .left-content-wrap {
        display: flex;
        flex-direction: column;
    }
    .left-content-wrap .metric-table {
        flex: 1 1 auto;
        height: 100%;
        width: 100%;
    }
    .chart-title {
        font-size: 14px;
        font-weight: 600;
        color: #1A1A2E;
        margin-bottom: 6px;
    }
    .growth-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        background: white;
    }
    .growth-table th, .growth-table td {
        border: 1px solid #E4E9F0;
        padding: 5px 4px;
        text-align: center;
        vertical-align: middle;
    }
    .growth-table th {
        background: #EEF2FA;
        font-weight: 600;
        color: #1A1A2E;
        font-size: 13px;
        font-family: Arial, "Microsoft YaHei", sans-serif;
    }
    .growth-table th:first-child { text-align: left; padding-left: 8px; }
    .growth-table td:first-child { text-align: left; font-weight: 600; padding-left: 8px; width: 100px; }
    .growth-table td { font-family: Arial, "Microsoft YaHei", sans-serif; }
    .growth-table tbody tr:hover td { background: #F0F4FF; }
    .neg { color: #E53935; }
    .pos10 { color: #00B050; }
    .caption { font-size: 11px; color: #666; margin-top: 10px; }
    div[data-testid="stPlotlyChart"] {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        margin-right: 0 !important;
    }
    /* Tighten gap between consecutive plotly charts only (not text/table elements) */
    div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stPlotlyChart"] + div[data-testid="stPlotlyChart"] {
        margin-top: -14px !important;
    }
    /* brand_analysis 表格 */
    .brand-table { width: 100%; border-collapse: collapse; table-layout: fixed; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 5px rgba(0,0,0,0.08); font-size: 13px; }
    .brand-table th, .brand-table td { border: 1px solid #D6DDE8; padding: 6px 4px; text-align: center; vertical-align: middle !important; white-space: nowrap; line-height: 1.35; height: 29px; font-family: Arial, "Microsoft YaHei", sans-serif; }
    .brand-table th { background: #B0B0B0; color: #111827; font-weight: 800; }
    .brand-table .brand-col { width: 88px; }
    .brand-table .attr-col { width: 70px; font-size: 12px; }
    .brand-table .group-head { background: #B0B0B0; font-size: 13px; font-weight: 800; }
    .brand-table .sub-head { background: #B0B0B0; font-size: 12px; }
    .brand-table .cat-row td { background: #F2F2F2; font-weight: 800; }
    .brand-table .affiliate-row td { background: #FFF2CC; }
    .brand-table .focus-row td { background: #FFFFFF; }
    .brand-table .share-growth-row td { background: #E2F0D9; }
    .brand-table .neg { color: #E53935; }
    .brand-table .pos { color: #00A85A; }
    .brand-table .plain { color: #111827; }
    .brand-table .neg-share { color: #E53935; font-style: italic; }
    .brand-table .pos-share { color: #00A85A; font-style: italic; }
    .brand-table tr:hover td { background: #EEF4FF; }

    /* ====== Tab 导航美化 ====== */
    /* Tab list - cylindrical pill shape, first tab offset right 0.5cm, gap 0.5cm */
    div[data-testid="stTabs"] [role="tablist"],
    .stTabs [role="tablist"],
    div[data-testid="stTabs"] > div > div > div[role="tablist"] {
        gap: 0.5cm !important;
        overflow: visible !important;
        padding-left: 0.5cm !important;
    }
    /* Tab buttons - cylindrical pill shape */
    div[data-testid="stTabs"] [data-testid="stTab"],
    div[data-testid="stTabs"] [role="tab"],
    .stTabs [data-testid="stTab"] {
        height: 42px !important;
        min-height: 42px !important;
        border-radius: 21px !important;  /* 圆柱形/胶囊形状 = height/2 */
        border: 1px solid #D8E2F0 !important;
        background: linear-gradient(180deg, #F8FAFF, #EEF2FA) !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        color: #5B7A9E !important;
        padding: 0 28px !important;
        line-height: 40px !important;
        box-sizing: border-box !important;
    }
    div[data-testid="stTabs"] [data-testid="stTab"]:hover,
    div[data-testid="stTabs"] [role="tab"]:hover {
        background: linear-gradient(180deg, #FFF8E8, #FFF1CC) !important;
        color: #9A5B00 !important;
        border-color: #F5A623 !important;
    }
    div[data-testid="stTabs"] [aria-selected="true"],
    div[data-testid="stTabs"] [data-testid="stTab"][data-selected="true"] {
        background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%) !important;
        color: white !important;
        border-color: #1B4F8E !important;
    }
    /* Hide default underline indicator */
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
    div[data-testid="stTabs"] [role="tab"]::after,
    div[data-testid="stTabs"] .react-aria-SelectionIndicator {
        display: none !important;
        height: 0 !important;
        opacity: 0 !important;
    }

    /* ====== Part B 美化 ====== */
    /* 主标题（Part B 顶部） */
    .partb-header {
        background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%);
        color: white;
        padding: 10px 18px;
        border-radius: 10px;
        font-size: 15px;
        font-weight: 800;
        letter-spacing: 0.02em;
        margin-bottom: 12px;
        box-shadow: 0 3px 12px rgba(27,79,142,0.18);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .partb-header .sub { font-size: 11px; font-weight: 400; opacity: 0.85; }

    /* 品类选择器容器 */
    .cat-selector-wrap {
        background: white;
        border: 1px solid #DCE3EF;
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 10px rgba(27,79,142,0.06);
    }
    .cat-selector-label {
        font-size: 12px;
        color: #64748B;
        font-weight: 600;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Section 标题卡片 */
    .section-header {
        background: linear-gradient(90deg, #1B4F8E 0%, #2E6BB8 100%);
        color: white;
        padding: 6px 16px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
        margin: 8px 0 8px;
        display: flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 2px 8px rgba(27,79,142,0.12);
    }
    .section-header .num {
        background: #F5A623;
        color: white;
        border-radius: 50%;
        width: 24px;
        height: 24px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 800;
        flex-shrink: 0;
    }

    /* 导出完整报告：每个品类的小标题 + 分隔（仅打印/导出时才有意义） */
    .cat-export-title {
        font-size: 19px;
        font-weight: 800;
        color: #102F57;
        margin: 22px 0 10px;
        padding-left: 10px;
        border-left: 5px solid #F5A623;
        font-family: 'Microsoft YaHei', Arial, sans-serif;
    }
    .cat-export-break {
        height: 10px;
    }

    /* Part B 筛选器美化 */
    .partb-filter {
        background: white;
        border: 1px solid #DCE3EF;
        border-radius: 10px;
        padding: 12px 18px;
        margin: 10px 0 14px;
        box-shadow: 0 2px 8px rgba(27,79,142,0.06);
    }

    /* 页面顶部主标题 */
    .main-header {
        background: linear-gradient(135deg, #0F2D52 0%, #1B4F8E 50%, #2E6BB8 100%);
        color: white;
        padding: 16px 28px;
        border-radius: 0 0 14px 14px;
        font-size: 22px;
        font-weight: 800;
        letter-spacing: 0.04em;
        margin-bottom: 0;
        box-shadow: 0 4px 16px rgba(15,45,82,0.25);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .main-header .badge {
        background: rgba(245,166,35,0.9);
        color: white;
        font-size: 12px;
        font-weight: 600;
        padding: 3px 12px;
        border-radius: 20px;
    }

    /* 确保 tab 内容不被遮挡 */
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 8px;
    }

    /* ====== 全局顶部留白，让标题下移 ====== */
    .main .block-container {
        padding-top: 7rem !important;
    }

    /* ====== 时间选择器 & 滚轴美化 ====== */
    .time-selector-wrap {
        background: linear-gradient(135deg, #FFFFFF 0%, #F0F7FF 100%);
        border: 1px solid #B8D4F0;
        border-radius: 14px;
        padding: 14px 20px;
        margin: 10px 0 16px;
        box-shadow: 0 3px 14px rgba(27,79,142,0.10);
    }
    .time-selector-label {
        font-size: 13px;
        color: #1B4F8E;
        font-weight: 700;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .time-selector-label .dot {
        width: 8px; height: 8px; border-radius: 50%; background: #F5A623;
        display: inline-block;
    }

    /* ====== select_slider 美化（baseweb slider） ====== */
    div[data-baseweb="select-slider"] [role="slider"] {
        background: #1B4F8E !important;
        border: 3px solid white !important;
        box-shadow: 0 2px 6px rgba(27,79,142,0.30) !important;
    }
    div[data-baseweb="select-slider"] > div > div {
        background: #D8E2F0 !important;
    }
    div[data-baseweb="select-slider"] [data-baseweb="thumb"] {
        background: #F5A623 !important;
    }


    /* ====== 结论输入框样式（无标题，自适应高度） ====== */
    div[data-testid="stTextArea"] textarea {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #1A1A2E !important;
        background: rgba(255,255,255,0.92) !important;
        border: 2px solid #F5A623 !important;
        border-radius: 6px !important;
        line-height: 1.6 !important;
        overflow: hidden !important;
        resize: none !important;
    }
    div[data-testid="stTextArea"] [data-baseweb="base-input"] {
        border: none !important;
        background: transparent !important;
    }
    div[data-testid="stTextArea"] {
        background: linear-gradient(135deg, #FFF8E1 0%, #FFF3CD 100%);
        border: 2px solid #F5A623;
        border-radius: 8px;
        padding: 8px 12px;
        box-shadow: 0 2px 8px rgba(245,166,35,0.15);
    }

    /* ====== 历史结论展示样式 ====== */
    .conclusion-history {
        margin: 8px 0 4px;
        border-radius: 8px;
        overflow: hidden;
    }
    .conclusion-history-title {
        font-size: 17px;
        font-weight: 700;
        color: #555;
        margin-bottom: 6px;
        padding-left: 4px;
    }
    .conclusion-history-item {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 8px 12px;
        margin-bottom: 4px;
        border-radius: 6px;
        border-left: 4px solid;
        background: rgba(255,255,255,0.6);
    }
    .conclusion-history-month {
        font-size: 17px;
        font-weight: 700;
        white-space: nowrap;
        min-width: 50px;
        font-family: Arial, sans-serif;
    }
    .conclusion-history-text {
        font-size: 17px;
        color: #333;
        line-height: 1.5;
        font-weight: 500;
    }

    /* ====== selectbox 美化 ====== */
    div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border-color: #B8D4F0 !important;
    }
    div[data-baseweb="select"] > div:hover {
        border-color: #F5A623 !important;
    }

    /* 图例取样线：实线 1.2px（默认约2px，偏细更清爽）；
       虚线因断口视觉上偏细，单独加粗到 2.4px 补偿，使实/虚线观感接近 */
    .legendlines path {
        stroke-width: 1.2px !important;
    }
    .legendlines path[style*="dasharray"],
    .legendlines path[stroke-dasharray] {
        stroke-width: 2.4px !important;
    }
</style>
""", unsafe_allow_html=True)

# ========================================================================
# PART A: 全国药店VDS市场表现 (来自 combined_dashboard)
# ========================================================================

# ====================== Part A 工具函数 ======================
def range_agg(d, s, e):
    sub = d[(d["ym_id"] >= s) & (d["ym_id"] <= e)]
    return sub.groupby("品类").agg(
        sale=(SALES_COL, "sum"),
        qty=("销售量-Pack('00))", "sum")
    ).reset_index()

def gv(agg, cat, col):
    r = agg[agg["品类"] == cat]
    return r[col].iloc[0] if len(r) else 0

def to_yi(x):   return x / 100000 if pd.notna(x) else 0

def to_yihe(x): return x / 1000000 if pd.notna(x) else 0

def uprice(sale_k, qty_h):
    return round(sale_k * 10 / qty_h) if qty_h else 0

def fn(v):
    return f"{round(v)}" if v >= 1 else f"{v:.1f}"

def gr(c, b):
    if pd.isna(b) or b == 0: return np.nan
    return c / b - 1

def gh(val):
    if pd.isna(val): return "<span style='color:#999'>—</span>"
    p = val * 100
    t = f"{p:.1f}%" if abs(round(p)) < 1 else f"{round(p)}%"
    c = "#E53935" if p < 0 else "#00B050"  # >0 绿色，<0 红色
    w = "600" if (p < 0 or p > 10) else "400"
    return f'<span style="color:{c};font-weight:{w}">{t}</span>'

# page2 工具函数
def total_vds_sales(df, months):
    mask = (df["品类"] == "VDS") & (df["year_month"].isin(months))
    return df.loc[mask, SALES_COL].sum()

def brand_sales(df, months, brand=None):
    # 汤臣倍健用CHC(营养补充剂)代表VDS（含OTC），其他品牌用VDS
    cat = "CHC(营养补充剂)" if brand == "汤臣倍健" else "VDS"
    mask = (df["品类"] == cat) & (df["year_month"].isin(months))
    if brand:
        mask = mask & (df["品牌"] == brand)
    return df.loc[mask, SALES_COL].sum()

def share_calc(df, months, brand, total):
    if total == 0:
        return 0.0
    return brand_sales(df, months, brand) / total * 100

def fmt_share_change(v):
    if pd.isna(v):
        return "-", C_TXT
    if v == 0:
        return "0.0", C_TXT
    if abs(v) < 0.05:
        s = f"{v:.2f}"
    else:
        s = f"{v:.1f}"
    color = "#00B050" if v > 0 else "#FF0000"
    return s, color

def brand_display_name(b):
    if "老百姓" in b:
        return f"<span style='line-height:1.1;'>老百姓<br><span style='font-size:11px;'>(维诺健)</span></span>"
    return f"<span style='line-height:1.1;'>{b}</span>"

# page3 工具函数
def ind_sales(month, condition):
    mask = df_ind["year_month"] == month
    for k, v in condition.items():
        mask = mask & (df_ind[k] == v)
    return df_ind.loc[mask, SALES_COL].sum() / 1000

def sku_sales(month, condition):
    mask = sku_df["year_month"] == month
    for k, v in condition.items():
        mask = mask & (sku_df[k] == v)
    return sku_df.loc[mask, SALES_COL].sum() / 1000

def calc_yoy_p3(df_full, month, key):
    y = int(month[:4])
    mon = int(month[4:])
    ly_m = f"{y - 1}{str(mon).zfill(2)}"
    curr = df_full[df_full["year_month"] == month][key].values
    ly = df_full[df_full["year_month"] == ly_m][key].values
    if len(curr) == 0 or len(ly) == 0 or ly[0] == 0:
        return np.nan
    return (curr[0] / ly[0] - 1) * 100

# page4 工具函数
def get_months(year, month, count=1):
    months = []
    y, m = year, month
    for _ in range(count):
        months.append(f"{y}{str(m).zfill(2)}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return sorted(months)

def sales_by_source(source, months, filters):
    if source == "brand":
        df = brand_df
        half_periods = set()
        for m in months:
            y = int(m[:4])
            mo = int(m[4:])
            half_periods.add(f"{y}H1" if mo <= 6 else f"{y}H2")
        mask = df["year_month"].isin(half_periods)
    else:
        df = df_ind if source == "industry" else sku_df
        mask = df["year_month"].isin(months)
    for k, v in filters.items():
        if isinstance(v, list):
            mask = mask & df[k].isin(v)
        else:
            mask = mask & (df[k] == v)
    return df.loc[mask, SALES_COL].sum() / 1000

def growth_rate(curr, ly):
    if ly == 0 or pd.isna(ly) or pd.isna(curr):
        return np.nan
    return (curr / ly - 1) * 100

def share_change_color(v):
    if pd.isna(v):
        return ("#ccc", "#333")
    if v > 0:
        return (GREEN, GREEN)
    if -0.5 <= v <= 0:
        return (YELLOW, RED)
    return (RED, RED)

def growth_color(v):
    if pd.isna(v):
        return "#333"
    return GREEN if v > 0 else RED

def format_pct(v, decimal=0):
    if pd.isna(v):
        return "-"
    return f"{v:+.0f}%" if decimal == 0 else f"{v:+.{decimal}f}%"

def format_share(v):
    if pd.isna(v):
        return "-"
    return f"{v:.1f}"

def format_sales(v):
    if pd.isna(v):
        return "-"
    return f"{v:,.0f}"

def circle_svg(color):
    return f'''<svg width="12" height="12" style="vertical-align:middle;margin-right:3px;">
        <circle cx="6" cy="6" r="5" fill="{color}" stroke="none"/>
    </svg>'''

# ====================== Part A PAGE 1: VDS+OTC 品类市场规模 ======================
def page1(sel_ym, SEL_M):
    ytd_label, ly_label, l3m_label, yy, lyy = period_labels(sel_ym)
    sl_l = ym_lab(SEL_M[0])
    sl_r = ym_lab(SEL_M[-1])
    st.markdown(f"""
    <div class="phdr">
        <h2>全国零售药店 — VDS+OTC 品类市场规模</h2>
    </div>
    """, unsafe_allow_html=True)

    render_conclusion("p1", sel_ym)

    sel_y = int(sel_ym[:4])
    sel_m = int(sel_ym[4:])
    ymid = sel_y * 12 + sel_m

    # VDS/OTC 筛选器已按需求移除，图例固定全部显示
    show_vds = True
    show_otc = True

    # YTD 计算
    ys = sel_y * 12 + 1
    ac = range_agg(df_ind, ys, ymid)
    al = range_agg(df_ind, (sel_y-1)*12+1, (sel_y-1)*12+sel_m)

    def ext(agg):
        sv = gv(agg, "VDS", "sale"); st_ = gv(agg, "CHC(营养补充剂)", "sale"); so = st_ - sv
        qv = gv(agg, "VDS", "qty"); qt = gv(agg, "CHC(营养补充剂)", "qty"); qo = qt - qv
        return sv, so, st_, qv, qo, qt

    cv, co, cT, cqv, cqo, cqT = ext(ac)
    lv, lo, lT, lqv, lqo, lqT = ext(al)

    cvw, cow, cTw = to_yi(cv), to_yi(co), to_yi(cT)
    lvw, low, lTw = to_yi(lv), to_yi(lo), to_yi(lT)
    cqvw, cqow, cqTw = to_yihe(cqv), to_yihe(cqo), to_yihe(cqT)
    lqvw, lqow, lqTw = to_yihe(lqv), to_yihe(lqo), to_yihe(lqT)

    cpv, cpo = uprice(cv, cqv), uprice(co, cqo)
    lpv, lpo = uprice(lv, lqv), uprice(lo, lqo)

    g_sv = gr(cvw, lvw); g_so = gr(cow, low); g_sT = gr(cTw, lTw)
    g_qv = gr(cqvw, lqvw); g_qo = gr(cqow, lqow); g_qT = gr(cqTw, lqTw)
    g_pv = gr(cpv, lpv); g_po = gr(cpo, lpo); g_pT = gr((cpv+cpo)/2, (lpv+lpo)/2)

    H = 280
    FZ = 16
    BW = 0.75
    BASE = dict(
        height=H,
        margin=dict(t=60, b=60, l=8, r=55),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(size=13, family="PingFang SC,Microsoft YaHei,sans-serif"),
        yaxis=dict(gridcolor="#EEF0F5", showticklabels=False, zeroline=False),
        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.0)
    )

    cL, cR = st.columns([0.47, 0.53], gap="medium")

    with cL:
        lgc, cc1, cc2, cc3 = st.columns([0.14, 1, 1, 1], gap="small")
        with lgc:
            # 图例盒（静态展示，不可勾选），垂直居中放置在图表左侧
            st.markdown(
                f"""<div style="display:flex;align-items:center;justify-content:center;height:305px;">
                <div style="padding:14px 16px;display:flex;flex-direction:column;gap:12px;">
                    <div style="display:flex;align-items:center;gap:8px;"><span style="width:13px;height:13px;background:{C_VDS};display:inline-block;"></span><span style="font-size:13px;color:{C_TXT};font-weight:500;">VDS</span></div>
                    <div style="display:flex;align-items:center;gap:8px;"><span style="width:13px;height:13px;background:{C_OTC};display:inline-block;"></span><span style="font-size:13px;color:{C_TXT};font-weight:500;">OTC</span></div>
                </div></div>""",
                unsafe_allow_html=True
            )
        with cc1:
            f1 = go.Figure()
            if show_otc:
                f1.add_bar(x=[ly_label, ytd_label], y=[low, cow], name="OTC",
                           marker_color=C_OTC, width=BW,
                           text=[fn(low), fn(cow)], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif"),
                           textangle=0, cliponaxis=False, legendrank=2)
            if show_vds:
                vds_base = [low, cow] if show_otc else [0, 0]
                f1.add_bar(x=[ly_label, ytd_label], y=[lvw, cvw], name="VDS",
                           marker_color=C_VDS, base=vds_base, width=BW,
                           text=[fn(lvw), fn(cvw)], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif"),
                           textangle=0, cliponaxis=False, legendrank=1)
            f1.update_layout(**BASE,
                title=dict(text="品类销售额<br><sup>(亿元)</sup>", font_size=13),
                barmode="stack", bargap=0.30, showlegend=False,
                xaxis=dict(tickfont=dict(size=13)))
            st.plotly_chart(f1, width='stretch')

        with cc2:
            f2 = go.Figure()
            if show_otc:
                f2.add_bar(x=[ly_label, ytd_label], y=[lqow, cqow], name="OTC",
                           marker_color=C_OTC, width=BW,
                           text=[fn(lqow), fn(cqow)], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif"),
                           textangle=0, cliponaxis=False, legendrank=2)
            if show_vds:
                vds_base = [lqow, cqow] if show_otc else [0, 0]
                f2.add_bar(x=[ly_label, ytd_label], y=[lqvw, cqvw], name="VDS",
                           marker_color=C_VDS, base=vds_base, width=BW,
                           text=[fn(lqvw), fn(cqvw)], textposition="outside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color=C_TXT, family="Arial, sans-serif"),
                           textangle=0, cliponaxis=False, legendrank=1)
            f2.update_layout(**BASE,
                title=dict(text="品类销售量<br><sup>(亿盒)</sup>", font_size=13),
                barmode="stack", bargap=0.30, showlegend=False,
                xaxis=dict(tickfont=dict(size=13)))
            st.plotly_chart(f2, width='stretch')

        with cc3:
            f3 = go.Figure()
            if show_vds:
                f3.add_bar(x=[ly_label, ytd_label], y=[lpv, cpv], name="VDS",
                           marker_color=C_VDS, width=0.33,
                           text=[f"{lpv}", f"{cpv}"], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif"),
                           cliponaxis=False, legendrank=1)
            if show_otc:
                f3.add_bar(x=[ly_label, ytd_label], y=[lpo, cpo], name="OTC",
                           marker_color=C_OTC, width=0.33,
                           text=[f"{lpo}", f"{cpo}"], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif"),
                           cliponaxis=False, legendrank=2)
            f3.update_layout(**BASE,
                title=dict(text="品类平均单价<br><sup>(元/盒)</sup>", font_size=13),
                barmode="group", bargap=0.35, bargroupgap=0.18, showlegend=False,
                xaxis=dict(tickfont=dict(size=13)))
            st.plotly_chart(f3, width='stretch')

        st.markdown(f"<b class='chart-title'>{ytd_label} 同比增速</b>", unsafe_allow_html=True)
        st.markdown(f"""
        <table class="dt">
        <tr>
            <th style='text-align:left;width:22%'>品类</th>
            <th>销售额同比</th><th>销量同比</th><th>均价同比</th>
        </tr>
        <tr>
            <td style='text-align:left;color:{C_VDS};font-weight:700'>● VDS</td>
            <td>{gh(g_sv)}</td><td>{gh(g_qv)}</td><td>{gh(g_pv)}</td>
        </tr>
        <tr>
            <td style='text-align:left;color:{C_OTC};font-weight:700'>● OTC</td>
            <td>{gh(g_so)}</td><td>{gh(g_qo)}</td><td>{gh(g_po)}</td>
        </tr>
        <tr style='background:#F5F7FF'>
            <td style='text-align:left;font-weight:700'>▸ VDS+OTC</td>
            <td>{gh(g_sT)}</td><td>{gh(g_qT)}</td><td>{gh(g_pT)}</td>
        </tr>
        </table>""", unsafe_allow_html=True)

    with cR:
        ma = df_ind.groupby(["year_month", "品类"])[SALES_COL].sum().reset_index()
        pc = ma.pivot(index="year_month", columns="品类", values=SALES_COL).fillna(0).reset_index()

        if "CHC(营养补充剂)" not in pc.columns or "VDS" not in pc.columns:
            st.warning("月度数据中缺少 VDS 或 CHC(营养补充剂) 品类，无法生成月度图表。")
        else:
            pc["OTCc"] = pc["CHC(营养补充剂)"] - pc["VDS"]
            pc["VDSc"] = pc["VDS"]
            pc["OTCc"] = pc["OTCc"].apply(to_yi)
            pc["VDSc"] = pc["VDSc"].apply(to_yi)

            ply = pc.copy()
            ply["year_month"] = ply["year_month"].apply(lambda y: f"{int(y[:4])+1}{y[4:]}")
            ply = ply.rename(columns={"VDSc": "VDSly", "OTCc": "OTCly"})

            mm = pd.merge(pc[["year_month", "VDSc", "OTCc"]],
                          ply[["year_month", "VDSly", "OTCly"]],
                          on="year_month", how="left")

            def mg(c, ly):
                if pd.isna(ly) or ly == 0: return np.nan
                return (c / ly) - 1

            mm["VG"] = mm.apply(lambda r: mg(r.VDSc, r.VDSly), axis=1)
            mm["OG"] = mm.apply(lambda r: mg(r.OTCc, r.OTCly), axis=1)
            mm["TG"] = mm.apply(lambda r: mg(r.VDSc + r.OTCc, r.VDSly + r.OTCly), axis=1)
            mm = mm[mm["year_month"].isin(SEL_M)].copy()

            if not mm.empty:
                om = {m: i for i, m in enumerate(ind_months)}
                mm["_o"] = mm["year_month"].map(om).astype(int)
                mm = mm.sort_values("_o").reset_index(drop=True)
                mm["lb"] = mm["year_month"].apply(ym_lab)

                fm = go.Figure()
                if show_otc:
                    fm.add_trace(go.Bar(x=mm["lb"], y=mm["OTCc"], name="OTC",
                        marker_color=C_OTC, width=BW, marker_line_width=0,
                        text=[fn(v) for v in mm["OTCc"]], textposition="inside",
                        insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif")))
                if show_vds:
                    vds_base_m = mm["OTCc"] if show_otc else [0] * len(mm)
                    fm.add_trace(go.Bar(x=mm["lb"], y=mm["VDSc"], name="VDS",
                        marker_color=C_VDS, base=vds_base_m, width=BW, marker_line_width=0,
                        text=[fn(v) for v in mm["VDSc"]], textposition="inside",
                        insidetextanchor="middle", textfont=dict(size=FZ, color="white", family="Arial, sans-serif"),
                        textangle=0))
                fm.update_layout(**{**BASE, "margin": dict(t=60, b=60, l=0, r=0)},
                                 barmode="stack", bargap=0.15, showlegend=False,
                                 uniformtext=dict(minsize=16, mode="show"),
                                 title=dict(text="品类销售额by月度<br><sup>(单位：亿元)</sup>", font_size=14),
                                 xaxis=dict(tickangle=-45, tickfont=dict(size=13), dtick=1, domain=[0.0, 1.0]))
                st.plotly_chart(fm, width='stretch')

                st.markdown(f"<div class='chart-title' style='margin-top:11px;display:block'>月度同比明细</div>", unsafe_allow_html=True)
                mlst = mm["lb"].tolist()
                n_m = len(mlst)
                tfs = "12px"
                hfs = "11.5px"  # 月度标签(25M1等)比数据小半个字号
                tdp = "6px 2px"
                hdr = "".join(f"<th style='font-size:{hfs};padding:{tdp};height:42px;text-align:center;white-space:nowrap'>{m}</th>" for m in mlst)
                vr = "".join(f"<td style='font-size:{tfs};padding:{tdp};height:42px;text-align:center;white-space:nowrap'>{gh(v)}</td>" for v in mm["VG"])
                orr = "".join(f"<td style='font-size:{tfs};padding:{tdp};height:42px;text-align:center;white-space:nowrap'>{gh(v)}</td>" for v in mm["OG"])
                trr = "".join(f"<td style='font-size:{tfs};padding:{tdp};height:42px;text-align:center;white-space:nowrap'>{gh(v)}</td>" for v in mm["TG"])

                st.markdown(f"""
                <table class="dt" style='width:100%;table-layout:fixed;margin-top:8px'>
                <colgroup>{"".join(f"<col style='width:{round(100/len(mlst),2)}%'>" for _ in mlst)}</colgroup>
                <tr>{hdr}</tr>
                <tr>{vr}</tr>
                <tr>{orr}</tr>
                <tr style='background:#F5F7FF'>{trr}</tr>
                </table>""", unsafe_allow_html=True)
            else:
                st.warning(f"范围内无数据 ({sl_l} ~ {sl_r})")

    st.divider()
    st.caption("""数据来源：中康全国零售药店
*注：VDS+OTC包含蓝帽子产品、健康食品及相关OTC产品（不含纯治疗作用OTC药品如感冒、止咳等）""")

# ====================== Part A PAGE 2: VDS 品牌份额 ======================
def page2(sel_month, trend_months):
    ytd_label, ly_label, l3m_label, yy, lyy = period_labels(sel_month)
    st.markdown(f"""
    <div class="phdr">
        <h2>VDS-Top5 品牌市场份额</h2>
    </div>
    """, unsafe_allow_html=True)

    sel_year = int(sel_month[:4])
    sel_mon = int(sel_month[4:])

    ytd_months = [f"{sel_year}{str(m).zfill(2)}" for m in range(1, sel_mon + 1)]
    ly_ytd_months = [f"{sel_year-1}{str(m).zfill(2)}" for m in range(1, sel_mon + 1)]
    sel_ym_id = sel_year * 12 + sel_mon
    ring_month = f"{sel_year}{str(sel_mon-1).zfill(2)}" if sel_mon > 1 else f"{sel_year-1}12"

    render_conclusion("p2", sel_month)

    vds_ytd_total = total_vds_sales(df_ind, ytd_months)
    vds_ly_total = total_vds_sales(df_ind, ly_ytd_months)
    vds_curr_total = total_vds_sales(df_ind, [sel_month])
    vds_ring_total = total_vds_sales(df_ind, [ring_month])

    brand_ytd = df_ind[(df_ind["品类"] == "VDS") & (df_ind["year_month"].isin(ytd_months)) &
                       (~df_ind["品牌"].str.contains("others|其他", case=False, na=False))].groupby("品牌")[SALES_COL].sum().sort_values(ascending=False)
    # 汤臣倍健用CHC(营养补充剂)替代VDS
    if "汤臣倍健" in brand_ytd.index:
        _tang_chc = df_ind[(df_ind["品类"] == "CHC(营养补充剂)") & (df_ind["品牌"] == "汤臣倍健") & (df_ind["year_month"].isin(ytd_months))][SALES_COL].sum()
        brand_ytd["汤臣倍健"] = _tang_chc
        brand_ytd = brand_ytd.sort_values(ascending=False)
    top5_brands = brand_ytd.head(5).index.tolist()

    if vds_ytd_total == 0 or vds_curr_total == 0:
        st.warning("所选月份暂无 VDS 数据，请检查数据源。")
        return

    color_map = {}
    for i, b in enumerate(top5_brands):
        color_map[b] = BRAND_COLORS.get(b, DEFAULT_COLORS[i % len(DEFAULT_COLORS)])

    metrics = []
    for b in top5_brands:
        ytd_share = share_calc(df_ind, ytd_months, b, vds_ytd_total)
        ly_share = share_calc(df_ind, ly_ytd_months, b, vds_ly_total)
        curr_share = share_calc(df_ind, [sel_month], b, vds_curr_total)
        ring_share = share_calc(df_ind, [ring_month], b, vds_ring_total)

        ytd_sales = brand_sales(df_ind, ytd_months, b)
        ly_sales = brand_sales(df_ind, ly_ytd_months, b)
        scale_yoy = (ytd_sales / ly_sales - 1) * 100 if ly_sales != 0 else np.nan

        metrics.append({
            "品牌": b,
            "YTD份额": ytd_share,
            "LY份额": ly_share,
            "当月份额": curr_share,
            "环期份额": ring_share,
            "YTD规模同比": scale_yoy,
            "YTD份额同比": ytd_share - ly_share,
            "份额环比": curr_share - ring_share,
        })

    metrics_df = pd.DataFrame(metrics)

    cL, cR = st.columns([0.5, 0.5], gap="medium")

    with cL:
        cL_chart, cL_table = st.columns([0.46, 0.54], gap="small")

        with cL_chart:
            st.markdown("<b class='chart-title'>VDS-Top5 企业市场份额 (%)</b>", unsafe_allow_html=True)
            fig = go.Figure()
            for b in top5_brands:
                m = metrics_df[metrics_df["品牌"] == b].iloc[0]
                fig.add_trace(go.Bar(
                    x=[ly_label], y=[m["LY份额"]], name=b,
                    marker_color=color_map[b], width=0.6,
                    text=[f"{m['LY份额']:.1f}"], textposition="inside",
                    insidetextanchor="middle", textfont=dict(size=16, color="white", family="Arial, sans-serif"),
                    showlegend=False
                ))
                fig.add_trace(go.Bar(
                    x=[ytd_label], y=[m["YTD份额"]], name=b,
                    marker_color=color_map[b], width=0.6,
                    text=[f"{m['YTD份额']:.1f}"], textposition="inside",
                    insidetextanchor="middle", textfont=dict(size=16, color="white", family="Arial, sans-serif"),
                    showlegend=False
                ))

            cr5_ly = metrics_df["LY份额"].sum()
            cr5_ytd = metrics_df["YTD份额"].sum()
            fig.add_annotation(x=ly_label, y=cr5_ly, text=f"<b>{cr5_ly:.1f}</b>",
                               showarrow=False, font=dict(size=16, color=C_TXT, family="Arial, sans-serif"), yshift=12)
            fig.add_annotation(x=ytd_label, y=cr5_ytd, text=f"<b>{cr5_ytd:.1f}</b>",
                               showarrow=False, font=dict(size=16, color=C_TXT, family="Arial, sans-serif"), yshift=12)

            # Single total share change annotation between LY and YTD (dynamic labels)
            _total_diff = cr5_ytd - cr5_ly
            if not pd.isna(_total_diff):
                _tclr = "#00B050" if _total_diff >= 0 else "#E53935"
                _tarr = "\u2191" if _total_diff >= 0 else "\u2193"
                _tmax = max(cr5_ly, cr5_ytd)
                # Arrow annotation - large and bold
                fig.add_annotation(x=0.5, y=_tmax, text=f"<b>{_tarr}</b>",
                                   showarrow=False,
                                   font=dict(size=34, color=_tclr, family="Arial, sans-serif"),
                                   xshift=-40, yshift=24, xanchor="center")
                # Value annotation - bold
                fig.add_annotation(x=0.5, y=_tmax, text=f"<b>{_total_diff:+.1f}</b>",
                                   showarrow=False,
                                   font=dict(size=22, color=_tclr, family="Arial, sans-serif"),
                                   xshift=0, yshift=22, xanchor="center")
                fig.update_layout(xaxis=dict(range=[-0.5, 1.5]))

            _y_max = max(cr5_ly, cr5_ytd) * 1.12
            fig.update_layout(
                height=460,
                barmode="stack",
                bargap=0.35,
                margin=dict(t=30, b=25, l=10, r=55),
                paper_bgcolor="white",
                plot_bgcolor="white",
                font=dict(size=13, family="Microsoft YaHei, Arial, sans-serif"),
                xaxis=dict(showgrid=False, tickfont=dict(size=8)),
                yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, range=[0, _y_max]),
                showlegend=False,
                uniformtext=dict(mode="show", minsize=16),
            )
            st.plotly_chart(fig, width='stretch')

        with cL_table:
            st.markdown(f"<b class='chart-title'>{ytd_label} 规模同比 & 份额变化</b>", unsafe_allow_html=True)
            table_rows = []
            for _, r in metrics_df[::-1].iterrows():
                sy = r["YTD规模同比"]
                ss = r["YTD份额同比"]
                sr = r["份额环比"]
                c = color_map[r['品牌']]
                ss_str, ss_color = fmt_share_change(ss)
                sr_str, sr_color = fmt_share_change(sr)
                if pd.isna(sy):
                    sy_str, sy_color = "-", C_TXT
                else:
                    sy_str = f"{sy:+.0f}%" if sy != 0 else "0%"
                    sy_color = "#00B050" if sy > 0 else "#FF0000"
                table_rows.append(
                    f"<tr><td style='color:{c};font-weight:600;'>"
                    f"<span style='display:inline-flex;align-items:center;'>"
                    f"<span style='width:10px;height:10px;border-radius:2px;background:{c};margin-right:6px;flex-shrink:0;'></span>"
                    f"{brand_display_name(r['品牌'])}</span></td>"
                    f"<td style='color:{sy_color}'>{sy_str}</td>"
                    f"<td style='color:{ss_color}'>{ss_str}</td>"
                    f"<td style='color:{sr_color}'>{sr_str}</td></tr>"
                )

            table_html = (
                f"<table class='dt-p2'>"
                f"<colgroup><col style='width:35%'><col style='width:21.67%'><col style='width:21.67%'><col style='width:21.67%'></colgroup>"
                f"<thead><tr><th>品牌</th><th>{ytd_label}<br>规模同比</th><th>{ytd_label}<br>份额同比</th><th>{sel_month[2:4]}M{sel_mon}<br>份额环比</th></tr></thead>"
                f"<tbody>{''.join(table_rows)}</tbody></table>"
            )
            st.markdown(table_html, unsafe_allow_html=True)

    with cR:
        st.markdown("<b class='chart-title'>VDS-Top5 企业市场份额月度趋势 (%)</b>", unsafe_allow_html=True)

        fig2 = go.Figure()
        for b in top5_brands:
            shares = []
            for m in trend_months:
                total = total_vds_sales(df_ind, [m])
                if total == 0:
                    shares.append(np.nan)
                else:
                    shares.append(share_calc(df_ind, [m], b, total))

            show_label = ("汤臣倍健" in b) or ("老百姓" in b)
            mode_str = "lines+markers+text" if show_label else "lines+markers"

            fig2.add_trace(go.Scatter(
                x=[f"{m[2:4]}M{int(m[4:])}" for m in trend_months],
                y=shares, name=b, mode=mode_str,
                marker=dict(color=color_map[b], size=5),
                line=dict(color=color_map[b], width=2, shape="spline", smoothing=1.3),
                text=[f"{v:.1f}" if (show_label and not pd.isna(v)) else "" for v in shares],
                textposition="top center" if "汤臣倍健" in b else "bottom center",
                textfont=dict(size=14, color=color_map[b], family="Arial, sans-serif"),
                showlegend=True
            ))

        fig2.update_layout(
            height=460,
            margin=dict(t=55, b=25, l=40, r=20),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=13, family="Microsoft YaHei, Arial, sans-serif"),
            xaxis=dict(showgrid=False, tickfont=dict(size=13), tickangle=-45),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                        font=dict(size=13), itemsizing="constant",
                        itemwidth=30, tracegroupgap=5),
        )
        st.plotly_chart(fig2, width='stretch')

    st.divider()
    st.caption("数据来源：中康全国零售药店")

# ====================== Part A PAGE 3: 汤臣倍健销售规模及市场份额 ======================
def page3(sel_ym, SEL_MONTHS):
    sl_l = ym_lab(SEL_MONTHS[0])
    sl_r = ym_lab(SEL_MONTHS[-1])
    st.markdown(f"""
    <div class="phdr">
        <h2>全国零售药店 - 汤臣倍健销售规模及市场份额</h2>
    </div>
    """, unsafe_allow_html=True)

    render_conclusion("p3", sel_ym)

    all_records = []
    for m in ind_months:
        vds_total = ind_sales(m, {"品类": "VDS"})
        # 汤臣倍健集团（industry 表 CHC 品类；品牌=汤臣倍健 行数值 = 集团权益=汤臣倍健 的集团总额）
        tang_group_total = ind_sales(m, {"品类": "CHC(营养补充剂)", "品牌": "汤臣倍健"})
        # 汤臣其他品牌：sku/brand 表中 集团权益=汤臣倍健 且 品牌≠汤臣倍健（健力多、Life-Space、天然博士等）
        tang_other = sku_sales(m, {"集团权益": "汤臣倍健"}) - sku_sales(m, {"集团权益": "汤臣倍健", "品牌": "汤臣倍健"})
        # 汤臣主品牌：industry(CHC 品类, 集团权益=汤臣倍健) - 其他品牌（即汤臣倍健品牌自身）
        tang_main = tang_group_total - tang_other
        share = (tang_group_total / vds_total * 100) if vds_total > 0 else np.nan

        all_records.append({
            "year_month": m,
            "label": ym_lab(m),
            "VDS": vds_total,
            "汤臣倍健集团": tang_group_total,
            "汤臣主品牌": tang_main,
            "汤臣其他品牌": tang_other,
            "市场份额": share,
        })

    df_full = pd.DataFrame(all_records)
    df_data = df_full[df_full["year_month"].isin(SEL_MONTHS)].reset_index(drop=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_data["label"],
        y=df_data["汤臣主品牌"],
        name="汤臣主品牌销售额-百万元",
        marker_color=C_KEY,
        text=[f"{v:.0f}" if v > 0 else "" for v in df_data["汤臣主品牌"]],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=15, color="white", family="Arial, sans-serif"),
    ))

    fig.add_trace(go.Bar(
        x=df_data["label"],
        y=df_data["汤臣其他品牌"],
        name="汤臣其他品牌销售额-百万元",
        marker_color=C_OTHER,
        text=[f"{v:.0f}" if v > 0 else "" for v in df_data["汤臣其他品牌"]],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=15, color="white", family="Arial, sans-serif"),
    ))

    fig.add_trace(go.Scatter(
        x=df_data["label"],
        y=df_data["汤臣倍健集团"],
        mode="text",
        text=[f"<b>{v:.0f}</b>" if v > 0 else "" for v in df_data["汤臣倍健集团"]],
        textposition="top center",
        textfont=dict(size=16, color="#000000", family="Arial, sans-serif"),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df_data["label"],
        y=df_data["市场份额"],
        name="市场份额%（占 total VDS）",
        mode="lines+markers+text",
        marker=dict(color=C_SHARE, size=5),
        line=dict(color=C_SHARE, width=2, shape="spline", smoothing=1.3),
        text=[f"{v:.1f}" if not pd.isna(v) else "" for v in df_data["市场份额"]],
        textposition="top center",
        textfont=dict(size=15, color=C_SHARE, family="Arial, sans-serif"),
        yaxis="y2"
    ))

    years = sorted(df_data["year_month"].str[:4].unique())
    shapes = []
    for year in years:
        year_mask = df_data["year_month"].str[:4] == year
        year_indices = df_data[year_mask].index.tolist()
        if len(year_indices) == 0:
            continue
        first_idx = year_indices[0]
        last_idx = year_indices[-1]
        mid_idx = (first_idx + last_idx) / 2

        shapes.append(dict(
            type="rect",
            xref="x",
            yref="paper",
            x0=first_idx - 0.5,
            x1=last_idx + 0.5,
            y0=1.10,
            y1=1.18,
            fillcolor="#f0f0f0",
            line=dict(color="#ddd", width=1),
            layer="above"
        ))

        fig.add_annotation(
            x=mid_idx,
            y=1.14,
            xref="x",
            yref="paper",
            text=f"{year}年",
            showarrow=False,
            font=dict(size=13, color="#555"),
            align="center",
            valign="middle",
            yanchor="middle"
        )

    bar_max = df_data["汤臣倍健集团"].max()
    share_max = df_data["市场份额"].max()
    y1_max = bar_max * 1.5 if not pd.isna(bar_max) and bar_max > 0 else None
    y2_max = share_max * 1.1 if not pd.isna(share_max) and share_max > 0 else None

    fig.update_layout(
        height=520,
        barmode="stack",
        bargap=0.15,
        margin=dict(t=130, b=30, l=0, r=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(size=15, family="Microsoft YaHei, sans-serif"),
        xaxis=dict(showgrid=False, tickfont=dict(size=13), dtick=1, tickangle=0, domain=[0.08, 1.0], automargin=False, range=[-0.5, len(df_data) - 0.5]),
        yaxis=dict(
            title="",
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, y1_max] if y1_max else None,
            automargin=False,
        ),
        yaxis2=dict(
            title="",
            overlaying="y",
            side="left",
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, y2_max] if y2_max else None,
            automargin=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0.98,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="rgba(0,0,0,0)",
            borderwidth=0,
            traceorder="reversed"
        ),
        shapes=shapes,
    )

    st.markdown(f"""
    <div style="text-align:center; font-size:15px; font-weight:600; color:{C_TXT}; margin:10px 0 6px 0; font-family:Microsoft YaHei, sans-serif;">
    全国零售药店 - 汤臣倍健销售规模及市场份额
    </div>
    """, unsafe_allow_html=True)

    # Chart full width - bars span edge to edge
    st.plotly_chart(fig, use_container_width=True)

    # Build merged table (label column + data columns as one continuous table)
    row_labels = ["VDS品类", "汤臣倍健集团", "汤臣主品牌"]
    row_keys = ["VDS", "汤臣倍健集团", "汤臣主品牌"]
    table_rows = []
    for row_name, key in zip(row_labels, row_keys):
        cells = [f"<td style='font-weight:600;text-align:left;padding-left:8px'>{row_name}</td>"]
        for m in SEL_MONTHS:
            v = calc_yoy_p3(df_full, m, key)
            if pd.isna(v):
                cells.append("<td style='text-align:center'>-</td>")
            else:
                color = "#FF0000" if v < 0 else ("#00B050" if v > 10 else C_TXT)
                cells.append(f"<td style='color:{color};text-align:center'>{v:+.0f}%</td>")
        table_rows.append("<tr>" + "".join(cells) + "</tr>")

    _n_p3 = len(SEL_MONTHS)
    _label_w = 8  # Must match xaxis domain left value (0.08)
    _data_w = round((100 - _label_w) / _n_p3, 2) if _n_p3 > 0 else 0
    header_cells = [f"<th style='text-align:center;padding:6px 4px'>{ym_lab(m)}</th>" for m in SEL_MONTHS]
    _p3_cols = f"<colgroup><col style='width:{_label_w}%'>" + "".join(f"<col style='width:{_data_w}%'>" for _ in range(_n_p3)) + "</colgroup>"
    table_html = (
        f"<table class='dt-p3' style='width:100%'>{_p3_cols}"
        f"<thead><tr><th style='text-align:left;padding-left:8px'>销售同比增速</th>{''.join(header_cells)}</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    st.divider()
    st.caption("数据来源：中康全国零售药店")
    st.caption("注：汤臣主品牌包含汤臣倍健+健安适+健视佳+维满B+维满C，不含健力多及益倍适。")

# ====================== Part A PAGE 4: 市场份额分析表 ======================
def page4(selected_month):
    st.markdown(f"""
    <div class="phdr">
        <h2>全国零售药店 - 汤臣倍健市场份额分析</h2>
    </div>
    """, unsafe_allow_html=True)
    render_conclusion("p4", selected_month)

    CUR_YEAR = int(selected_month[:4])
    CUR_MONTH = int(selected_month[4:])

    YTD_MONTHS = get_months(CUR_YEAR, CUR_MONTH, CUR_MONTH)
    CUR_MONTH_STR = f"{CUR_YEAR}{str(CUR_MONTH).zfill(2)}"
    PRE_MONTH_STR = get_months(CUR_YEAR, CUR_MONTH, 2)[0]

    YTD_LY_MONTHS = get_months(CUR_YEAR - 1, CUR_MONTH, CUR_MONTH)
    CUR_LY_MONTH_STR = f"{CUR_YEAR - 1}{str(CUR_MONTH).zfill(2)}"

    yy = str(CUR_YEAR)[2:]
    lyy = str(CUR_YEAR - 1)[2:]

    # Quarter-end: L3M = previous completed quarter, not trailing 3 months
    q_end = CUR_MONTH in (3, 6, 9, 12)
    if q_end:
        if CUR_MONTH == 3:
            l3m_label = f"{lyy}Q4"
            L3M_MONTHS = [f"{CUR_YEAR-1}10", f"{CUR_YEAR-1}11", f"{CUR_YEAR-1}12"]
            L3M_LY_MONTHS = [f"{CUR_YEAR-2}10", f"{CUR_YEAR-2}11", f"{CUR_YEAR-2}12"]
        elif CUR_MONTH == 6:
            l3m_label = f"{yy}Q1"
            L3M_MONTHS = [f"{CUR_YEAR}01", f"{CUR_YEAR}02", f"{CUR_YEAR}03"]
            L3M_LY_MONTHS = [f"{CUR_YEAR-1}01", f"{CUR_YEAR-1}02", f"{CUR_YEAR-1}03"]
        elif CUR_MONTH == 9:
            l3m_label = f"{yy}Q2"
            L3M_MONTHS = [f"{CUR_YEAR}04", f"{CUR_YEAR}05", f"{CUR_YEAR}06"]
            L3M_LY_MONTHS = [f"{CUR_YEAR-1}04", f"{CUR_YEAR-1}05", f"{CUR_YEAR-1}06"]
        elif CUR_MONTH == 12:
            l3m_label = f"{yy}Q3"
            L3M_MONTHS = [f"{CUR_YEAR}07", f"{CUR_YEAR}08", f"{CUR_YEAR}09"]
            L3M_LY_MONTHS = [f"{CUR_YEAR-1}07", f"{CUR_YEAR-1}08", f"{CUR_YEAR-1}09"]
    else:
        l3m_label = "L3M"
        L3M_MONTHS = get_months(CUR_YEAR, CUR_MONTH, 3)
        L3M_LY_MONTHS = get_months(CUR_YEAR - 1, CUR_MONTH, 3)

    # YTD label: H1 at M6, H2 at M12, Q1 at M3, etc.
    if CUR_MONTH == 3:
        ytd_label = f"{yy}Q1"
    elif CUR_MONTH == 6:
        ytd_label = f"{yy}H1"
    elif CUR_MONTH == 9:
        ytd_label = f"{yy}Q1-Q3"
    elif CUR_MONTH == 12:
        ytd_label = f"{yy}H2"
    else:
        ytd_label = "YTD"

    # LY YTD label
    if CUR_MONTH == 3:
        ytd_ly_label = f"{lyy}Q1"
    elif CUR_MONTH == 6:
        ytd_ly_label = f"{lyy}H1"
    elif CUR_MONTH == 9:
        ytd_ly_label = f"{lyy}Q1-Q3"
    elif CUR_MONTH == 12:
        ytd_ly_label = f"{lyy}H2"
    else:
        ytd_ly_label = "LY"


    ROWS = [
        {
            "name": "VDS+OTC", "sub": "",
            "cat_source": "industry", "cat_filter": {"品类": "CHC(营养补充剂)"},
            "brand_source": "industry", "brand_filter": {"品类": "CHC(营养补充剂)", "品牌": "汤臣倍健"},
            "brand_display": "汤臣倍健集团", "has_bar": False,
        },
        {
            "name": "VDS", "sub": "",
            "cat_source": "industry", "cat_filter": {"品类": "VDS"},
            "brand_source": "industry", "brand_filter": {"品类": "CHC(营养补充剂)", "品牌": "汤臣倍健"},
            "brand_display": "汤臣倍健集团", "has_bar": False,
        },
        {"name": "蛋白粉", "sub": "不含OTC", "cat_source": "sku", "cat_filter": {"品类": "蛋白粉"}, "brand_source": "sku", "brand_filter": {"品类": "蛋白粉", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "成人钙", "sub": "含OTC", "cat_source": "sku", "cat_filter": {"品类": "钙-成人"}, "brand_source": "sku", "brand_filter": {"品类": "钙-成人", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "儿童钙", "sub": "含OTC", "cat_source": "sku", "cat_filter": {"品类": "钙-儿童"}, "brand_source": "sku", "brand_filter": {"品类": "钙-儿童", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "成人多维", "sub": "含OTC", "cat_source": "sku", "cat_filter": {"品类": "多维-成人"}, "brand_source": "sku", "brand_filter": {"品类": "多维-成人", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "儿童多维", "sub": "含OTC", "cat_source": "sku", "cat_filter": {"品类": "多维-儿童"}, "brand_source": "sku", "brand_filter": {"品类": "多维-儿童", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "维B", "sub": "含OTC", "cat_source": "brand", "cat_filter": {"品类": "维生素B"}, "brand_source": "brand", "brand_filter": {"品类": "维生素B", "品牌": ["汤臣倍健", "维满B"]}, "brand_display": "汤臣倍健(含维满)", "has_bar": True, "semi_annual": True},
        {"name": "维C", "sub": "含OTC", "cat_source": "brand", "cat_filter": {"品类": "维生素C"}, "brand_source": "brand", "brand_filter": {"品类": "维生素C", "品牌": ["汤臣倍健", "维满C"]}, "brand_display": "汤臣倍健(含维满)", "has_bar": True, "semi_annual": True},
        {"name": "鱼油", "sub": "不含OTC", "cat_source": "sku", "cat_filter": {"品类": "鱼油"}, "brand_source": "sku", "brand_filter": {"品类": "鱼油", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "褪黑素", "sub": "含OTC", "cat_source": "brand", "cat_filter": {"品类": "褪黑素"}, "brand_source": "brand", "brand_filter": {"品类": "褪黑素", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True, "semi_annual": True},
        {"name": "氨糖", "sub": "含OTC", "cat_source": "sku", "cat_filter": {"品类": "关节护理"}, "brand_source": "sku", "brand_filter": {"品类": "关节护理", "品牌": "健力多"}, "brand_display": "健力多", "has_bar": True},
        {"name": "益生菌", "sub": "含OTC", "cat_source": "sku", "cat_filter": {"品类": "益生菌"}, "brand_source": "sku", "brand_filter": {"品类": "益生菌", "品牌": "Life-Space"}, "brand_display": "Life-Space", "has_bar": True},
    ]

    # Semi-annual categories only show at half-year boundaries (June or December)
    is_half_year = CUR_MONTH in (6, 12)
    ROWS = [r for r in ROWS if not r.get('semi_annual', False) or is_half_year]

    table_data = []
    for r in ROWS:
        is_semi = r.get("semi_annual", False)
        cat_ytd = sales_by_source(r["cat_source"], YTD_MONTHS, r["cat_filter"])
        cat_ytd_ly = sales_by_source(r["cat_source"], YTD_LY_MONTHS, r["cat_filter"])
        if is_semi:
            cat_l3m = np.nan
            cat_m4 = np.nan
            cat_m3 = np.nan
            cat_l3m_ly = np.nan
            cat_m4_ly = np.nan
        else:
            cat_l3m = sales_by_source(r["cat_source"], L3M_MONTHS, r["cat_filter"])
            cat_m4 = sales_by_source(r["cat_source"], [CUR_MONTH_STR], r["cat_filter"])
            cat_m3 = sales_by_source(r["cat_source"], [PRE_MONTH_STR], r["cat_filter"])
            cat_l3m_ly = sales_by_source(r["cat_source"], L3M_LY_MONTHS, r["cat_filter"])
            cat_m4_ly = sales_by_source(r["cat_source"], [CUR_LY_MONTH_STR], r["cat_filter"])

        brand_ytd = sales_by_source(r["brand_source"], YTD_MONTHS, r["brand_filter"])
        brand_ytd_ly = sales_by_source(r["brand_source"], YTD_LY_MONTHS, r["brand_filter"])
        if is_semi:
            brand_l3m = np.nan
            brand_m4 = np.nan
            brand_m3 = np.nan
            brand_l3m_ly = np.nan
            brand_m4_ly = np.nan
        else:
            brand_l3m = sales_by_source(r["brand_source"], L3M_MONTHS, r["brand_filter"])
            brand_m4 = sales_by_source(r["brand_source"], [CUR_MONTH_STR], r["brand_filter"])
            brand_m3 = sales_by_source(r["brand_source"], [PRE_MONTH_STR], r["brand_filter"])
            brand_l3m_ly = sales_by_source(r["brand_source"], L3M_LY_MONTHS, r["brand_filter"])
            brand_m4_ly = sales_by_source(r["brand_source"], [CUR_LY_MONTH_STR], r["brand_filter"])

        share_ytd = (brand_ytd / cat_ytd * 100) if cat_ytd > 0 else np.nan
        share_l3m = (brand_l3m / cat_l3m * 100) if cat_l3m > 0 else np.nan
        share_m4 = (brand_m4 / cat_m4 * 100) if cat_m4 > 0 else np.nan
        share_m3 = (brand_m3 / cat_m3 * 100) if cat_m3 > 0 else np.nan

        share_ytd_ly = (brand_ytd_ly / cat_ytd_ly * 100) if cat_ytd_ly > 0 else np.nan
        share_l3m_ly = (brand_l3m_ly / cat_l3m_ly * 100) if cat_l3m_ly > 0 else np.nan
        share_m4_ly = (brand_m4_ly / cat_m4_ly * 100) if cat_m4_ly > 0 else np.nan

        table_data.append({
            "name": r["name"], "sub": r["sub"], "brand_display": r["brand_display"], "has_bar": r["has_bar"],
            "cat_ytd": cat_ytd, "cat_l3m": cat_l3m, "cat_m4": cat_m4, "cat_m3": cat_m3,
            "cat_ytd_yoy": growth_rate(cat_ytd, cat_ytd_ly),
            "cat_l3m_yoy": growth_rate(cat_l3m, cat_l3m_ly),
            "cat_m4_yoy": growth_rate(cat_m4, cat_m4_ly),
            "cat_m4_mom": growth_rate(cat_m4, cat_m3),
            "brand_ytd": brand_ytd, "brand_l3m": brand_l3m, "brand_m4": brand_m4, "brand_m3": brand_m3,
            "brand_ytd_yoy": growth_rate(brand_ytd, brand_ytd_ly),
            "brand_l3m_yoy": growth_rate(brand_l3m, brand_l3m_ly),
            "brand_m4_yoy": growth_rate(brand_m4, brand_m4_ly),
            "brand_m4_mom": growth_rate(brand_m4, brand_m3),
            "share_ytd": share_ytd, "share_l3m": share_l3m, "share_m4": share_m4, "share_m3": share_m3,
            "share_ytd_yoy": share_ytd - share_ytd_ly if not pd.isna(share_ytd) and not pd.isna(share_ytd_ly) else np.nan,
            "share_l3m_yoy": share_l3m - share_l3m_ly if not pd.isna(share_l3m) and not pd.isna(share_l3m_ly) else np.nan,
            "share_m4_yoy": share_m4 - share_m4_ly if not pd.isna(share_m4) and not pd.isna(share_m4_ly) else np.nan,
            "share_m4_mom": share_m4 - share_m3 if not pd.isna(share_m4) and not pd.isna(share_m3) else np.nan,
        })

    df_table = pd.DataFrame(table_data)

    bar_rows = df_table[df_table["has_bar"]]
    max_cat_ytd = bar_rows["cat_ytd"].max() if len(bar_rows) > 0 else 1
    max_brand_ytd = bar_rows["brand_ytd"].max() if len(bar_rows) > 0 else 1

    header_html = f"""
    <table class="dashboard-table">
      <thead>
        <tr class="top-header">
          <th rowspan="2" class="cat-header">品类</th>
          <th class="sales-header-a">销售额<br><span style="font-size:11px;font-weight:normal;">百万元</span></th>
          <th colspan="4" class="growth-header-a">销售额增速</th>
          <th rowspan="2" class="brand-header">汤臣品牌</th>
          <th class="sales-header-b">销售额<br><span style="font-size:11px;font-weight:normal;">百万元</span></th>
          <th colspan="4" class="growth-header-b">销售额增速</th>
          <th colspan="7" class="share-header">汤臣倍健市场份额 (%)</th>
        </tr>
        <tr class="sub-header">
          <th class="sales-header-a">{ytd_label}</th>
          <th class="growth-header-a">{ytd_label}<br>同比</th>
          <th class="growth-header-a">{l3m_label}<br>同比</th>
          <th class="growth-header-a">{yy}M{CUR_MONTH}<br>同比</th>
          <th class="growth-header-a">{yy}M{CUR_MONTH}<br>环比</th>
          <th class="sales-header-b">{ytd_label}</th>
          <th class="growth-header-b">{ytd_label}<br>同比</th>
          <th class="growth-header-b">{l3m_label}<br>同比</th>
          <th class="growth-header-b">{yy}M{CUR_MONTH}<br>同比</th>
          <th class="growth-header-b">{yy}M{CUR_MONTH}<br>环比</th>
          <th class="share-header">{ytd_label}</th>
          <th class="share-header">同比</th>
          <th class="share-header">{l3m_label}</th>
          <th class="share-header">同比</th>
          <th class="share-header">{yy}M{CUR_MONTH}</th>
          <th class="share-header">同比</th>
          <th class="share-header">环比</th>
        </tr>
      </thead>
      <tbody>
    """

    def td_bar_sales(v, max_v, start_color, end_color, bold=True):
        if pd.isna(v):
            return '<td class="num">-</td>'
        width = min(100, max(0, v / max_v * 100)) if max_v > 0 else 0
        cls = " sales-bold" if bold else ""
        return f'''<td class="num bar-cell{cls}">
            <div class="bar-bg" style="width:{width:.1f}%; background: linear-gradient(90deg, {start_color}, {end_color});"></div>
            <span class="bar-text">{format_sales(v)}</span>
        </td>'''

    def td_growth(v):
        color = growth_color(v)
        return f'<td class="num" style="color:{color}">{format_pct(v)}</td>'

    def td_share(v):
        return f'<td class="num">{format_share(v)}</td>'

    def td_share_change(v):
        if pd.isna(v):
            return '<td class="num share-change">-</td>'
        c_color, f_color = share_change_color(v)
        s = f"{v:+.1f}"
        return f'<td class="num share-change" style="color:{f_color}">{circle_svg(c_color)}<span>{s}</span></td>'

    def td_sales_plain(v):
        if pd.isna(v):
            return '<td class="num sales-bold">-</td>'
        return f'<td class="num sales-bold">{format_sales(v)}</td>'

    def build_row(row):
        _sub_cls = "sub-no-otc" if "不含" in row["sub"] else "sub-yes-otc"
        _sub_text = f'({row["sub"]})' if row["sub"] else ""
        name_cell = f'<td class="cat-name">{row["name"]} <span class="{_sub_cls}">{_sub_text}</span></td>'
        cat_sales = td_bar_sales(row["cat_ytd"], max_cat_ytd, BAR_A_START, BAR_A_END) if row["has_bar"] else td_sales_plain(row["cat_ytd"])
        cat_growth = "".join([
            td_growth(row["cat_ytd_yoy"]),
            td_growth(row["cat_l3m_yoy"]),
            td_growth(row["cat_m4_yoy"]),
            td_growth(row["cat_m4_mom"]),
        ])
        _bd = row["brand_display"]
        if "(" in _bd:
            _bd_main, _bd_suffix = _bd.split("(", 1)
            brand_cell = f'<td class="brand-name">{_bd_main}<span class="brand-sub">({_bd_suffix}</span></td>'
        else:
            brand_cell = f'<td class="brand-name">{_bd}</td>'
        brand_sales = td_bar_sales(row["brand_ytd"], max_brand_ytd, BAR_B_START, BAR_B_END) if row["has_bar"] else td_sales_plain(row["brand_ytd"])
        brand_growth = "".join([
            td_growth(row["brand_ytd_yoy"]),
            td_growth(row["brand_l3m_yoy"]),
            td_growth(row["brand_m4_yoy"]),
            td_growth(row["brand_m4_mom"]),
        ])
        share = "".join([
            td_share(row["share_ytd"]),
            td_share_change(row["share_ytd_yoy"]),
            td_share(row["share_l3m"]),
            td_share_change(row["share_l3m_yoy"]),
            td_share(row["share_m4"]),
            td_share_change(row["share_m4_yoy"]),
            td_share_change(row["share_m4_mom"]),
        ])
        return f"<tr>{name_cell}{cat_sales}{cat_growth}{brand_cell}{brand_sales}{brand_growth}{share}</tr>"

    rows_html = "".join([build_row(row) for _, row in df_table.iterrows()])

    footer_note = f"""
      </tbody>
    </table>
    <div class="footer-note">
      <div class="footer-left">
        <p>数据来源：中康全国零售药店</p>
        <p>*注：VDS+OTC包含蓝帽子产品、健康食品及相关OTC产品（不含纯治疗作用的OTC药品如感冒、止咳等）；单维、褪黑素仅半年度频次数据。</p>
      </div>
      <div class="footer-right">
        <p>市场份额变化：<span class="legend-circle green"></span> <span class="legend-text green">≥0 pts</span> <span class="legend-circle yellow"></span> <span class="legend-text red">-0.5~0 pts</span> <span class="legend-circle red"></span> <span class="legend-text red">≤-0.5 pts</span></p>
      </div>
    </div>
    """

    st.markdown(f'<div class="table-wrapper"><div class="table-footer-wrapper">{header_html}{rows_html}{footer_note}</div></div>', unsafe_allow_html=True)
    st.markdown("<div style='height:120px'></div>", unsafe_allow_html=True)

# ========================================================================
# PART B: 重点品类汤臣市场表现 (来自 merged_dashboard)
# ========================================================================

# ====================== Part B Configs: FP_CATEGORY_CONFIG, FP_COLORS ======================
FP_CATEGORY_CONFIG = {
    "蛋白粉": {"cat": "蛋白粉", "brand": "汤臣倍健", "has_otc": False, "brand_label": "汤臣倍健"},
    "成人钙": {"cat": "钙-成人", "brand": "汤臣倍健", "has_otc": True, "brand_label": "汤臣倍健"},
    "儿童钙": {"cat": "钙-儿童", "brand": "汤臣倍健", "has_otc": True, "brand_label": "汤臣倍健"},
    "成人多维": {"cat": "多维-成人", "brand": "汤臣倍健", "has_otc": True, "brand_label": "汤臣倍健"},
    "儿童多维": {"cat": "多维-儿童", "brand": "汤臣倍健", "has_otc": True, "brand_label": "汤臣倍健"},
    "鱼油": {"cat": "鱼油", "brand": "汤臣倍健", "has_otc": False, "brand_label": "汤臣倍健"},
    "氨糖": {"cat": "关节护理", "brand": "健力多", "has_otc": True, "brand_label": "健力多"},
    "益生菌": {"cat": "益生菌", "brand": "Life-Space", "has_otc": True, "brand_label": "Life-Space"},
}

FP_COLORS = {
    "otc": "#F5A623",
    "vds": "#D35400",
    "cat": "#F5A623",
    "brand": "#1B4F8E",
    "brand_line": "#1B4F8E",
}

# ====================== Part B first_page 函数 (fp_*) ======================
def fp_get_ytd_months(year, month):
    return [f"{year}{str(m).zfill(2)}" for m in range(1, month + 1)]


def fp_get_ly_month(month):
    y = int(month[:4])
    m = int(month[4:])
    return f"{y - 1}{str(m).zfill(2)}"


def fp_growth_color(v):
    if pd.isna(v):
        return "#333"
    if v < 0:
        return "#E53935"
    if v > 0:
        return "#00B050"
    return "#1A1A2E"


def fp_fmt_pct(v):
    """智能百分比：>=1% 不保留小数，<1% 保留 1-3 位小数"""
    if pd.isna(v):
        return "-"
    if v == 0:
        return "0%"
    if abs(v) >= 1:
        return f"{v:+.0f}%"
    for n in [1, 2, 3]:
        s = f"{v:+.{n}f}%"
        if abs(float(s.rstrip("%"))) >= 0.001:
            return s
    return f"{v:+.3f}%"


def fp_calc_agg(df, months, filters):
    mask = df["year_month"].isin(months)
    for k, v in filters.items():
        if k == "处方性质":
            if v == "OTC":
                mask = mask & (df[k] == "OTC")
            else:
                mask = mask & (df[k] != "OTC")
        else:
            mask = mask & (df[k] == v)
    sub = df[mask]
    sales = sub["sales_m"].sum()
    qty = sub["qty_h"].sum()
    price = (sub[SALES_COL].sum() / sub[QTY_COL].sum() * 10) if qty > 0 else np.nan
    return {"sales": sales, "qty": qty, "price": price}


def fp_calc_yoy(curr, ly):
    if pd.isna(curr) or pd.isna(ly) or ly == 0:
        return np.nan
    return (curr / ly - 1) * 100


def fp_build_monthly_data(months, cat, brand, has_otc):
    records = []
    for m in months:
        row = {"month": m, "label": ym_lab(m)}
        row["cat"] = fp_calc_agg(sku_df, [m], {"品类": cat})["sales"]
        if has_otc:
            row["otc"] = fp_calc_agg(sku_df, [m], {"品类": cat, "处方性质": "OTC"})["sales"]
            row["vds"] = fp_calc_agg(sku_df, [m], {"品类": cat, "处方性质": "VDS"})["sales"]
        row["brand"] = fp_calc_agg(sku_df, [m], {"品类": cat, "品牌": brand})["sales"]
        y = int(m[:4])
        mon = int(m[4:])
        ly_m = f"{y-1}{str(mon).zfill(2)}"
        row["cat_ly"] = fp_calc_agg(sku_df, [ly_m], {"品类": cat})["sales"]
        if has_otc:
            row["otc_ly"] = fp_calc_agg(sku_df, [ly_m], {"品类": cat, "处方性质": "OTC"})["sales"]
            row["vds_ly"] = fp_calc_agg(sku_df, [ly_m], {"品类": cat, "处方性质": "VDS"})["sales"]
        row["brand_ly"] = fp_calc_agg(sku_df, [ly_m], {"品类": cat, "品牌": brand})["sales"]
        records.append(row)
    return pd.DataFrame(records)


def fp_build_metric_row(label, header_class, filters, curr_m, ly_m, ytd_ms, ytd_ly_ms):
    curr = fp_calc_agg(sku_df, [curr_m], filters)
    ly = fp_calc_agg(sku_df, [ly_m], filters)
    ytd = fp_calc_agg(sku_df, ytd_ms, filters)
    ytd_ly = fp_calc_agg(sku_df, ytd_ly_ms, filters)
    return {
        "label": label,
        "header_class": header_class,
        "curr_sales": curr["sales"],
        "ytd_sales": ytd["sales"],
        "curr_sales_yoy": fp_calc_yoy(curr["sales"], ly["sales"]),
        "ytd_sales_yoy": fp_calc_yoy(ytd["sales"], ytd_ly["sales"]),
        "curr_qty_yoy": fp_calc_yoy(curr["qty"], ly["qty"]),
        "ytd_qty_yoy": fp_calc_yoy(ytd["qty"], ytd_ly["qty"]),
        "curr_price_yoy": fp_calc_yoy(curr["price"], ly["price"]),
        "ytd_price_yoy": fp_calc_yoy(ytd["price"], ytd_ly["price"]),
    }


# ====================== Part B render_first_page() ======================
def render_first_page(selected_cat, selected_month, display_months):
    config = FP_CATEGORY_CONFIG[selected_cat]
    has_otc = config["has_otc"]

    CUR_YEAR = int(selected_month[:4])
    CUR_MONTH = int(selected_month[4:])
    CUR_M_STR = selected_month
    ytd_label, ly_label, l3m_label, yy, lyy = period_labels(selected_month)
    LY_M_STR = fp_get_ly_month(selected_month)
    YTD_MONTHS = fp_get_ytd_months(CUR_YEAR, CUR_MONTH)
    YTD_LY_MONTHS = fp_get_ytd_months(CUR_YEAR - 1, CUR_MONTH)

    render_conclusion(f"fp_{selected_cat}", selected_month)

    metric_rows = []
    metric_rows.append(fp_build_metric_row(selected_cat, "cat-h", {"品类": config["cat"]}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))
    if has_otc:
        metric_rows.append(fp_build_metric_row(f"{selected_cat}OTC", "otc-h", {"品类": config["cat"], "处方性质": "OTC"}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))
        metric_rows.append(fp_build_metric_row(f"{selected_cat}VDS", "vds-h", {"品类": config["cat"], "处方性质": "VDS"}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))
    metric_rows.append(fp_build_metric_row(config["brand_label"], "brand-h", {"品类": config["cat"], "品牌": config["brand"]}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))

    monthly_df = fp_build_monthly_data(display_months, config["cat"], config["brand"], has_otc)

    # YTD OTC/VDS 销售额占比及占比同比（pts）
    otc_vds_box = ""
    if has_otc:
        _ytd_otc = fp_calc_agg(sku_df, YTD_MONTHS, {"品类": config["cat"], "处方性质": "OTC"})["sales"]
        _ytd_vds = fp_calc_agg(sku_df, YTD_MONTHS, {"品类": config["cat"], "处方性质": "VDS"})["sales"]
        _ly_otc = fp_calc_agg(sku_df, YTD_LY_MONTHS, {"品类": config["cat"], "处方性质": "OTC"})["sales"]
        _ly_vds = fp_calc_agg(sku_df, YTD_LY_MONTHS, {"品类": config["cat"], "处方性质": "VDS"})["sales"]
        _ytd_tot = _ytd_otc + _ytd_vds
        _ly_tot = _ly_otc + _ly_vds
        _otc_share = _ytd_otc / _ytd_tot * 100 if _ytd_tot else 0.0
        _vds_share = 100 - _otc_share
        _otc_share_ly = _ly_otc / _ly_tot * 100 if _ly_tot else 0.0
        _vds_share_ly = 100 - _otc_share_ly
        _d_otc = _otc_share - _otc_share_ly
        _d_vds = _vds_share - _vds_share_ly
        # 注意：otc_vds_box 必须单行拼接——多行缩进的 HTML 会被 Markdown 解析成代码块原样显示
        # 标注默认在色块内居中；占比过小（<13%）的一侧标签连带下方同比值一起移到色块外侧，避免文字溢出
        _otc_small = _otc_share < 13
        _vds_small = _vds_share < 13
        _otc_lbl = f"OTC, {_otc_share:.0f}%"
        _vds_lbl = f"VDS, {_vds_share:.0f}%"
        _otc_d = f"{_d_otc:+.1f}%"
        _vds_d = f"{_d_vds:+.1f}%"
        _otc_c = "#00A85A" if _d_otc >= 0 else "#E53935"
        _vds_c = "#00A85A" if _d_vds >= 0 else "#E53935"
        _seg_font = "font-size:14px;font-weight:700;font-family:Arial,&quot;Microsoft YaHei&quot;,sans-serif"
        if _otc_small:
            _otc_inner = f"<span style='position:absolute;left:{_otc_share:.4f}%;top:0;bottom:0;display:flex;align-items:center;transform:translateX(8px);color:#8FAADC;white-space:nowrap'>{_otc_lbl}</span>"
        else:
            _otc_inner = _otc_lbl
        if _vds_small:
            _vds_inner = f"<span style='position:absolute;left:{_otc_share:.4f}%;top:0;bottom:0;display:flex;align-items:center;transform:translateX(-100%) translateX(-6px);color:#ffffff;white-space:nowrap'>{_vds_lbl}</span>"
        else:
            # VDS 标注右对齐：贴齐整个柱状条最右端
            _vds_inner = f"<span style='margin-left:auto;padding-right:6px;white-space:nowrap'>{_vds_lbl}</span>"
        # 下方同比：默认居中（与标注一致）；占比过小的一侧同比值连带移到外侧
        if _otc_small:
            _otc_d_inner = f"<span style='position:absolute;left:{_otc_share:.4f}%;top:50%;transform:translateX(8px) translateY(-50%);color:{_otc_c};white-space:nowrap'>{_otc_d}</span>"
        else:
            _otc_d_inner = _otc_d
        _vds_d_inner = (f"<span style='position:absolute;left:{_otc_share:.4f}%;top:50%;transform:translateX(-100%) translateX(-6px) translateY(-50%);color:{_vds_c};white-space:nowrap'>{_vds_d}</span>" if _vds_small else f"<span style='display:block;text-align:right;padding-right:6px'>{_vds_d}</span>")
        _otc_bar = f"<div style='width:{_otc_share:.4f}%;background:#8FAADC;display:flex;align-items:center;justify-content:center;color:#fff;white-space:nowrap;{_seg_font}'>{_otc_inner}</div>"
        _vds_bar = f"<div style='width:{_vds_share:.4f}%;background:#BF9000;display:flex;align-items:center;justify-content:center;color:#fff;white-space:nowrap;{_seg_font}'>{_vds_inner}</div>"
        # 同比行行首加"占比+-"标签（不上"同比"文字标签），同比值在其色块宽度内居中
        _otc_d_cell = f"<div style='width:{_otc_share:.4f}%;position:relative;text-align:center;color:{_otc_c};white-space:nowrap'><span style='position:absolute;left:2px;top:50%;transform:translateY(-50%);color:#00A85A'>占比+-</span>{_otc_d_inner}</div>"
        _vds_d_cell = f"<div style='width:{_vds_share:.4f}%;position:relative;text-align:center;color:{_vds_c};white-space:nowrap'>{_vds_d_inner}</div>"
        otc_vds_box = (
            f"<div style='border:1px solid #BFBFBF;border-radius:6px;margin:0 0 10px 0;overflow:hidden;background:#fff'>"
            f"<div style='text-align:center;font-weight:700;font-size:16px;color:#333;padding:8px 0;border-bottom:1px solid #E4E9F0'>{selected_cat}OTC&amp;VDS分布 | 销售额占比</div>"
            f"<div style='display:flex;align-items:stretch'>"
            f"<div style='width:126px;flex:none;background:linear-gradient(180deg,#F5F8FD 0%,#E7EEF9 100%);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:15px;color:#102F57'>{ytd_label}</div>"
            f"<div style='flex:1 1 auto;padding:10px 12px 8px 12px;min-width:0'>"
            f"<div style='position:relative;display:flex;height:44px;border-radius:2px;overflow:visible'>{_otc_bar}{_vds_bar}</div>"
            f"<div style='position:relative;display:flex;align-items:center;margin-top:6px;{_seg_font}'>{_otc_d_cell}{_vds_d_cell}</div>"
            f"</div></div></div>"
        )

    is_kids_ca = (selected_cat == "儿童钙")

    if is_kids_ca:
        right_chart_height = 470
    elif has_otc:
        right_chart_height = 450
    else:
        right_chart_height = 470
    # 左列（OTC/VDS盒子 + 指标表）与右列（图表 + 间距 + 月度同比明细表）整体高度对齐
    _otc_box_h = 140 if has_otc else 0
    _growth_rows = 4 if has_otc else 2      # 品类同比 + OTC/VDS(如有) + 品牌同比
    _growth_est = (_growth_rows + 1) * 26   # 含表头，每行约26px
    _streamlit_gap = 18                     # 图表与下方明细表间距
    # 每品类像素级微调：实测后按需增减对应数值（正=加高，负=降低）
    _LEFT_H_TWEAK = {"蛋白粉": 0, "成人钙": 0, "儿童钙": 0, "成人多维": 0, "儿童多维": 0, "鱼油": 0, "氨糖": 0, "益生菌": 0}
    left_content_height = right_chart_height + _streamlit_gap + _growth_est - _otc_box_h + _LEFT_H_TWEAK.get(selected_cat, 0)

    cL, cR = st.columns([0.45, 0.55], gap="medium")
    with cL:
        st.markdown(f"<div class='cat-badge'>{selected_cat}品类 & {config['brand_label']}情况</div>", unsafe_allow_html=True)
        if has_otc:
            st.markdown(otc_vds_box, unsafe_allow_html=True)
        st.markdown("<div id='left-table-wrap'>", unsafe_allow_html=True)
        metric_value_col_count = len(metric_rows) * 2
        colgroup = "<colgroup><col style='width:126px'>" + "".join(["<col>" for _ in range(metric_value_col_count)]) + "</colgroup>"
        top_header = "<tr><th rowspan='2' style='width:126px'>维度</th>"
        for r in metric_rows:
            top_header += f"<th colspan='2' class='{r['header_class']}'>{r['label']}</th>"
        top_header += "</tr>"
        sub_header = "<tr>"
        for _ in metric_rows:
            sub_header += f"<th>{ym_lab(CUR_M_STR)}</th><th>{ytd_label}</th>"
        sub_header += "</tr>"

        def metric_tr(label, curr_key, ytd_key, is_pct=True):
            cells = [f"<td>{label}</td>"]
            for r in metric_rows:
                if is_pct:
                    cells.append(f"<td class='value' style='color:{fp_growth_color(r[curr_key])}'>{fp_fmt_pct(r[curr_key])}</td>")
                    cells.append(f"<td class='value' style='color:{fp_growth_color(r[ytd_key])}'>{fp_fmt_pct(r[ytd_key])}</td>")
                else:
                    cells.append(f"<td class='value'>{fmt_num(r[curr_key])}</td>")
                    cells.append(f"<td class='value'>{fmt_num(r[ytd_key])}</td>")
            return "<tr>" + "".join(cells) + "</tr>"

        table_class = "metric-table" if has_otc else "metric-table compact"
        table_html = (
            f"<table class='{table_class}'>"
            + colgroup + top_header + sub_header
            + metric_tr("规模-百万", "curr_sales", "ytd_sales", is_pct=False)
            + metric_tr("销售额同比", "curr_sales_yoy", "ytd_sales_yoy")
            + metric_tr("销售量同比", "curr_qty_yoy", "ytd_qty_yoy")
            + metric_tr("单价同比", "curr_price_yoy", "ytd_price_yoy")
            + "</table>"
        )
        st.markdown(f"<div class='left-content-wrap' style='height:{left_content_height}px'>{table_html}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with cR:
        st.markdown(f"<div class='cat-badge'>{selected_cat}品类 & {config['brand_label']}销售规模及同比增长率（单位：百万元）</div>", unsafe_allow_html=True)
        fig = go.Figure()
        if has_otc:
            fig.add_trace(go.Bar(
                x=monthly_df["label"], y=monthly_df["otc"], name=f"{selected_cat}OTC",
                marker_color=FP_COLORS["otc"],
                text=[fmt_num(v) for v in monthly_df["otc"]], textposition="inside",
                textfont=dict(size=14, color="white", family="Arial, sans-serif"),
                insidetextanchor="middle",
                textangle=0,
                cliponaxis=False,
                showlegend=True,
            ))
            vds_vals = monthly_df["vds"].fillna(0).values
            otc_vals = monthly_df["otc"].fillna(0).values
            cat_total_for_max = monthly_df["otc"] + monthly_df["vds"]
            bar_max = cat_total_for_max.max() if len(cat_total_for_max) > 0 else 1
            vds_visible = vds_vals.copy()
            fig.add_trace(go.Bar(
                x=monthly_df["label"], y=vds_visible, name=f"{selected_cat}VDS",
                marker_color=FP_COLORS["vds"],
                text=["" for _ in vds_vals], textposition="none",
                insidetextanchor="middle",
                textangle=0,
                cliponaxis=False,
                showlegend=True,
                base=otc_vals,
            ))
            # 儿童钙 VDS 段较薄，标注下移并跨入橙色 OTC 区域，避免数字被上方边界截断
            if is_kids_ca:
                vds_label_y = np.maximum(otc_vals * 0.08, otc_vals - bar_max * 0.018)
            else:
                vds_label_y = otc_vals + vds_vals / 2
            vds_label_text = [fmt_num(v) if v > 0 else "" for v in vds_vals]
            fig.add_trace(go.Scatter(
                x=monthly_df["label"], y=vds_label_y, name=f"{selected_cat}VDS标签",
                mode="text",
                text=vds_label_text,
                textposition="middle center",
                textfont=dict(size=14, color="white", family="Arial, sans-serif"),
                showlegend=False, hoverinfo="skip",
                cliponaxis=False,
            ))
            cat_total = monthly_df["otc"] + monthly_df["vds"]
            fig.add_trace(go.Scatter(
                x=monthly_df["label"], y=cat_total, name="品类总计",
                mode="text",
                text=[fmt_num(v) for v in cat_total],
                textposition="top center",
                textfont=dict(size=14, color="#333", family="Arial, sans-serif"),
                showlegend=False, hoverinfo="skip",
            ))
        else:
            fig.add_trace(go.Bar(
                x=monthly_df["label"], y=monthly_df["cat"], name=selected_cat,
                marker_color=FP_COLORS["cat"],
                text=[fmt_num(v) for v in monthly_df["cat"]], textposition="inside",
                textfont=dict(size=14, color="white", family="Arial, sans-serif"),
                insidetextanchor="middle",
                textangle=0,
                cliponaxis=False,
                showlegend=True,
            ))
            cat_total = monthly_df["cat"]
            bar_max = cat_total.max() if len(cat_total) > 0 else 1

        # 汤臣品牌折线图
        if 'bar_max' not in dir() or bar_max is None:
            bar_max = cat_total.max() if len(cat_total) > 0 else 1
        brand_min = monthly_df["brand"].min() if len(monthly_df) > 0 else 0
        brand_max = monthly_df["brand"].max() if len(monthly_df) > 0 else 1
        # y1: 下方堆叠柱图独立区域；上限留出品类总计标注空间
        y1_top_padding = 1.08 if is_kids_ca else 1.22
        y1_range = [0, bar_max * y1_top_padding] if bar_max > 0 else [0, 1]
        y1_domain_top = 0.76 if is_kids_ca else 0.66
        y2_domain_bottom = 0.86 if is_kids_ca else 0.76
        # y2: 上方品牌折线图独立区域；用动态截断 Y 轴放大波动，不从 0 起画，趋势更明显
        brand_span = brand_max - brand_min
        if brand_span > 0:
            y2_low = max(0, brand_min - brand_span * 0.35)
            y2_high = brand_max + brand_span * 0.55
            if y2_high <= y2_low:
                y2_high = y2_low + 1
            y2_range = [y2_low, y2_high]
        elif brand_max > 0:
            y2_range = [brand_max * 0.85, brand_max * 1.15]
        else:
            y2_range = [0, 1]
        fig.add_trace(go.Scatter(
            x=monthly_df["label"], y=monthly_df["brand"], name=config["brand_label"],
            mode="lines+markers+text",
            marker=dict(color=FP_COLORS["brand_line"], size=6),
            line=dict(color=FP_COLORS["brand_line"], width=2.5, shape="spline", smoothing=1.3),
            text=[fmt_num(v) for v in monthly_df["brand"]],
            textposition="top center",
            textfont=dict(size=14, color=FP_COLORS["brand_line"], family="Arial, sans-serif"),
            yaxis="y2",
            cliponaxis=False,
            showlegend=True, hoverinfo="skip",
        ))
        fig.update_layout(
            barmode="stack",
            bargap=0.34,
            height=right_chart_height,
            margin=dict(t=72, b=55, l=0, r=0),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=13, family="Microsoft YaHei, Arial, sans-serif"),
            xaxis=dict(showgrid=False, tickfont=dict(size=9), tickangle=0, automargin=True, domain=[0.08, 1.0], range=[-0.45, len(monthly_df) - 0.55]),
            uniformtext=dict(minsize=13, mode="show"),
            yaxis=dict(
                showgrid=False, showticklabels=False, zeroline=False,
                range=y1_range, automargin=True,
                domain=[0.00, y1_domain_top],
            ),
            yaxis2=dict(
                anchor="x", side="right",
                showgrid=False, showticklabels=False, zeroline=False,
                range=y2_range,
                automargin=True,
                domain=[y2_domain_bottom, 1.00],
                showline=False, ticks="",
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=12, family="Microsoft YaHei, sans-serif"),
                bgcolor="rgba(255,255,255,0)",
            ),
            showlegend=True,
        )
        for tr in fig.data:
            if tr.showlegend is None:
                tr.showlegend = False
        st.plotly_chart(fig, width='stretch')

        # 下方增长率表
        growth_rows = []
        growth_rows.append({
            "label": "品类同比",
            "values": [fp_calc_yoy(r["cat"], r["cat_ly"]) for _, r in monthly_df.iterrows()]
        })
        if has_otc:
            growth_rows.append({
                "label": "OTC",
                "values": [fp_calc_yoy(r["otc"], r["otc_ly"]) for _, r in monthly_df.iterrows()]
            })
            growth_rows.append({
                "label": "VDS",
                "values": [fp_calc_yoy(r["vds"], r["vds_ly"]) for _, r in monthly_df.iterrows()]
            })
        _bl = config["brand_label"]
        _bl_short = {"汤臣倍健": "汤臣", "健力多": "健力多", "Life-Space": "益倍适"}.get(_bl, _bl)
        growth_rows.append({
            "label": f"{_bl_short}同比",
            "values": [fp_calc_yoy(r["brand"], r["brand_ly"]) for _, r in monthly_df.iterrows()]
        })
        n_months = len(display_months)
        label_w = 8  # percentage for label column (reduced for alignment)
        data_w = round((100 - label_w) / n_months, 2) if n_months > 0 else 0
        _cols = f"<colgroup><col style='width:{label_w}%'>" + "".join(f"<col style='width:{data_w}%'>" for _ in range(n_months)) + "</colgroup>"
        header = "<tr><th style='white-space:nowrap;font-size:12px'>增长率</th>" + "".join([f"<th style='font-size:10px;white-space:nowrap;padding:4px 1px'>{ym_lab(m)}</th>" for m in display_months]) + "</tr>"
        body = ""
        for gr in growth_rows:
            _align = "text-align:right" if gr['label'] in ("OTC", "VDS") else "text-align:left"
            cells = [f"<td style='white-space:nowrap;font-size:11px;padding:4px 2px;{_align}'>{gr['label']}</td>"]
            for v in gr["values"]:
                cells.append(f"<td style='color:{fp_growth_color(v)};white-space:nowrap;font-size:11px;padding:4px 1px;text-align:center'>{fp_fmt_pct(v)}</td>")
            body += "<tr>" + "".join(cells) + "</tr>"

        growth_html = f"<table class='growth-table' style='font-size:12px;table-layout:fixed;width:100%'>{_cols}" + header + body + "</table>"
        st.markdown(growth_html, unsafe_allow_html=True)

    st.caption("*注：VDS+OTC包含蓝帽子产品、健康食品、相关OTC，不含感冒止咳纯药品")


# ====================== Part B BA_CATEGORY_CONFIG, AFFILIATE_BRANDS, BRAND_ALIAS, COLOR_PALETTE ======================
BA_CATEGORY_CONFIG = {
    "蛋白粉": {"cat": "蛋白粉", "focus": ["汤臣倍健", "维诺健"]},
    "成人钙": {"cat": "钙-成人", "focus": ["钙尔奇", "迪巧", "励全", "汤臣倍健"]},
    "儿童钙": {"cat": "钙-儿童", "focus": ["锌钙特", "仁合益康", "汤臣倍健"]},
    "成人多维": {"cat": "多维-成人", "focus": ["善存", "汤臣倍健", "海神药业"]},
    "儿童多维": {"cat": "多维-儿童", "focus": ["草仙药业", "汤臣倍健"]},
    "鱼油": {"cat": "鱼油", "focus": ["汤臣倍健", "维诺健"]},
    "氨糖": {"cat": "关节护理", "focus": ["健力多", "九力", "朗迪"]},
    "益生菌": {"cat": "益生菌", "focus": ["江中", "益君康", "Life-Space"]},
}

AFFILIATE_BRANDS = {"汤臣倍健", "健力多", "Life-Space"}

BRAND_ALIAS = {
    "浙江寰领医药科技有限公司": "寰领医药",
    "草仙药业有限公司": "草仙药业",
    "黑龙江仁合堂药业有限责任公司": "仁合堂药业",
    "绿叶制药集团": "绿叶制药",
}

COLOR_PALETTE = [
    "#4472C4", "#FF6B4A", "#A5A5A5", "#FFC000", "#5B9BD5",
    "#70AD47", "#C55A11", "#7F7F7F", "#9E480E", "#997300",
]

# ====================== Part B brand_analysis 函数 ======================
def brand_name(name):
    return BRAND_ALIAS.get(str(name), str(name))


def brand_filter_values(name):
    values = [str(name)]
    values.extend([raw for raw, alias in BRAND_ALIAS.items() if alias == str(name)])
    return list(dict.fromkeys(values))


def get_month_by_offset(ym, offset):
    target_id = ym_id_map.get(ym, int(ym[:4]) * 12 + int(ym[4:])) + offset
    candidates = sku_df.loc[sku_df["ym_id"] == target_id, "year_month"].unique()
    if len(candidates):
        return sorted(candidates)[0]
    y = (target_id - 1) // 12
    m = target_id - y * 12
    return f"{y}{str(m).zfill(2)}"


def period_months(kind, current_ym):
    y = int(current_ym[:4])
    m = int(current_ym[4:])
    current_id = y * 12 + m
    if kind == "M":
        return [current_ym]
    if kind == "LM":
        return [get_month_by_offset(current_ym, -1)]
    if kind == "LYM":
        return [get_month_by_offset(current_ym, -12)]
    if kind == "YTD":
        return [f"{y}{str(i).zfill(2)}" for i in range(1, m + 1)]
    if kind == "YTD_LY":
        return [f"{y - 1}{str(i).zfill(2)}" for i in range(1, m + 1)]
    if kind == "MAT":
        return sorted(sku_df.loc[sku_df["ym_id"].isin(range(current_id - 11, current_id + 1)), "year_month"].unique())
    if kind == "MAT_LY":
        return sorted(sku_df.loc[sku_df["ym_id"].isin(range(current_id - 23, current_id - 11)), "year_month"].unique())
    if kind == "L3M":
        return sorted(sku_df.loc[sku_df["ym_id"].isin(range(current_id - 2, current_id + 1)), "year_month"].unique())
    return [current_ym]


def safe_div(num, den):
    return np.nan if den is None or pd.isna(den) or den == 0 else num / den


def ba_calc_agg(months, cat=None, brand=None):
    mask = sku_df["year_month"].isin(months)
    if cat is not None:
        mask &= sku_df["品类"].eq(cat)
    if brand is not None:
        mask &= sku_df["品牌"].isin(brand_filter_values(brand))
    sub = sku_df.loc[mask]
    sales = sub["sales_m"].sum()
    qty = sub["qty_h"].sum()
    raw_sales = sub[SALES_COL].sum()
    raw_qty = sub[QTY_COL].sum()
    price = safe_div(raw_sales, raw_qty) * 10 if raw_qty else np.nan
    return {"sales": sales, "qty": qty, "price": price}


def calc_share(months, cat, brand):
    brand_sales = ba_calc_agg(months, cat=cat, brand=brand)["sales"]
    cat_sales = ba_calc_agg(months, cat=cat)["sales"]
    return safe_div(brand_sales, cat_sales) * 100


def growth(curr, base):
    if pd.isna(curr) or pd.isna(base) or base == 0:
        return np.nan
    return (curr / base - 1) * 100


def fmt_share(v):
    if pd.isna(v):
        return "-"
    if abs(v - 100) < 0.0000001:
        return "100"
    if round(abs(v), 1) == 0:
        return f"{v:.2f}"
    return f"{v:.1f}"


def fmt_delta(v):
    if pd.isna(v):
        return "-"
    if abs(v) < 0.05:
        return "0.0"
    return f"{v:.1f}"


def fmt_growth(v):
    if pd.isna(v):
        return "-"
    if v > 999:
        return "999%+"
    rounded = round(v)
    if rounded == 0:
        return "0.0%"
    return f"{rounded:.0f}%"


def cls_growth(v):
    if pd.isna(v):
        return "plain"
    if v < 0:
        return "neg"
    if v > 0:
        return "pos"
    return "plain"


def cls_delta(v):
    if pd.isna(v):
        return "plain"
    return "pos-share" if v >= 0 else "neg-share"


def td(value, css="plain", title=None):
    title_attr = f" title='{title}'" if title else ""
    return f"<td class='{css}'{title_attr}>{value}</td>"


def build_top10(cat, ytd_months):
    cat_df = sku_df[sku_df["year_month"].isin(ytd_months) & sku_df["品类"].eq(cat)]
    return cat_df.groupby("品牌", dropna=False)["sales_m"].sum().sort_values(ascending=False).head(10).index.tolist()


def row_metrics(label, cat, brand, current_ym):
    months_m = period_months("M", current_ym)
    months_lm = period_months("LM", current_ym)
    months_lym = period_months("LYM", current_ym)
    months_ytd = period_months("YTD", current_ym)
    months_ytd_ly = period_months("YTD_LY", current_ym)

    m = ba_calc_agg(months_m, cat=cat, brand=brand)
    lm = ba_calc_agg(months_lm, cat=cat, brand=brand)
    lym = ba_calc_agg(months_lym, cat=cat, brand=brand)
    ytd = ba_calc_agg(months_ytd, cat=cat, brand=brand)
    ytd_ly = ba_calc_agg(months_ytd_ly, cat=cat, brand=brand)

    if brand is None:
        share_m = share_lm = share_lym = share_ytd = share_ytd_ly = 100.0
    else:
        share_m = calc_share(months_m, cat, brand)
        share_lm = calc_share(months_lm, cat, brand)
        share_lym = calc_share(months_lym, cat, brand)
        share_ytd = calc_share(months_ytd, cat, brand)
        share_ytd_ly = calc_share(months_ytd_ly, cat, brand)

    return {
        "label": label,
        "brand": brand,
        "sales_ytd": ytd["sales"],
        "sales_m": m["sales"],
        "sales_yoy": growth(ytd["sales"], ytd_ly["sales"]),
        "qty_yoy": growth(ytd["qty"], ytd_ly["qty"]),
        "price_yoy": growth(ytd["price"], ytd_ly["price"]),
        "m_sales_yoy": growth(m["sales"], lym["sales"]),
        "m_sales_mom": growth(m["sales"], lm["sales"]),
        "share_m": share_m,
        "share_m_yoy_delta": share_m - share_lym if not pd.isna(share_m) and not pd.isna(share_lym) else np.nan,
        "share_m_mom_delta": share_m - share_lm if not pd.isna(share_m) and not pd.isna(share_lm) else np.nan,
        "share_ytd": share_ytd,
        "share_ytd_yoy_delta": share_ytd - share_ytd_ly if not pd.isna(share_ytd) and not pd.isna(share_ytd_ly) else np.nan,
    }


def get_brand_attribute(cat, brand, ytd_months):
    """Get brand attribute (VDS/OTC/mixed) based on 处方性质 distribution."""
    if brand is None:
        return "-"
    mask = sku_df["year_month"].isin(ytd_months) & sku_df["品类"].eq(cat) & sku_df["品牌"].isin(brand_filter_values(brand))
    sub = sku_df.loc[mask]
    otc_sales = sub[sub["处方性质"] == "OTC"]["sales_m"].sum()
    vds_sales = sub[sub["处方性质"] != "OTC"]["sales_m"].sum()
    total = otc_sales + vds_sales
    if total == 0:
        return "-"
    if otc_sales == 0:
        return ("VDS", None)
    if vds_sales == 0:
        return ("OTC", None)
    # Mixed: show the LARGER attribute with its percentage
    otc_pct = otc_sales / total * 100
    vds_pct = vds_sales / total * 100
    if otc_pct >= 99.5:
        return ("OTC", None)
    if vds_pct >= 99.5:
        return ("VDS", None)
    if otc_pct >= vds_pct:
        return ("OTC", otc_pct)
    else:
        return ("VDS", vds_pct)


def build_table_html(cat_label, cat, table_brands, current_ym):
    ytd_label, _, _, _, _ = period_labels(current_ym)
    rows = [row_metrics(cat_label, cat, None, current_ym)]
    rows.extend([row_metrics(brand_name(b), cat, b, current_ym) for b in table_brands])
    html = [
        "<table class='brand-table'>",
        "<tr><th rowspan='2' class='brand-col'>TOP品牌</th><th rowspan='2' class='attr-col'>属性</th><th colspan='1' class='group-head'>销售额<br>百万元</th><th colspan='3' class='group-head'>同比增长率</th><th colspan='2' class='group-head'>销售额增长率</th><th colspan='5' class='group-head'>市场份额(%)</th></tr>",
        f"<tr><th class='sub-head'>{ytd_label}</th><th class='sub-head'>销售额</th><th class='sub-head'>销售量</th><th class='sub-head'>单盒均价</th><th class='sub-head'>{ym_lab(current_ym)}<br>同比</th><th class='sub-head'>{ym_lab(current_ym)}<br>环比</th><th class='sub-head'>{ym_lab(current_ym)}</th><th class='sub-head'>同比</th><th class='sub-head'>环比</th><th class='sub-head'>{ytd_label}</th><th class='sub-head'>同比</th></tr>",
    ]
    ytd_months = period_months("YTD", current_ym)
    for idx, r in enumerate(rows):
        classes = []
        if idx == 0:
            classes.append("cat-row")
        if r["brand"] in AFFILIATE_BRANDS:
            classes.append("affiliate-row")
        if idx > 0 and r["brand"] not in AFFILIATE_BRANDS and (
            (not pd.isna(r["share_ytd_yoy_delta"]) and r["share_ytd_yoy_delta"] >= 0.5)
            or (not pd.isna(r["share_m_yoy_delta"]) and r["share_m_yoy_delta"] >= 0.5)
        ):
            classes.append("share-growth-row")
        html.append(f"<tr class='{' '.join(classes)}'>")
        html.append(td(r["label"], "plain"))
        attr = get_brand_attribute(cat, r["brand"], ytd_months)
        if isinstance(attr, tuple):
            attr_type, attr_pct = attr
            if attr_pct is not None:
                attr_html = f"{attr_type} <span style='color:#E53935;font-size:9px'>{attr_pct:.0f}%</span>"
            else:
                attr_html = attr_type
        else:
            attr_html = str(attr)
        html.append(td(attr_html, "plain"))
        html.append(td(fmt_num(r["sales_ytd"])))
        for key in ["sales_yoy", "qty_yoy", "price_yoy", "m_sales_yoy", "m_sales_mom"]:
            raw = r[key]
            title = f"原始增长率：{raw:.3f}%" if not pd.isna(raw) else None
            html.append(td(fmt_growth(raw), cls_growth(raw), title=title))
        html.append(td(fmt_share(r["share_m"])))
        if idx == 0:
            html.append(td(""))
            html.append(td(""))
            html.append(td(fmt_share(r["share_ytd"])))
            html.append(td(""))
        else:
            html.append(td(fmt_delta(r["share_m_yoy_delta"]), cls_delta(r["share_m_yoy_delta"])))
            html.append(td(fmt_delta(r["share_m_mom_delta"]), cls_delta(r["share_m_mom_delta"])))
            html.append(td(fmt_share(r["share_ytd"])))
            html.append(td(fmt_delta(r["share_ytd_yoy_delta"]), cls_delta(r["share_ytd_yoy_delta"])))
        html.append("</tr>")
    html.append("</table>")
    return "".join(html)


def make_top10_share_chart(cat_label, cat, top_brands, current_ym, chart_height=690):
    ytd_label, ly_label, _, _, _ = period_labels(current_ym)
    ytd_months = period_months("YTD", current_ym)
    ly_months = period_months("YTD_LY", current_ym)
    fig = go.Figure()
    ytd_shares = [calc_share(ytd_months, cat, b) for b in top_brands]
    ly_shares = [calc_share(ly_months, cat, b) for b in top_brands]
    total_ly = np.nansum(ly_shares)
    total_ytd = np.nansum(ytd_shares)

    for i, brand in enumerate(top_brands):
        ly_val = ly_shares[i]
        ytd_val = ytd_shares[i]
        inc = (not pd.isna(ytd_val)) and (not pd.isna(ly_val)) and ytd_val > ly_val
        show_text = True
        fig.add_trace(
            go.Bar(
                x=[ly_label, ytd_label],
                y=[0 if pd.isna(ly_val) else ly_val, 0 if pd.isna(ytd_val) else ytd_val],
                name=brand_name(brand),
                marker=dict(
                    color=COLOR_PALETTE[i % len(COLOR_PALETTE)],
                    line=dict(color=["#FF0000" if inc else "rgba(0,0,0,0)", "#FF0000" if inc else "rgba(0,0,0,0)"], width=[2.0 if inc else 0, 2.0 if inc else 0]),
                ),
                text=[fmt_share(ly_val) if show_text else "", fmt_share(ytd_val) if show_text else ""],
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="white", size=14 if show_text else 9, family="Arial, sans-serif"),
                hovertemplate="%{fullData.name}<br>%{x}份额：%{y:.3f}%<extra></extra>",
                showlegend=False,
            )
        )

    legend_y_positions = np.linspace(0.16, 0.82, max(len(top_brands), 1))
    for i, brand in enumerate(top_brands):
        ly_val = ly_shares[i]
        ytd_val = ytd_shares[i]
        inc = (not pd.isna(ytd_val)) and (not pd.isna(ly_val)) and ytd_val > ly_val
        y_pos = float(legend_y_positions[i])
        fig.add_shape(
            type="rect",
            xref="paper",
            yref="paper",
            x0=1.015,
            x1=1.045,
            y0=y_pos - 0.012,
            y1=y_pos + 0.012,
            fillcolor=COLOR_PALETTE[i % len(COLOR_PALETTE)],
            line=dict(color="#FF0000" if inc else "rgba(0,0,0,0)", width=1.5 if inc else 0),
        )
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=1.055,
            y=y_pos,
            text=brand_name(brand),
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=14, color="#333", family="Microsoft YaHei"),
        )

    fig.add_annotation(x=ly_label, y=total_ly + 1.5, text=f"<b>{fmt_share(total_ly)}</b>", showarrow=False, font=dict(size=20, color="#111", family="Arial, sans-serif"))
    fig.add_annotation(x=ytd_label, y=total_ytd + 1.5, text=f"<b>{fmt_share(total_ytd)}</b>", showarrow=False, font=dict(size=20, color="#111", family="Arial, sans-serif"))
    # Top10 汇总占比同比变化：正绿箭头向上，负红箭头向下
    # 位置：图表右侧（图例上方），与右侧图例列对齐
    _top_delta = total_ytd - total_ly
    if not pd.isna(_top_delta) and abs(_top_delta) >= 0.05:
        _up = _top_delta >= 0
        fig.add_annotation(
            xref="paper", yref="paper",
            x=1.055, y=0.93,
            text=f"<b>{'↑' if _up else '↓'} {_top_delta:+.1f}</b>",
            showarrow=False, xanchor="left", yanchor="middle",
            font=dict(size=18, color="#00A85A" if _up else "#E53935", family="Arial, sans-serif"),
        )
    fig.add_annotation(
        x=0.5, y=1.0,
        xref="x", yref="paper",
        text="<b>Top10品牌市场份额%</b>",
        showarrow=False,
        xanchor="center", yanchor="bottom",
        font=dict(size=18, color="#666", family="Microsoft YaHei"),
    )
    fig.update_layout(
        barmode="stack",
        height=chart_height,
        margin=dict(t=38, b=25, l=20, r=120),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Microsoft YaHei", size=14),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(showgrid=False, showticklabels=False, range=[0, max(total_ly, total_ytd) + 6]),
        showlegend=False,
    )
    return fig


def make_trend_chart(cat_label, cat, brands, months):
    fig = go.Figure()
    _TREND_YMAX = {"蛋白粉": 65, "成人钙": 40, "儿童钙": 40, "成人多维": 45, "儿童多维": 40, "鱼油": 55, "氨糖": 45, "益生菌": 35}
    # Pre-calculate all brand values for overlap detection
    _brand_vals = []
    for brand in brands:
        _bv = [calc_share([m], cat, brand) for m in months]
        _brand_vals.append(_bv)
    _all_vals_flat = [v for bv in _brand_vals for v in bv if not pd.isna(v)]
    _y_max = _TREND_YMAX.get(cat_label, max(_all_vals_flat) * 1.25 if _all_vals_flat else 100)
    _overlap_thresh = _y_max * 0.03  # 3% of y-axis range = "overlapping"

    for i, brand in enumerate(brands):
        vals = _brand_vals[i]
        _bn = brand_name(brand)
        _valid_idx = [j for j, v in enumerate(vals) if not pd.isna(v)]
        if cat_label == "成人钙" and "励全" in _bn and len(_valid_idx) >= 2:
            _text = ["" for _ in vals]
            _text[_valid_idx[0]] = fmt_share(vals[_valid_idx[0]])
            _text[_valid_idx[-1]] = fmt_share(vals[_valid_idx[-1]])
        else:
            _text = [fmt_share(v) if not pd.isna(v) else "" for v in vals]

        # Blank out 25M10 for 九力 in 氨糖 (replaced by custom annotation with higher offset)
        if cat_label == "氨糖" and "九力" in _bn:
            for _j, _m in enumerate(months):
                if ym_lab(_m) == "25M10" and not pd.isna(vals[_j]):
                    _text[_j] = ""
        # Blank out 25M2 for 草仙药业 in 儿童多维 (replaced by custom annotation lower)
        if cat_label == "儿童多维" and "草仙" in _bn:
            for _j, _m in enumerate(months):
                if ym_lab(_m) == "25M2" and not pd.isna(vals[_j]):
                    _text[_j] = ""

        # Build textposition: if lines overlap at a month, higher->top, lower->bottom
        _tp = []
        for j, m in enumerate(months):
            _my_val = vals[j]
            _lbl = ym_lab(m)
            if pd.isna(_my_val):
                _tp.append("top center")
                continue
            # Check for overlap with other brands at this month
            _overlap = False
            _am_higher = True
            for k in range(len(brands)):
                if k == i:
                    continue
                _other_val = _brand_vals[k][j] if j < len(_brand_vals[k]) else None
                if _other_val is None or pd.isna(_other_val):
                    continue
                if abs(_my_val - _other_val) < _overlap_thresh:
                    _overlap = True
                    if _my_val < _other_val:
                        _am_higher = False
                    break
            if _overlap:
                _tp.append("top center" if _am_higher else "bottom center")
            else:
                # No overlap: use existing default rules
                if (cat_label == "氨糖" and "九力" in _bn and _lbl in ["25M10", "25M11", "25M12", "26M2"]):
                    _tp.append("top center")
                elif (cat_label == "儿童多维" and "汤臣倍健" in _bn and _lbl == "25M2"):
                    _tp.append("top center")
                elif (cat_label == "氨糖" and "九力" in _bn):
                    _tp.append("bottom center")
                elif (cat_label == "成人钙" and "汤臣倍健" in _bn):
                    _tp.append("bottom center")
                elif (cat_label == "儿童钙" and "汤臣倍健" in _bn):
                    _tp.append("bottom center")
                elif (cat_label == "儿童多维" and "汤臣倍健" in _bn):
                    _tp.append("bottom center")
                elif (cat_label == "益生菌" and "Life-Space" in _bn):
                    _tp.append("bottom center")
                else:
                    _tp.append("top center")

        fig.add_trace(
            go.Scatter(
                x=[ym_lab(m) for m in months],
                y=vals,
                mode="lines+markers+text",
                name=_bn,
                line=dict(width=3, color=COLOR_PALETTE[i % len(COLOR_PALETTE)], shape="spline", smoothing=1.3),
                marker=dict(size=6),
                text=_text,
                textposition=_tp,
                textfont=dict(size=14, color=COLOR_PALETTE[i % len(COLOR_PALETTE)], family="Arial, sans-serif"),
                hovertemplate="%{fullData.name}<br>%{x}份额：%{y:.3f}%<extra></extra>",
            )
        )
    # Custom annotation: 九力 25M10 label moved ~0.1cm higher (yshift=18)
    if cat_label == "氨糖":
        for i, brand in enumerate(brands):
            _bn = brand_name(brand)
            if "九力" in _bn:
                for j, m in enumerate(months):
                    if ym_lab(m) == "25M10":
                        _val = _brand_vals[i][j]
                        if not pd.isna(_val):
                            fig.add_annotation(
                                x=ym_lab(m), y=_val,
                                text=fmt_share(_val),
                                showarrow=False, yshift=18,
                                font=dict(size=14, color=COLOR_PALETTE[i % len(COLOR_PALETTE)], family="Arial, sans-serif"),
                            )
                        break
                break
    # Custom annotation: 草仙药业 25M2 label moved ~0.8cm lower (yshift=-30)
    if cat_label == "儿童多维":
        for i, brand in enumerate(brands):
            _bn = brand_name(brand)
            if "草仙" in _bn:
                for j, m in enumerate(months):
                    if ym_lab(m) == "25M2":
                        _val = _brand_vals[i][j]
                        if not pd.isna(_val):
                            fig.add_annotation(
                                x=ym_lab(m), y=_val,
                                text=fmt_share(_val),
                                showarrow=False, yshift=-30,
                                font=dict(size=14, color=COLOR_PALETTE[i % len(COLOR_PALETTE)], family="Arial, sans-serif"),
                            )
                        break
                break
    fig.update_layout(
        title=dict(text=f"{cat_label}-重点品牌份额(%)趋势", x=0.5, font=dict(size=16, color="#666")),
        height=315,
        margin=dict(t=46, b=48, l=0, r=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Microsoft YaHei", size=13),
        xaxis=dict(showgrid=False, tickangle=-45, automargin=False),
        yaxis=dict(showgrid=True, gridcolor="#EEF2FA", showticklabels=False, zeroline=False, range=[-5 if cat_label == "儿童钙" else 0, 25 if cat_label == "氨糖" else _y_max]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(range=[-0.5, len(months) - 0.5])
    return fig


# ====================== Part B render_brand_analysis() (WITH 氨糖/益生菌 mod) ======================
def render_brand_analysis(selected_cat, selected_month, display_months):
    config = BA_CATEGORY_CONFIG[selected_cat]
    source_cat = config["cat"]
    ytd_label, ly_label, l3m_label, yy, lyy = period_labels(selected_month)

    render_conclusion(f"ba_{selected_cat}", selected_month)

    ytd_months = period_months("YTD", selected_month)
    top10_brands = build_top10(source_cat, ytd_months)
    table_brands = list(top10_brands)
    if selected_cat in ("氨糖", "益生菌"):
        # 氨糖&益生菌：品牌表格中去掉汤臣倍健
        table_brands = [b for b in table_brands if b != "汤臣倍健"]
    else:
        if "汤臣倍健" not in table_brands and ba_calc_agg(ytd_months, cat=source_cat, brand="汤臣倍健")["sales"] > 0:
            table_brands.append("汤臣倍健")
    # Calculate left chart height to match right side (table + gap + trend chart)
    n_table_rows = len(table_brands) + 3  # +1 category row, +2 header rows
    table_row_h = 30  # brand-table row height - reduced to align with trend chart bottom
    table_height = n_table_rows * table_row_h
    trend_chart_h = 351  # make_trend_chart height
    streamlit_gap_ba = 18  # gap between table and trend chart
    left_chart_height = table_height + streamlit_gap_ba + trend_chart_h

    left_col, right_col = st.columns([0.28, 0.72], gap="medium")
    with left_col:
        st.plotly_chart(make_top10_share_chart(selected_cat, source_cat, top10_brands, selected_month, left_chart_height), width='stretch')
    with right_col:
        st.markdown(build_table_html(selected_cat, source_cat, table_brands, selected_month), unsafe_allow_html=True)
        st.plotly_chart(make_trend_chart(selected_cat, source_cat, config["focus"], display_months), width='stretch')


# ====================== Part B SA_CATEGORY_CONFIG, TITLE_MAP, SA_COLORS, SHARE_YMAX, SHARE_DECIMALS, CHART_NAMES ======================
SA_CATEGORY_CONFIG = {
    "蛋白粉": {
        "cat": "蛋白粉",
        "rows": [
            {"name": "旧品", "source": "brand", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健(蛋白粉)"}},
            {"name": "金装", "source": "brand", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健金装(蛋白粉)"}},
            {"name": "白金", "source": "brand", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健白金(蛋白粉)"}},
            {"name": "E钙",  "source": "brand", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健(钙维生素E蛋白粉)"}},
            {"name": "金装礼盒装300g*2p", "source": "sku", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健金装(蛋白粉)", "产品包装": "300gx2p"}},
            {"name": "白金礼盒装330g*2p", "source": "sku", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健白金(蛋白粉)", "产品包装": "330gx2p"}},
            {"name": "E钙蛋520g",          "source": "sku", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健(钙维生素E蛋白粉)", "产品包装": "520g"}},
            {"name": "金装450g",          "source": "sku", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健金装(蛋白粉)", "产品包装": "450g"}},
            {"name": "白金480g",          "source": "sku", "filters": {"品类": "蛋白粉", "品牌产品": "汤臣倍健白金(蛋白粉)", "产品包装": "480g"}},
            {"name": "汤臣整体",           "source": "sku", "filters": {"品类": "蛋白粉", "品牌": "汤臣倍健"}, "dist_source": "distribution", "dist_filters": {"品牌_NEW": "汤臣倍健蛋白粉"}},
        ],
    },
    "成人钙": {
        "cat": "钙-成人",
        "rows": [
            {"name": "200粒x2",   "source": "sku", "filters": {"品类": "钙-成人", "品牌产品": "汤臣倍健(钙维生素D维生素K软胶囊)", "产品包装": "1gx200sx2p"}},
            {"name": "120粒",     "source": "sku", "filters": {"品类": "钙-成人", "品牌产品": "汤臣倍健(钙维生素D维生素K软胶囊)", "产品包装": "1gx120s"}},
            {"name": "焕动力120粒","source": "sku", "filters": {"品类": "钙-成人", "品牌产品": "焕动力(钙维生素D维生素K软胶囊)", "产品包装": "1gx120s"}},
            {"name": "其他",      "source": "sku", "filters": {"品类": "钙-成人", "品牌": "汤臣倍健"}, "exclude_any": [
                {"品牌产品": "汤臣倍健(钙维生素D维生素K软胶囊)", "产品包装": "1gx200sx2p"},
                {"品牌产品": "汤臣倍健(钙维生素D维生素K软胶囊)", "产品包装": "1gx120s"},
                {"品牌产品": "焕动力(钙维生素D维生素K软胶囊)", "产品包装": "1gx120s"},
            ]},
            {"name": "钙尔奇D600 60片", "source": "sku", "filters": {"品类": "钙-成人", "品牌产品": "钙尔奇D600(碳酸钙D3片(Ⅰ))", "产品包装": "0.6gx60s"}},
            {"name": "汤臣钙DK整体",   "source": "brand", "filters": {"品类": "钙-成人", "品牌产品": "汤臣倍健(钙维生素D维生素K软胶囊)"}},
            {"name": "汤臣钙整体",     "source": "sku", "filters": {"品类": "钙-成人", "品牌": "汤臣倍健"}},
        ],
    },
    "儿童钙": {
        "cat": "钙-儿童",
        "rows": [
            {"name": "牛初乳60片*2", "source": "sku", "filters": {"品类": "钙-儿童", "品牌产品": "汤臣倍健(牛初乳加钙咀嚼片)", "产品包装": "1.2gx60sx2p"}},
            {"name": "液体钙12袋",   "source": "sku", "filters": {"品类": "钙-儿童", "品牌产品": "汤臣倍健(钙锌维生素K口服液)", "产品包装": "15mlx12d"}},
            {"name": "钙铁锌60片",   "source": "sku", "filters": {"品类": "钙-儿童", "品牌产品": "汤臣倍健(钙铁锌咀嚼片)", "产品包装": "1.5gx60s"}},
            {"name": "钙镁90片",     "source": "sku", "filters": {"品类": "钙-儿童", "品牌产品": "汤臣倍健(钙镁咀嚼片)", "产品包装": "1.6gx90s"}},
            {"name": "锌钙特葡萄糖酸钙锌口服液24袋", "source": "sku", "filters": {"品类": "钙-儿童", "品牌产品": "锌钙特(葡萄糖酸钙锌口服溶液)", "产品包装": "10ml:0.73gx24z"}},
            {"name": "汤臣儿童钙整体", "source": "sku", "filters": {"品类": "钙-儿童", "品牌": "汤臣倍健"}},
        ],
    },
    "成人多维": {
        "cat": "多维-成人",
        "rows": [
            {"name": "女维120片", "source": "sku", "filters": {"品类": "多维-成人", "品牌产品": "汤臣倍健(多种维生素矿物质片)", "品名(含属性)": "多种维生素矿物质片|女士型|", "产品包装": "1.5gx60sx2p"}},
            {"name": "女维60片",  "source": "sku", "filters": {"品类": "多维-成人", "品牌产品": "汤臣倍健(多种维生素矿物质片)", "品名(含属性)": "多种维生素矿物质片|女士型|", "产品包装": "1.5gx60s"}},
            {"name": "男维120片", "source": "sku", "filters": {"品类": "多维-成人", "品牌产品": "汤臣倍健(多种维生素矿物质片)", "品名(含属性)": "多种维生素矿物质片|男士型|", "产品包装": "1.5gx60sx2p"}},
            {"name": "男维60片",  "source": "sku", "filters": {"品类": "多维-成人", "品牌产品": "汤臣倍健(多种维生素矿物质片)", "品名(含属性)": "多种维生素矿物质片|男士型|", "产品包装": "1.5gx60s"}},
            {"name": "银善存91sx2p", "source": "sku", "filters": {"品类": "多维-成人", "品牌产品": "银善存(多维元素片(29-Ⅱ))", "产品包装": "91sx2p"}},
            {"name": "善存多维元素片(29)91sx2p", "source": "sku", "filters": {"品类": "多维-成人", "品牌产品": "善存(多维元素片(29))", "产品包装": "91sx2p"}},
            {"name": "汤臣多维整体", "source": "sku", "filters": {"品类": "多维-成人", "品牌": "汤臣倍健"}},
        ],
    },
    "儿童多维": {
        "cat": "多维-儿童",
        "rows": [
            {"name": "儿童多维60s", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "汤臣倍健(多种维生素咀嚼片)", "品名(含属性)": "多种维生素咀嚼片|儿童型|", "产品包装": "1gx60s"}},
            {"name": "青少年多维60s", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "汤臣倍健(多种维生素咀嚼片)", "品名(含属性)": "多种维生素咀嚼片|青少年型|", "产品包装": "1gx60s"}},
            {"name": "汤臣儿童60片", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "汤臣倍健(多种维生素咀嚼片)", "品名(含属性)": "多种维生素咀嚼片|儿童型|", "产品包装": "1gx60s"}},
            {"name": "汤臣青少年60片", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "汤臣倍健(多种维生素咀嚼片)", "品名(含属性)": "多种维生素咀嚼片|青少年型|", "产品包装": "1gx60s"}},
            {"name": "仁合堂五维赖氨酸12袋", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "五维赖氨酸口服溶液(黑龙江仁合堂药业)", "产品包装": "10mlx12z"}},
            {"name": "草仙药业五维赖氨酸片36s", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "五维赖氨酸片(草仙药业)", "产品包装": "36s"}},
            {"name": "小施尔康多维咀嚼片(10)30s", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "小施尔康(小儿多维生素咀嚼片(10))", "产品包装": "30s"}},
            {"name": "汤臣儿童多维整体", "source": "sku", "filters": {"品类": "多维-儿童", "品牌": "汤臣倍健"}},
        ],
    },
    "鱼油": {
        "cat": "鱼油",
        "rows": [
            {"name": "200粒",   "source": "sku", "filters": {"品类": "鱼油", "品牌产品": "汤臣倍健(鱼油软胶囊)", "产品包装": "1gx200s"}},
            {"name": "100粒",   "source": "sku", "filters": {"品类": "鱼油", "品牌产品": "汤臣倍健(鱼油软胶囊)", "产品包装": "1gx100s"}},
            {"name": "晶纯60粒","source": "sku", "filters": {"品类": "鱼油", "品牌产品": "汤臣倍健晶纯(鱼油软胶囊)", "产品包装": "0.8gx60s"}},
            {"name": "汤臣鱼油总体", "source": "sku", "filters": {"品类": "鱼油", "品牌": "汤臣倍健"}, "dist_source": "distribution", "dist_filters": {"品牌_NEW": "汤臣倍健鱼油"}},
        ],
    },
    "氨糖": {
        "cat": "关节护理",
        "rows": [
            {"name": "旧品", "source": "brand", "filters": {"品类": "关节护理", "品牌产品": "健力多蓝氨糖(氨糖软骨素钙片)"}},
            {"name": "金装", "source": "brand", "filters": {"品类": "关节护理", "品牌产品": "健力多金装氨糖(氨糖加软骨素钙片)"}},
            {"name": "白金", "source": "brand", "filters": {"品类": "关节护理", "品牌产品": "健力多白金氨糖(氨糖硫酸软骨素钙片)"}},
            {"name": "OTC",  "source": "brand", "filters": {"品类": "关节护理", "品牌产品": "健力多(硫酸氨基葡萄糖胶囊)"}},
            {"name": "金装280片礼盒装", "source": "sku", "filters": {"品类": "关节护理", "品牌产品": "健力多金装氨糖(氨糖加软骨素钙片)", "产品包装": "1.18gx70sx4p"}},
            {"name": "白金150片",       "source": "sku", "filters": {"品类": "关节护理", "品牌产品": "健力多白金氨糖(氨糖硫酸软骨素钙片)", "产品包装": "1.16gx150s"}},
            {"name": "OTC60粒",         "source": "sku", "filters": {"品类": "关节护理", "品牌产品": "健力多(硫酸氨基葡萄糖胶囊)", "产品包装": "0.25gx60s"}},
            {"name": "蓝氨糖120片",     "source": "sku", "filters": {"品类": "关节护理", "品牌产品": "健力多蓝氨糖(氨糖软骨素钙片)", "产品包装": "0.9gx120s"}},
            {"name": "健力多整体",       "source": "sku", "filters": {"品类": "关节护理", "品牌": "健力多"}},
        ],
    },
    "益生菌": {
        "cat": "益生菌",
        "rows": [
            {"name": "蓝帽20袋", "source": "sku", "filters": {"品类": "益生菌", "品牌产品": "益倍适(益生菌粉)", "产品包装": "1.5gx20d"}},
            {"name": "蓝帽48袋", "source": "sku", "filters": {"品类": "益生菌", "品牌产品": "益倍适(益生菌粉)", "产品包装": "1.5gx20dx2h+1.5gx8d"}},
            {"name": "畅护10袋", "source": "sku", "filters": {"品类": "益生菌", "品牌产品": "益倍适(畅护益生菌固体饮料)", "产品包装": "2.5gx10d"}},
            {"name": "其他",     "source": "sku", "filters": {"品类": "益生菌", "品牌": "Life-Space"}, "exclude_any": [
                {"品牌产品": "益倍适(益生菌粉)", "产品包装": "1.5gx20d"},
                {"品牌产品": "益倍适(益生菌粉)", "产品包装": "1.5gx20dx2h+1.5gx8d"},
                {"品牌产品": "益倍适(畅护益生菌固体饮料)", "产品包装": "2.5gx10d"},
                {"品牌产品": "益倍适(B420益生菌固体饮料)", "产品包装": "1.5gx20d"},
            ]},
            {"name": "益君康30片", "source": "sku", "filters": {"品类": "益生菌", "品牌产品": "益君康(复方嗜酸乳杆菌片)", "产品包装": "0.5gx30s"}},
            {"name": "B420 20袋",  "source": "sku", "filters": {"品类": "益生菌", "品牌产品": "益倍适(B420益生菌固体饮料)", "产品包装": "1.5gx20d"}},
            {"name": "益倍适总体", "source": "sku", "filters": {"品类": "益生菌", "品牌": "Life-Space"}, "dist_source": "distribution", "dist_filters": {"品牌_NEW": "益倍适"}},
        ],
    },
}

TITLE_MAP = {
    "蛋白粉": "汤臣蛋白粉各系列-线下药店市场指标趋势",
    "成人钙": "汤臣成人钙SKU-市场指标趋势分析",
    "儿童钙": "儿童钙-SKU市场指标趋势分析",
    "成人多维": "汤臣成人多维SKU-市场指标趋势分析",
    "儿童多维": "儿童多维SKU-线下药店市场指标趋势",
    "鱼油": "汤臣鱼油各规格-线下药店市场指标趋势",
    "氨糖": "健力多氨糖各SKU-线下药店市场指标趋势",
    "益生菌": "益倍适各系列-线下药店市场指标趋势",
}

SA_COLORS = ["#A6A6A6", "#FFC000", "#ED7D31", "#92D050", "#5B9BD5", "#7030A0", "#00B050", "#C00000", "#4472C4", "#7F6000"]

SHARE_YMAX = {
    "蛋白粉": 60,
    "成人钙": 6,
    "儿童钙": 2,
    "成人多维": 5,
    "儿童多维": 25,
    "鱼油": 45,
    "氨糖": 25,
    "益生菌": 10,
}

SHARE_DECIMALS = {
    "蛋白粉": 0,
    "成人钙": 0,
    "儿童钙": 1,
    "成人多维": 1,
    "儿童多维": 1,
    "鱼油": 0,
    "氨糖": 0,
    "益生菌": 0,
}

CHART_NAMES = {
    "蛋白粉": {
        "bar":    ["旧品", "金装", "白金", "E钙"],
        "brand_total_name": "汤臣整体",
        "price":  ["金装礼盒装300g*2p", "白金礼盒装330g*2p", "E钙蛋520g", "金装450g", "白金480g"],
        "dist":   ["旧品", "金装", "白金", "E钙", "汤臣整体"],
        "power":  ["旧品", "金装", "白金", "E钙", "汤臣整体"],
        "bar_colors": {
            "旧品": "#A6A6A6",
            "金装": "#4472C4",
            "白金": "#FFC000",
            "E钙": "#92D050",
            "金装礼盒装300g*2p": "#5B9BD5",
            "白金礼盒装330g*2p": "#FFD966",
            "E钙蛋520g": "#00B050",
            "金装450g": "#2F5597",
            "白金480g": "#BF9000",
            "汤臣整体": "#7030A0",
        },
    },
    "成人钙": {
        "bar":    ["其他", "200粒x2", "120粒", "焕动力120粒"],
        "brand_total_name": "汤臣钙整体",
        "price":  ["200粒x2", "120粒", "焕动力120粒", "钙尔奇D600 60片"],
        "dist":   ["200粒x2", "120粒", "焕动力120粒", "汤臣钙DK整体", "钙尔奇D600 60片"],
        "power":  ["200粒x2", "120粒", "焕动力120粒", "汤臣钙DK整体", "钙尔奇D600 60片"],
        "bar_colors": {
            "200粒x2": "#4472C4", "120粒": "#FFC000", "焕动力120粒": "#92D050", "其他": "#A6A6A6",
            "汤臣钙DK整体": "#7030A0", "钙尔奇D600 60片": "#7F6000", "汤臣钙整体": "#7030A0",
        },
    },
    "儿童钙": {
        "bar":    ["牛初乳60片*2", "钙铁锌60片", "钙镁90片", "液体钙12袋"],
        "brand_total_name": "汤臣儿童钙整体",
        "price":  ["牛初乳60片*2", "钙镁90片", "液体钙12袋", "钙铁锌60片", "锌钙特葡萄糖酸钙锌口服液24袋"],
        "dist":   ["牛初乳60片*2", "钙镁90片", "液体钙12袋", "钙铁锌60片", "锌钙特葡萄糖酸钙锌口服液24袋"],
        "power":  ["牛初乳60片*2", "钙镁90片", "液体钙12袋", "钙铁锌60片", "锌钙特葡萄糖酸钙锌口服液24袋"],
        "bar_colors": {
            "牛初乳60片*2": "#A6A6A6", "钙铁锌60片": "#FFC000", "钙镁90片": "#5B9BD5", "液体钙12袋": "#92D050",
            "锌钙特葡萄糖酸钙锌口服液24袋": "#7F6000", "汤臣儿童钙整体": "#7030A0",
        },
    },
    "成人多维": {
        "bar":    ["男维60片", "男维120片", "女维60片", "女维120片"],
        "brand_total_name": "汤臣多维整体",
        "price":  ["女维120片", "女维60片", "男维120片", "男维60片", "银善存91sx2p", "善存多维元素片(29)91sx2p"],
        "dist":   ["女维120片", "女维60片", "男维120片", "男维60片", "银善存91sx2p", "善存多维元素片(29)91sx2p"],
        "power":  ["女维120片", "女维60片", "男维120片", "男维60片", "银善存91sx2p", "善存多维元素片(29)91sx2p"],
        "bar_colors": {
            "女维120片": "#FFC000", "女维60片": "#FFD966",
            "男维120片": "#4472C4", "男维60片": "#5B9BD5",
            "银善存91sx2p": "#7F6000", "善存多维元素片(29)91sx2p": "#BF9000", "汤臣多维整体": "#7030A0",
        },
    },
    "儿童多维": {
        "bar":    ["儿童多维60s", "青少年多维60s"],
        "brand_total_name": "汤臣儿童多维整体",
        "sales_decimals": 1,
        "price":  ["汤臣儿童60片", "汤臣青少年60片", "仁合堂五维赖氨酸12袋", "草仙药业五维赖氨酸片36s", "小施尔康多维咀嚼片(10)30s"],
        "dist":   ["汤臣儿童60片", "汤臣青少年60片", "仁合堂五维赖氨酸12袋", "草仙药业五维赖氨酸片36s", "小施尔康多维咀嚼片(10)30s"],
        "power":  ["汤臣儿童60片", "汤臣青少年60片", "仁合堂五维赖氨酸12袋", "草仙药业五维赖氨酸片36s", "小施尔康多维咀嚼片(10)30s"],
        "bar_colors": {
            "儿童多维60s": "#8FAADC",
            "青少年多维60s": "#2E75B6",
            "汤臣儿童60片": "#8FAADC",
            "汤臣青少年60片": "#2E75B6",
            "仁合堂五维赖氨酸12袋": "#ED7D31",
            "草仙药业五维赖氨酸片36s": "#FFC000",
            "小施尔康多维咀嚼片(10)30s": "#70AD47",
            "汤臣儿童多维整体": "#8FAADC",
        },
    },
    "鱼油": {
        "bar":    ["200粒", "100粒", "晶纯60粒"],
        "brand_total_name": "汤臣鱼油总体",
        "price":  ["200粒", "100粒", "晶纯60粒"],
        "dist":   ["200粒", "100粒", "晶纯60粒", "汤臣鱼油总体"],
        "power":  ["200粒", "100粒", "晶纯60粒", "汤臣鱼油总体"],
        "bar_colors": {
            "200粒": "#4472C4", "100粒": "#FFC000", "晶纯60粒": "#92D050",
            "汤臣鱼油总体": "#7030A0",
        },
    },
    "氨糖": {
        "bar":    ["旧品", "金装", "白金", "OTC", "蓝氨糖120片"],
        "brand_total_name": "健力多整体",
        "price":  ["金装280片礼盒装", "白金150片", "OTC60粒", "蓝氨糖120片"],
        "dist":   ["旧品", "金装", "白金", "OTC"],
        "power":  ["旧品", "金装", "白金", "OTC"],
        "bar_colors": {
            "旧品": "#BFBFBF", "金装": "#FFC000", "白金": "#C55A11", "OTC": "#00B050",
            "蓝氨糖120片": "#5B9BD5",
            "金装280片礼盒装": "#FFC000", "白金150片": "#C55A11",
            "OTC60粒": "#00B050", "健力多整体": "#7030A0",
        },
        "price_colors": {"蓝氨糖120片": "#8FAADC"},
    },
    "益生菌": {
        "bar":    ["其他", "蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋"],
        "brand_total_name": "益倍适总体",
        "price":  ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "益君康30片"],
        "dist":   ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "益倍适总体", "益君康30片"],
        "power":  ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "益倍适总体", "益君康30片"],
        "bar_colors": {
            "蓝帽20袋": "#4472C4", "蓝帽48袋": "#2F5597", "畅护10袋": "#FFC000",
            "B420 20袋": "#92D050", "其他": "#A6A6A6",
            "益倍适总体": "#7030A0", "益君康30片": "#7F6000",
        },
    },
}

# ====================== Part B sku_analysis 函数 ======================
def norm(v):
    if pd.isna(v):
        return ""
    return str(v).strip().replace(" ", "").replace("\u3000", "").lower()


def _col_norm(s):
    return s.astype(str).str.strip().str.replace(" ", "", regex=False).str.replace("\u3000", "", regex=False).str.lower()


def source_df(source):
    if source == "brand":
        return brand_df
    if source == "distribution":
        return dist_df
    return sku_df


def filter_df(df, months, filters=None, exclude_any=None):
    mask = df["year_month"].isin(months) if "year_month" in df.columns else pd.Series(True, index=df.index)
    for col, val in (filters or {}).items():
        if col not in df.columns:
            return df.iloc[:0]
        mask &= _col_norm(df[col]) == norm(val)
    for ex in (exclude_any or []):
        ex_mask = pd.Series(True, index=df.index)
        for col, val in ex.items():
            if col not in df.columns:
                ex_mask = pd.Series(False, index=df.index)
                break
            ex_mask &= _col_norm(df[col]) == norm(val)
        mask &= ~ex_mask
    return df.loc[mask]


def calc_sales_price(df):
    sales_raw = float(df[SALES_COL].sum()) if SALES_COL in df.columns else 0.0
    qty = float(df[QTY_COL].sum()) if QTY_COL in df.columns else 0.0
    sales_m = sales_raw / 1000
    price = sales_raw / qty * 10 if qty != 0 else np.nan
    return sales_m, price


def calc_dist(row_conf, months):
    src = row_conf.get("dist_source", row_conf["source"])
    filters = row_conf.get("dist_filters", row_conf.get("filters", {}))
    df = filter_df(source_df(src), months, filters)
    if df.empty or DIST_COL not in df.columns:
        return np.nan
    valid = df[DIST_COL].notna()
    if not valid.any():
        return np.nan
    if SALES_COL in df.columns and df.loc[valid, SALES_COL].sum() > 0:
        rate = np.average(df.loc[valid, DIST_COL], weights=df.loc[valid, SALES_COL])
    else:
        rate = df.loc[valid, DIST_COL].mean()
    return rate * 100


_CACHE_VER = 16


@st.cache_data(ttl=300, show_spinner=False)
def build_metrics_cached(cat, rows_json, months_json, _ver=_CACHE_VER):
    import json
    rows = json.loads(rows_json)
    months = json.loads(months_json)
    months_set = set(months)

    filter_cols = {"品类", "品牌", "品牌产品", "产品包装", "品名(含属性)", "品牌_NEW"}
    for row in rows:
        filter_cols.update(row.get("filters", {}).keys())
        filter_cols.update(row.get("dist_filters", {}).keys())
        for ex in row.get("exclude_any", []):
            filter_cols.update(ex.keys())

    sources_needed = set()
    for row in rows:
        sources_needed.add(row["source"])
        sources_needed.add(row.get("dist_source", row["source"]))

    norm_src = {}
    for src in sources_needed:
        raw = source_df(src)
        nd = raw.copy()
        for col in filter_cols:
            if col in nd.columns:
                nd[f"_n_{col}"] = _col_norm(nd[col])
        if "year_month" in nd.columns:
            nd = nd[nd["year_month"].isin(months_set)]
        norm_src[src] = nd

    def fast_filter(nd, months_list, filters=None, exclude_any=None):
        ms = set(months_list)
        mask = nd["year_month"].isin(ms) if "year_month" in nd.columns else pd.Series(True, index=nd.index)
        for col, val in (filters or {}).items():
            ncol = f"_n_{col}"
            if ncol not in nd.columns:
                return nd.iloc[:0]
            mask &= nd[ncol] == norm(val)
        for ex in (exclude_any or []):
            ex_mask = pd.Series(True, index=nd.index)
            for col, val in ex.items():
                ncol = f"_n_{col}"
                if ncol not in nd.columns:
                    ex_mask = pd.Series(False, index=nd.index)
                    break
                ex_mask &= nd[ncol] == norm(val)
            mask &= ~ex_mask
        return nd.loc[mask]

    cat_sales = (
        fast_filter(norm_src.get("sku", norm_src[rows[0]["source"]]), months, {"品类": cat})
        .groupby("year_month")[SALES_COL].sum() / 1000
    ).to_dict()

    records = []
    for m in months:
        for row in rows:
            src = row["source"]
            nd = norm_src[src]
            df = fast_filter(nd, [m], row.get("filters", {}), row.get("exclude_any", []))
            sales_m, price = calc_sales_price(df)
            share = sales_m / cat_sales.get(m, 0) * 100 if cat_sales.get(m, 0) else np.nan

            dsrc = row.get("dist_source", src)
            dnd = norm_src[dsrc]
            dfilters = row.get("dist_filters", row.get("filters", {}))
            ddf = fast_filter(dnd, [m], dfilters)

            def _agg_rate(col):
                # ND 数值铺货率：优先“铺货率”列，缺失时回落到“加权铺货率”
                _c = col
                if _c not in ddf.columns and col == ND_COL and ND_FALLBACK in ddf.columns:
                    _c = ND_FALLBACK
                if ddf.empty or _c not in ddf.columns:
                    return np.nan
                col = _c
                valid = ddf[col].notna()
                if not valid.any():
                    return np.nan
                if SALES_COL in ddf.columns and ddf.loc[valid, SALES_COL].sum() > 0:
                    r = np.average(ddf.loc[valid, col], weights=ddf.loc[valid, SALES_COL])
                else:
                    r = ddf.loc[valid, col].mean()
                return r * 100

            # WD 动销铺货率（优先动销铺货率列，缺列回退加权铺货率）
            dist = _agg_rate(WD_COL)
            # ND 数值铺货率（铺货率列，口径与 WD 一致，缺列则为空）
            nd = _agg_rate(ND_COL) if ND_AVAILABLE else np.nan

            power = share / dist * 100 if dist else np.nan
            records.append({
                "month": m, "label": ym_lab(m), "name": row["name"],
                "sales_m": sales_m, "share": share, "price": price,
                "dist": dist, "nd": nd, "power": power,
            })
    return pd.DataFrame(records)


# ====================== Part B 公共绘图函数 ======================
def _chart_base(fig, title, height=380, legend_y=1.08, show_yaxis=False, legend_below=False):
    if legend_below:
        leg = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=12))
        title_y = 0.93
        margin_t = 110
        margin_b = 48
    else:
        leg = dict(orientation="h", yanchor="bottom", y=legend_y, xanchor="center", x=0.5, font=dict(size=12))
        title_y = 0.93
        margin_t = 100
        margin_b = 48
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.5, xanchor="center", y=title_y, yanchor="top", font=dict(size=15, color="#333")),
        height=height, margin=dict(t=margin_t, b=margin_b, l=10, r=54),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Microsoft YaHei", size=12),
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(showgrid=False, zeroline=False, visible=show_yaxis),
        legend=leg,
    )
    return fig


# New products that must always show 环比 annotation even if share is small
NEW_PRODUCTS = {
    "E钙", "E钙蛋520g",
    "焕动力120粒",
    "液体钙12袋",
    "晶纯60粒",
    "OTC", "OTC60粒",
    "B420 20袋",
    "蓝氨糖120片",
}


def make_stacked_bar(df, metric, title, names, colors, text_decimals=0, height=380, legend_y=1.08, y_max=None, brand_total_name=None):
    fig = go.Figure()
    labels = df["label"].drop_duplicates().tolist()
    for idx, name in enumerate(names):
        sub = df[df["name"] == name].set_index("label").reindex(labels)
        vals = pd.to_numeric(sub[metric], errors="coerce").fillna(0)
        c = colors.get(name, SA_COLORS[idx % len(SA_COLORS)])
        # 根据值大小动态调整字体：小于1的小数字用更小字体
        text_labels = []
        _bar_font_sizes = []
        for v in vals:
            if v <= 0:
                text_labels.append("")
                _bar_font_sizes.append(12)
            elif v < 1:
                text_labels.append(f"{v:.{text_decimals}f}")
                _bar_font_sizes.append(12)
            else:
                text_labels.append(f"{v:.{text_decimals}f}")
                _bar_font_sizes.append(12)
        fig.add_bar(
            x=labels, y=vals, name=name, marker_color=c,
            text=text_labels,
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=_bar_font_sizes, color="white", family="Arial, sans-serif"),
            textangle=0,
            hovertemplate=f"{name}<br>%{{x}}：%{{y:.{text_decimals}f}}<extra></extra>",
        )
    fig.update_layout(barmode="stack")

    # --- Add total annotations above each bar ---
    # Use brand total data for the displayed value, but position at stacked bar top
    _totals_display = []   # brand total value (for text)
    _totals_position = []  # stacked bar sum (for y position)
    for _lbl in labels:
        # Calculate stacked bar sum for positioning
        _stack_sum = 0.0
        for _name in names:
            _sub = df[(df["label"] == _lbl) & (df["name"] == _name)]
            _v = pd.to_numeric(_sub[metric], errors="coerce").fillna(0)
            if len(_v) > 0:
                _stack_sum += float(_v.iloc[0])
        _totals_position.append(_stack_sum)
        # Get brand total for display
        if brand_total_name:
            _bt = df[(df["label"] == _lbl) & (df["name"] == brand_total_name)]
            _v = pd.to_numeric(_bt[metric], errors="coerce").fillna(0)
            _t = float(_v.iloc[0]) if len(_v) > 0 else 0.0
        else:
            _t = _stack_sum
        _totals_display.append(_t)
    _max_pos = max(_totals_position) if _totals_position else 0
    _decimals = 0 if metric == "share" else text_decimals
    for _i, _lbl in enumerate(labels):
        _t_display = _totals_display[_i]
        _t_pos = _totals_position[_i]
        if _t_display > 0:
            fig.add_annotation(
                x=_lbl, y=_t_pos,
                text=f"<b>{_t_display:.{_decimals}f}</b>",
                showarrow=False,
                yshift=10,
                font=dict(size=14, color="#FF0000", family="Arial, sans-serif"),
            )
    # Set y-axis range for sales chart to accommodate annotations
    if metric != "share" and _max_pos > 0:
        fig.update_layout(yaxis=dict(showgrid=False, zeroline=False, visible=False, range=[0, _max_pos * 1.15]))

    if metric == "share" and len(labels) >= 2:
        last_label, prev_label = labels[-1], labels[-2]
        month_num = last_label.split("M")[-1] if "M" in last_label else ""
        ymax = y_max if y_max is not None else 100
        fig.add_annotation(
            x=last_label, y=ymax * 1.12, text=f"<b>{month_num}月环比<br>(pts)</b>", showarrow=False,
            xshift=26, yshift=0, font=dict(size=12, color="#333"),
        )
        y_cursor = 0.0
        for _hb_idx, name in enumerate(names):
            last_v = pd.to_numeric(df.loc[(df["label"] == last_label) & (df["name"] == name), metric], errors="coerce")
            prev_v = pd.to_numeric(df.loc[(df["label"] == prev_label) & (df["name"] == name), metric], errors="coerce")
            if last_v.notna().any() and prev_v.notna().any():
                val = float(last_v.iloc[0]); base = float(prev_v.iloc[0])
                diff = val - base
                y_center = y_cursor + val / 2
                # Skip 环比 annotation only for non-新产品 with very small share
                # Use relative threshold: 3% of y-axis max (scales with category)
                _skip_threshold = ymax * 0.03
                if val >= _skip_threshold or name in NEW_PRODUCTS:
                    # Stagger annotations vertically to avoid overlap for small segments
                    _hb_yshift = 0
                    if val < (ymax * 0.05):
                        _stagger = [8, -8, 5, -5, 10, -10]
                        _hb_yshift = _stagger[_hb_idx % len(_stagger)]
                    _hb_dec = 2 if abs(diff) < 0.05 else 1
                    fig.add_annotation(
                        x=last_label, y=y_center, text=f"{diff:+.{_hb_dec}f}", showarrow=False,
                        xshift=26, yshift=_hb_yshift,
                        font=dict(size=13, color="#00A85A" if diff >= 0 else "#E53935", family="Microsoft YaHei", weight="bold"),
                    )
                y_cursor += val
            else:
                y_cursor += float(last_v.iloc[0]) if last_v.notna().any() else 0
    fig = _chart_base(fig, title, height, legend_y, show_yaxis=False, legend_below=True)
    # 柱图绘图区向两边拉长：左右边距与下方线图一致（l=24/r=24），柱子整体更宽
    fig.update_layout(margin=dict(t=110, b=48, l=24, r=24))
    fig.update_layout(showlegend=True)
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10, family="Microsoft YaHei"))
    if metric == "share":
        ymax = y_max if y_max is not None else 100
        fig.update_layout(yaxis=dict(showgrid=False, zeroline=False, visible=False, range=[0, ymax * 1.25]))
    return fig


def make_line_chart(df, metric, title, names, colors, decimals=0, height=380, label_mode="endpoints", cat_label=None, dashed=False, margin_l=10, margin_r=54):
    fig = go.Figure()
    labels = df["label"].drop_duplicates().tolist()

    # ---- Category+metric-specific label configuration (Tasks 2-8) ----
    # full_above:  all months labeled, above the line
    # full_below:  all months labeled, below the line
    # highpoint_above: start/end + data high point, above the line
    # default:     fallback mode for items not explicitly listed
    _LC = {
        # === 蛋白粉 ===
        # price: 白金礼盒装 above, 金装礼盒 below, E钙蛋 above
        ("蛋白粉", "price"): {"default": "all", "product_month_yshift_delta": {"白金480g": {"25M3": -8}}},
        # 金装450g/白金480g use alternate labeling
        # dist: 汤臣整体 all above (close); others endpoints, staggered to avoid overlap
        ("蛋白粉", "dist"):  {"full_above": ["金装", "汤臣整体", "旧品"], "month_xshift": {"25M1": -12}, "month_yshift": {"25M1": -12}, "product_yshift_offset": {"白金": -11}, "product_month_yshift_delta": {"E钙": {"26M6": 12}, "白金": {"26M6": 8}, "金装": {"26M6": -12}}, "default": "endpoints"},
        # power: same pattern as dist
        ("蛋白粉", "power"): {"full_above": ["汤臣整体"], "product_month_xshift": {"金装": {"26M6": 8}, "白金": {"26M6": 8}, "旧品": {"26M6": 8}}, "product_month_yshift_delta": {"旧品": {"26M6": 4}, "白金": {"25M1": -19}}, "default": "endpoints"},
        # === 成人钙 ===
        # dist: all closer, staggered
        ("成人钙", "dist"):  {"full_above": ["200粒x2", "焕动力120粒", "钙尔奇D600 60片"], "full_below": ["汤臣钙DK整体", "120粒"], "default": "endpoints"},
        # power: 200粒x2 above, 汤臣钙DK整体 below, 钙尔奇 start/end, 120粒 below
        ("成人钙", "power"): {"full_above": ["200粒x2"], "full_below": ["汤臣钙DK整体", "120粒"], "alternate_below": ["焕动力120粒"], "default": "endpoints"},
        # === 儿童钙 ===
        ("儿童钙", "price"): {"product_month_yshift_delta": {"钙铁锌60片": {"25M7": -8}, "液体钙12袋": {"25M7": -8}}, "product_month_xshift": {"液体钙12袋": {"25M7": -8}}},
        ("儿童钙", "dist"):  {"full_above": ["锌钙特葡萄糖酸钙锌口服液24袋"], "month_xshift": {"25M1": -12, "26M6": 12}, "product_month_xshift": {"锌钙特葡萄糖酸钙锌口服液24袋": {"25M1": 12, "26M6": -12}}, "product_month_yshift_delta": {"钙镁90片": {"25M1": -8, "26M6": -11}}, "default": "endpoints"},
        ("儿童钙", "power"): {"full_above": ["锌钙特葡萄糖酸钙锌口服液24袋"], "product_month_yshift_delta": {"钙镁90片": {"25M1": -11, "26M6": -11}}, "product_month_xshift": {"钙镁90片": {"25M1": -8, "26M6": 8}}, "default": "endpoints"},
        # === 成人多维 ===
        ("成人多维", "price"): {"full_below": ["善存多维元素片(29)91sx2p", "女维60片"], "product_yshift_offset": {"女维60片": -8}, "default": "all"},
        ("成人多维", "dist"):  {"full_above": ["银善存91sx2p"], "full_below": ["善存多维元素片(29)91sx2p"], "alternate_above": ["男维120片"], "month_xshift": {"25M1": -8, "26M6": 8}, "product_month_yshift_delta": {"女维120片": {"25M1": -4}, "男维60片": {"26M6": -8}}, "default": "endpoints"},
        ("成人多维", "power"): {"alternate_above": ["善存多维元素片(29)91sx2p", "银善存91sx2p"], "month_xshift": {"25M1": -4, "26M6": 4}, "product_month_yshift_delta": {"女维120片": {"25M1": 8, "26M6": 4}, "男维120片": {"25M1": 4, "26M6": 2}, "男维60片": {"25M1": -8, "26M6": -8}, "女维60片": {"25M1": -12, "26M6": -12}}, "product_month_xshift": {"女维120片": {"25M1": -4, "26M6": 4}, "男维120片": {"25M1": -4, "26M6": 4}, "男维60片": {"25M1": -8, "26M6": 8}, "女维60片": {"25M1": -8, "26M6": 8}}, "default": "endpoints"},
        # === 鱼油 ===
        ("鱼油", "price"): {"full_above": ["200粒", "100粒", "晶纯60粒"], "default": "all", "yshift_base": 10},
        ("鱼油", "power"): {"full_above": ["汤臣鱼油总体", "100粒"], "product_mode": {"200粒": "endpoints"}, "product_month_yshift_delta": {"200粒": {"25M1": 19}, "晶纯60粒": {"25M5": -19, "25M6": 19}, "汤臣鱼油总体": {"25M3": 19, "25M4": 34}}, "default": "highlow"},
        ("鱼油", "dist"):  {"full_above": ["200粒"], "full_below": ["100粒", "晶纯60粒"], "product_month_yshift_delta": {"100粒": {"25M1": -19, "25M2": -19, "25M3": 19, "25M4": -19, "26M6": 15}}, "default": "all"},
        # === 氨糖 ===
        ("氨糖", "price"): {"full_below": ["OTC60粒"], "default": "all"},
        ("氨糖", "power"): {"full_above": ["OTC", "金装"], "month_override": {"OTC": {"26M2": "below"}}, "month_xshift": {"25M1": -8, "26M6": 8}, "product_month_xshift": {"OTC": {"25M9": -8, "25M10": -8}}, "default": "endpoints"},
        ("氨糖", "dist"):  {"full_above": ["金装", "白金"], "full_below": ["旧品", "OTC"], "month_xshift": {"25M1": -8, "26M6": 8}, "product_yshift_offset": {"旧品": -8}, "default": "endpoints"},
        # === 益生菌 ===
        ("益生菌", "price"): {"full_above": ["蓝帽48袋", "蓝帽20袋", "益君康30片"], "full_below": ["畅护10袋", "B420 20袋"], "month_override": {"B420 20袋": {"26M4": "below", "26M6": "above"}}, "month_yshift": {"B420 20袋": {"26M4": 12}}, "default": "alternate"},
        ("益生菌", "dist"):  {"alternate_above": ["畅护10袋"], "start_from": {"畅护10袋": "25M5"}, "include_months": {"畅护10袋": ["25M4"]}, "month_xshift": {"25M1": -4}, "default": "alternate"},
        ("益生菌", "power"): {"alternate_above": ["蓝帽48袋", "益倍适总体", "畅护10袋"], "start_from": {"畅护10袋": "25M5", "B420 20袋": "26M5"}, "skip_months": {"畅护10袋": ["25M4"], "B420 20袋": ["25M4"]}, "null_months": {"畅护10袋": ["25M4"], "B420 20袋": ["26M4"]}, "month_yshift": {"B420 20袋": {"26M5": -3}}, "month_xshift": {"25M1": -4, "26M6": 4}, "default": "endpoints"},
        # === 儿童多维 ===
        ("儿童多维", "price"): {"full_above": ["汤臣儿童60片", "汤臣青少年60片", "草仙药业五维赖氨酸片36s"], "full_below": ["仁合堂五维赖氨酸12袋", "小施尔康多维咀嚼片(10)30s"], "default": "endpoints"},
        ("儿童多维", "dist"):  {"full_above": ["小施尔康多维咀嚼片(10)30s", "汤臣儿童60片", "草仙药业五维赖氨酸片36s"], "full_below": ["汤臣青少年60片", "仁合堂五维赖氨酸12袋"], "default": "endpoints"},
        ("儿童多维", "power"): {"full_above": ["仁合堂五维赖氨酸12袋", "草仙药业五维赖氨酸片36s"], "full_below": ["小施尔康多维咀嚼片(10)30s", "汤臣儿童60片", "汤臣青少年60片"], "default": "endpoints"},
    }
    cfg = _LC.get((cat_label, metric), {})
    full_above = set(cfg.get("full_above", []))
    full_below = set(cfg.get("full_below", []))
    alternate_above = set(cfg.get("alternate_above", []))
    alternate_below = set(cfg.get("alternate_below", []))
    highpoint_above = set(cfg.get("highpoint_above", []))
    highpoint_below = set(cfg.get("highpoint_below", []))
    default_mode = cfg.get("default", label_mode)
    start_from = cfg.get("start_from", {})  # {name: "25M5"} skip labels before this month
    month_override = cfg.get("month_override", {})  # {name: {"26M4": "below", "26M6": "above"}}
    yshift_base = cfg.get("yshift_base", 6)  # base yshift for labels
    skip_months = cfg.get("skip_months", {})  # {name: ["25M4"]} skip specific month labels
    null_months = cfg.get("null_months", {})  # {name: ["25M4"]} null out data (removes line+point)
    month_yshift = cfg.get("month_yshift", {})  # {name: {"26M4": -23}} override yshift for specific months
    month_xshift = cfg.get("month_xshift", {})  # {"25M1": -2} global xshift by month (all products)
    include_months = cfg.get("include_months", {})  # {"name": ["25M4"]} force include months (overrides start_from)
    product_yshift_offset = cfg.get("product_yshift_offset", {})  # {"name": -8} per-product yshift offset
    product_month_xshift = cfg.get("product_month_xshift", {})  # {"OTC": {"25M9": -8}} per-product per-month xshift
    product_month_yshift_delta = cfg.get("product_month_yshift_delta", {})  # {"100粒": {"25M1": -19}} per-product per-month yshift delta
    product_mode = cfg.get("product_mode", {})  # {"200粒": "endpoints"} per-product mode override

    label_specs = []  # 收集所有数据标签，最后统一做防重叠分离

    for idx, name in enumerate(names):
        sub = df[df["name"] == name].set_index("label").reindex(labels)
        vals = pd.to_numeric(sub[metric], errors="coerce")
        # Apply null_months: set specific months to NaN (removes data point + line)
        if name in null_months:
            _null_set = set(null_months[name])
            for _ni in range(len(labels)):
                if str(labels[_ni]) in _null_set and _ni < len(vals):
                    vals.iloc[_ni] = float('nan')
        c = colors.get(name, SA_COLORS[idx % len(SA_COLORS)])
        if dashed:
            fig.add_scatter(
                x=labels, y=vals, mode="lines", name=name,
                line=dict(width=2.0, shape="spline", smoothing=1.3, color=c, dash="6px,4px"),
                hovertemplate=f"{name}<br>%{{x}}：%{{y:.{decimals}f}}<extra></extra>",
            )
        else:
            fig.add_scatter(
                x=labels, y=vals, mode="lines+markers", name=name,
                line=dict(width=2.3, shape="spline", smoothing=1.3, color=c),
                marker=dict(size=5),
                hovertemplate=f"{name}<br>%{{x}}：%{{y:.{decimals}f}}<extra></extra>",
            )
        valid = [i for i, v in enumerate(vals) if not pd.isna(v)]
        if not valid:
            continue

        # --- Determine which months to annotate (Task 2-8) ---
        # --- 标注规则（page3 折线图统一）：隔1个月标注 + 首尾月份必标 ---
        annotate_indices = set()
        for j in range(0, len(valid), 2):
            annotate_indices.add(valid[j])
        if valid:
            annotate_indices.add(valid[-1])  # 尾月必标
            annotate_indices.add(valid[0])   # 首月必标

        # --- Apply start_from filter: skip labels before specified month ---
        if name in start_from:
            _sf = start_from[name]
            _sf_val = int(_sf.split("M")[0]) * 12 + int(_sf.split("M")[1])
            _sf_idx = len(labels)
            for i, lbl in enumerate(labels):
                try:
                    _ls = str(lbl)
                    _lv = int(_ls.split("M")[0]) * 12 + int(_ls.split("M")[1])
                    if _lv >= _sf_val:
                        _sf_idx = i
                        break
                except:
                    pass
            annotate_indices = {i for i in annotate_indices if i >= _sf_idx}

        # --- Apply include_months: force include specific months (overrides start_from) ---
        if name in include_months:
            _inc_set = set(include_months[name])
            for i in range(len(labels)):
                if str(labels[i]) in _inc_set and i < len(vals) and not pd.isna(vals.iloc[i]):
                    annotate_indices.add(i)

        # --- Apply skip_months filter: remove specific months ---
        if name in skip_months:
            _skip_set = set(skip_months[name])
            annotate_indices = {i for i in annotate_indices if str(labels[i]) not in _skip_set}

        # --- Determine yshift: above (positive) or below (negative) ---
        # Labels close to data point, not overlapping; tight stagger
        _ov = month_override.get(name, {})

        _ys = month_yshift.get(name, {})
        for i in sorted(annotate_indices):
            _lbl = str(labels[i]) if i < len(labels) else ""
            # Hardcoded skip: 益生菌 power 25M4 for 畅护10袋 & B420 20袋
            if cat_label == "益生菌" and metric == "power" and _lbl == "25M4" and name in ("畅护10袋", "B420 20袋"):
                continue
            if _lbl in _ov:
                _below = _ov[_lbl] == "below"
            else:
                _below = name in full_below or name in alternate_below or name in highpoint_below
            # Also check hardcoded skip for start_from items
            if name in start_from:
                try:
                    _my_lv = int(_lbl.split("M")[0]) * 12 + int(_lbl.split("M")[1])
                    _sf_val2 = int(str(start_from[name]).split("M")[0]) * 12 + int(str(start_from[name]).split("M")[1])
                    if _my_lv < _sf_val2:
                        _inc_check = include_months.get(name, set())
                        if _lbl not in _inc_check:
                            continue
                except:
                    pass
            # Apply month_yshift override or default
            if _lbl in _ys:
                yshift = _ys[_lbl]
            else:
                yshift = -(yshift_base + idx * 2) if _below else (yshift_base + idx * 2)
                if metric == "price":
                    yshift += 2  # Global price label upward shift ~0.05cm
            yshift += product_yshift_offset.get(name, 0)
            _pmdelta = product_month_yshift_delta.get(name, {})
            if _lbl in _pmdelta:
                yshift += _pmdelta[_lbl]
            _xshift = month_xshift.get(_lbl, 0)
            _pxshift = product_month_xshift.get(name, {})
            if _lbl in _pxshift:
                _xshift += _pxshift[_lbl]
            label_specs.append(dict(
                mi=i, yval=float(vals.iloc[i]), xshift=_xshift, yshift=yshift,
                above=(not _below), text=f"{vals.iloc[i]:.{decimals}f}",
                font=dict(size=12, color=c, family="Arial, sans-serif"),
            ))
    fig = _chart_base(fig, title, height, 1.08, legend_below=True)
    fig.update_layout(margin=dict(t=110, b=48, l=margin_l, r=margin_r))
    fig.update_xaxes(tickangle=-45, tickfont=dict(size=10, family="Microsoft YaHei"))

    # ===== 数据标签防重叠：像素空间迭代分离（避免标签互相重叠、也远离折线） =====
    if label_specs:
        _allv = pd.to_numeric(df[metric], errors="coerce").dropna()
        if len(_allv):
            _ymin0, _ymax0 = float(_allv.min()), float(_allv.max())
            _pad = (_ymax0 - _ymin0) * 0.12 if _ymax0 > _ymin0 else max(1.0, abs(_ymax0) * 0.12)
            _yrange = (_ymin0 - _pad, _ymax0 + _pad)
        else:
            _yrange = (0.0, 1.0)
        _n = len(labels)
        _W, _H = 430, height
        _mt, _mb = 110, 48
        _ml, _mr = margin_l, margin_r
        _pw = _W - _ml - _mr
        _ph = _H - _mt - _mb

        def _xpx(mi, xs):
            return _ml + (mi / (_n - 1)) * _pw + xs if _n > 1 else _ml + _pw / 2

        def _ypx(yv):
            return _mt + (_yrange[1] - yv) / (_yrange[1] - _yrange[0]) * _ph

        def _cw(t):
            return sum(12 if ord(ch) > 0x2E80 else 7 for ch in t) + 6

        for s in label_specs:
            s["cy"] = (_ypx(s["yval"]) - s["yshift"]) if s["above"] else (_ypx(s["yval"]) + s["yshift"])
            s["w"] = max(22, _cw(s["text"]))
            s["h"] = 16
            s["x0"] = _xpx(s["mi"], s["xshift"]) - s["w"] / 2
            s["x1"] = s["x0"] + s["w"]
        for _ in range(20):
            _changed = False
            _order = sorted(range(len(label_specs)), key=lambda k: label_specs[k]["cy"])
            for a in range(len(_order)):
                i = _order[a]
                for b in range(a - 1, -1, -1):
                    j = _order[b]
                    if not (label_specs[i]["x1"] > label_specs[j]["x0"] and label_specs[i]["x0"] < label_specs[j]["x1"]):
                        continue
                    if not (label_specs[i]["cy"] < label_specs[j]["cy"] + label_specs[j]["h"] / 2 + label_specs[i]["h"] / 2
                            and label_specs[i]["cy"] > label_specs[j]["cy"] - label_specs[j]["h"] / 2 - label_specs[i]["h"] / 2):
                        continue
                    _ov = (label_specs[j]["h"] / 2 + label_specs[i]["h"] / 2) - abs(label_specs[i]["cy"] - label_specs[j]["cy"])
                    if _ov <= 0:
                        continue
                    _push = _ov / 2 + 1.5
                    # 两个标签反向推开：i 按其侧向上/下，j 按其侧向下/上，最大化间距
                    if label_specs[i]["above"]:
                        label_specs[i]["cy"] -= _push
                    else:
                        label_specs[i]["cy"] += _push
                    if label_specs[j]["above"]:
                        label_specs[j]["cy"] += _push
                    else:
                        label_specs[j]["cy"] -= _push
                    for s in (label_specs[i], label_specs[j]):
                        _dist = abs(s["cy"] - _ypx(s["yval"]))
                        if _dist < 11:
                            if s["above"]:
                                s["cy"] = min(s["cy"], _ypx(s["yval"]) - 11)
                            else:
                                s["cy"] = max(s["cy"], _ypx(s["yval"]) + 11)
                    _changed = True
            if not _changed:
                break
        for s in label_specs:
            s["yshift"] = max(3.0, (_ypx(s["yval"]) - s["cy"]) if s["above"] else (s["cy"] - _ypx(s["yval"])))
            fig.add_annotation(
                x=labels[s["mi"]], y=s["yval"], text=s["text"],
                showarrow=False, xshift=s["xshift"], yshift=s["yshift"],
                font=s["font"],
            )
        fig.update_layout(yaxis=dict(range=list(_yrange)))
    return fig


def render_charts(metric_df, cat_label):
    cfg = CHART_NAMES.get(cat_label, {})
    all_names = metric_df["name"].drop_duplicates().tolist()
    colors = {n: SA_COLORS[i % len(SA_COLORS)] for i, n in enumerate(all_names)}
    colors.update(cfg.get("bar_colors", {}))

    # Cache figures in session_state to avoid re-creating on every rerun
    _cache_key = f"_sa_charts_{cat_label}"
    _data_hash = hash(metric_df.to_csv().encode())

    if _cache_key in st.session_state and st.session_state.get(f"{_cache_key}_h") == _data_hash:
        _figs = st.session_state[_cache_key]
    else:
        bar_names = cfg.get("bar", all_names)
        share_ymax = SHARE_YMAX.get(cat_label, 100)
        share_dec = SHARE_DECIMALS.get(cat_label, 0)
        _btn = cfg.get("brand_total_name")
        sales_dec = cfg.get("sales_decimals", 0)
        price_names = cfg.get("price", all_names)
        dist_names = cfg.get("dist", all_names)
        power_names = cfg.get("power", dist_names)

        nd_names = cfg.get("nd", dist_names)
        # 均价图允许单独覆盖颜色（如氨糖蓝氨糖120片在均价线中用浅蓝）
        price_colors = dict(colors)
        price_colors.update(cfg.get("price_colors", {}))
        _LM = dict(l=24, r=24)  # 线图左右边距相等，绘图区向右拉长
        _figs = {
            "bar1": make_stacked_bar(metric_df, "sales_m", "销售额（百万元）", bar_names, colors, text_decimals=sales_dec, height=437, brand_total_name=_btn),
            "bar2": make_stacked_bar(metric_df, "share", "销售额份额（%）", bar_names, colors, text_decimals=share_dec, height=437, y_max=share_ymax, brand_total_name=_btn),
            "line_wd": make_line_chart(metric_df, "dist", "WD动销铺货率（%）", dist_names, colors, decimals=0, height=437, label_mode="alternate", cat_label=cat_label, margin_l=_LM["l"], margin_r=_LM["r"]),
            "line_nd": make_line_chart(metric_df, "nd", "ND数值铺货率（%）", nd_names, colors, decimals=0, height=437, label_mode="alternate", cat_label=cat_label, dashed=True, margin_l=_LM["l"], margin_r=_LM["r"]),
            "line_price": make_line_chart(metric_df, "price", "重点SKU均价（元/盒）", price_names, price_colors, decimals=0, height=437, label_mode="alternate", cat_label=cat_label, margin_l=_LM["l"], margin_r=_LM["r"]),
            "line_power": make_line_chart(metric_df, "power", "单点卖力", power_names, colors, decimals=0, height=437, label_mode="alternate", cat_label=cat_label, margin_l=_LM["l"], margin_r=_LM["r"]),
        }
        for _lk in ("line_wd", "line_nd", "line_price", "line_power"):
            _figs[_lk].update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                            font=dict(size=10, family="Microsoft YaHei"),
                            itemsizing="constant", itemwidth=30),
            )
        st.session_state[_cache_key] = _figs
        st.session_state[f"{_cache_key}_h"] = _data_hash

    _PCFG = {'displayModeBar': False, 'showTips': False}

    left, mid, right = st.columns([0.34, 0.33, 0.33], gap="medium")
    with left:
        st.plotly_chart(_figs["bar1"], width='stretch', config=_PCFG)
        st.plotly_chart(_figs["bar2"], width='stretch', config=_PCFG)
    with mid:
        st.plotly_chart(_figs["line_wd"], width='stretch', config=_PCFG)
        st.plotly_chart(_figs["line_nd"], width='stretch', config=_PCFG)
    with right:
        st.plotly_chart(_figs["line_price"], width='stretch', config=_PCFG)
        st.plotly_chart(_figs["line_power"], width='stretch', config=_PCFG)
        st.markdown("<p style='font-size:11px;color:#E53935;font-style:italic;margin-top:4px'>*单点卖力=销售额份额/动销铺货率</p>", unsafe_allow_html=True)



# ====================== Part B render_sku_analysis() ======================
def render_sku_analysis(selected_cat, selected_month, display_months):
    config = SA_CATEGORY_CONFIG[selected_cat]
    ytd_label, ly_label, l3m_label, yy, lyy = period_labels(selected_month)

    render_conclusion(f"sa_{selected_cat}", selected_month)

    row_keys_json = json.dumps(config["rows"])
    months_json = json.dumps(display_months)

    with st.spinner("正在加载图表..."):
        metric_df = build_metrics_cached(config["cat"], row_keys_json, months_json)
        st.markdown(f"<h3 style='text-align:center;margin:12px 0 18px;color:#111'>{TITLE_MAP.get(selected_cat, selected_cat)}</h3>", unsafe_allow_html=True)
        render_charts(metric_df, selected_cat)



# ====================== 主入口：顶部标题 + 双 Tab 导航 ======================
# 动态计算最新月份标签
_latest_month_a = ind_months[-1] if ind_months else all_months[-1]
_latest_label_a = ym_lab(_latest_month_a)

# 顶部主标题（使用最新月份）
st.markdown(f"""
<div class="main-header">
    <span>{_latest_label_a} 线下药店市场监测报告</span>
    <span class="badge">中康全国零售药店数据</span>
</div>
""", unsafe_allow_html=True)


# Tab 导航
tab_a, tab_b = st.tabs(["全国药店VDS市场表现", "重点品类汤臣市场表现"])

# ====================== Tab A: 全国药店VDS市场表现 ======================
with tab_a:
    # 统一时间选择器（控制整个 Tab A 页面）
    st.markdown('<div class="time-selector-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="time-selector-label"><span class="dot"></span>时间范围选择</div>', unsafe_allow_html=True)
    tc1, tc2 = st.columns([0.25, 0.75], gap="small")
    with tc1:
        sel_ym_a = st.selectbox("统计截止月份", options=ind_months, index=len(ind_months) - 1, label_visibility="collapsed", key="tab_a_month")
    with tc2:
        # 默认从25M1开始到最新月份
        _target_left_a = "202501"
        di_a = 0
        for _i, _m in enumerate(ind_months):
            if _m >= _target_left_a:
                di_a = _i
                break
        sl_l_a, sl_r_a = st.select_slider("月度数据范围", options=YM_LABS, value=(YM_LABS[di_a], YM_LABS[-1]), label_visibility="collapsed", key="tab_a_range")
        si_a = YM_LABS.index(sl_l_a)
        ei_a = YM_LABS.index(sl_r_a)
        SEL_M_A = ind_months[si_a:ei_a + 1]
    st.markdown('</div>', unsafe_allow_html=True)

    # 使用统一时间选择渲染四个页面
    page1(sel_ym_a, SEL_M_A)
    page2(sel_ym_a, SEL_M_A)
    page3(sel_ym_a, SEL_M_A)
    page4(sel_ym_a)

# ====================== Tab B: 重点品类汤臣市场表现 ======================
with tab_b:
    # Part B 主标题
    st.markdown("""
    <div class="partb-header">
        <span>重点品类汤臣市场表现</span>
        <span class="sub">品类概览 + 品牌竞争 + SKU/品线分析</span>
    </div>
    """, unsafe_allow_html=True)

    # 月份 + 范围选择器（置于品类选择器上方）
    st.markdown('<div class="partb-filter">', unsafe_allow_html=True)
    cf1, cf2 = st.columns([0.28, 0.72], gap="small")
    with cf1:
        selected_month = st.selectbox("选择报告月份", options=all_months, index=len(all_months) - 1, label_visibility="collapsed")
    with cf2:
        # 默认从25M1开始到最新月份
        _target_left = "202501"
        default_left = 0
        for _i, _m in enumerate(all_months):
            if _m >= _target_left:
                default_left = _i
                break
        ym_labels_b = [ym_lab(m) for m in all_months]
        sl_l, sl_r = st.select_slider("月份滚动范围", options=ym_labels_b, value=(ym_labels_b[default_left], ym_labels_b[-1]), label_visibility="collapsed")
        si = ym_labels_b.index(sl_l)
        ei = ym_labels_b.index(sl_r)
        display_months = all_months[si:ei + 1]
    st.markdown('</div>', unsafe_allow_html=True)

    # 品类选择器
    if "selected_cat" not in st.session_state:
        st.session_state.selected_cat = list(FP_CATEGORY_CONFIG.keys())[0]

    st.markdown('<div class="cat-selector-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="cat-selector-label">选择品类</div>', unsafe_allow_html=True)
    cat_names = list(FP_CATEGORY_CONFIG.keys())
    btn_cols = st.columns(len(cat_names))
    for i, cat in enumerate(cat_names):
        with btn_cols[i]:
            is_sel = (st.session_state.selected_cat == cat)
            if st.button(cat, key=f"cat_btn_{i}", type="primary" if is_sel else "secondary", width='stretch'):
                st.session_state.selected_cat = cat
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    selected_cat = st.session_state.selected_cat

    # 导出完整报告模式：Tab B 一次性渲染全部品类（每个品类含 品类概览/品牌竞争/SKU分析 三段）
    _SECTION1 = '<div class="section-header"><span class="num">1</span><span>品类概览</span></div>'
    _SECTION2 = '<div class="section-header"><span class="num">2</span><span>品牌竞争分析</span></div>'
    _SECTION3 = '<div class="section-header"><span class="num">3</span><span>SKU/品线分析</span></div>'

    if st.session_state.get("exp_all_cat", False):
        for _ci, _cat in enumerate(FP_CATEGORY_CONFIG.keys()):
            if _ci > 0:
                st.markdown('<div class="cat-export-break"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="cat-export-title">▍品类：{_cat}</div>', unsafe_allow_html=True)
            st.markdown(_SECTION1, unsafe_allow_html=True)
            render_first_page(_cat, selected_month, display_months)
            st.markdown(_SECTION2, unsafe_allow_html=True)
            render_brand_analysis(_cat, selected_month, display_months)
            st.markdown(_SECTION3, unsafe_allow_html=True)
            render_sku_analysis(_cat, selected_month, display_months)
    else:
        # ---- Section 一：品类概览 ----
        st.markdown(_SECTION1, unsafe_allow_html=True)
        render_first_page(selected_cat, selected_month, display_months)

        # ---- Section 二：品牌竞争分析 ----
        st.markdown(_SECTION2, unsafe_allow_html=True)
        render_brand_analysis(selected_cat, selected_month, display_months)

        # ---- Section 三：SKU/品线分析 ----
        st.markdown(_SECTION3, unsafe_allow_html=True)
        render_sku_analysis(selected_cat, selected_month, display_months)

# ===== 导出按钮移至页面最底部 =====
# ===== 导出 PDF 按钮（超长单页、不分页） =====
col_pdf1, col_pdf2, col_pdf3 = st.columns([1, 2, 1])
with col_pdf2:
    components.html(r"""
    <div style="text-align:center;">
        <button id="__longpdf_btn" type="button" style="
            background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%);
            color: white; border: none; padding: 9px 26px;
            border-radius: 8px; font-size: 14px; font-weight: 700;
            cursor: pointer; font-family: 'Microsoft YaHei', Arial, sans-serif;
        ">📄 导出当前页为 PDF（超长单页）</button>
        <p id="__longpdf_tip" style="font-size:11px;color:#999;margin-top:5px;margin-bottom:0;line-height:1.5;">
            自动滚动加载后生成单页长 PDF；打印框中目标选「另存为 PDF」，勾选「背景图形」，其余保持默认
        </p>
    </div>
    <script>
    (function () {
        const btn = document.getElementById('__longpdf_btn');
        const tip = document.getElementById('__longpdf_tip');
        const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

        btn.addEventListener('click', async function () {
            const win = window.parent;
            const doc = win.document;
            const oldHtml = btn.innerHTML;
            btn.disabled = true;
            btn.style.opacity = '0.65';
            btn.innerHTML = '正在生成，请稍候…';

            const HIDE = '[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stStatusWidget"],'
                + ' footer, #stBottom, .stDeployButton, [data-testid="stSidebarCollapsedControl"],'
                + ' [data-testid="stSidebar"], iframe[title="st.iframe"]';
            const OPEN = '[data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp,'
                + ' main, section, [data-testid="stMainBlockContainer"], [data-testid="stVerticalBlock"]';

            const fixedHidden = [];
            const styleBackups = [];
            const ruleBackups = [];
            let injected = null;
            let finished = false;

            function restore() {
                if (finished) return;
                finished = true;
                try {
                    if (injected && injected.parentNode) injected.parentNode.removeChild(injected);
                    fixedHidden.forEach(([el, d]) => { el.style.display = d; el.removeAttribute('data-longpdf-hidden'); });
                    styleBackups.forEach(([el, css]) => { el.textContent = css; el.removeAttribute('data-longpdf-backup'); });
                    ruleBackups.forEach(([ss, idx, css]) => { try { ss.insertRule(css, idx); } catch (e) {} });
                    win.scrollTo(0, 0);
                } catch (e) {}
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.innerHTML = oldHtml;
            }

            try {
                // 1) 滚动到底，触发懒加载图表
                await new Promise((resolve) => {
                    let prev = -1, stable = 0;
                    const t = setInterval(() => {
                        win.scrollTo(0, doc.body.scrollHeight);
                        const h = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
                        if (h === prev) { if (++stable >= 4) { clearInterval(t); resolve(); } }
                        else { stable = 0; prev = h; }
                    }, 500);
                });
                win.scrollTo(0, 0);
                await sleep(1000);

                // 2) 注入展开样式（屏幕态先用于测量真实高度）
                injected = doc.createElement('style');
                injected.id = '__longpdf_style__';
                injected.textContent =
                    'html, body { height: auto !important; overflow: visible !important; }'
                    + OPEN + ' { height: auto !important; min-height: 0 !important; overflow: visible !important; }'
                    + HIDE + ' { display: none !important; }';
                doc.head.appendChild(injected);

                // 3) 隐藏 fixed/sticky 悬浮元素（避免重复下标）
                doc.querySelectorAll('body *').forEach((el) => {
                    const s = win.getComputedStyle(el);
                    if (s.position === 'fixed' || s.position === 'sticky') {
                        fixedHidden.push([el, el.style.display]);
                        el.setAttribute('data-longpdf-hidden', '1');
                        el.style.display = 'none';
                    }
                });

                // 4) Plotly 图表按当前容器宽度重绘，防止右侧月份被裁
                try {
                    doc.querySelectorAll('.js-plotly-plot').forEach((el) => {
                        if (win.Plotly) { try { win.Plotly.Plots.resize(el); } catch (e) {} }
                    });
                    win.dispatchEvent(new win.Event('resize'));
                } catch (e) {}
                await sleep(1200);

                // 5) 测量完整内容宽高
                const W = doc.documentElement.clientWidth || win.innerWidth;
                const H = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight,
                                   doc.body.offsetHeight, doc.documentElement.offsetHeight);

                // 6) 注入超长单页 @page：纸张高度 = 内容真实高度 + 少量余量（刚好 1 页，不放大）
                // 关键：浏览器(Chrome/Edge)对单页纸张高度有硬上限（约 16384px，部分版本 ~18000px）。
                // 纸张高度一旦超过上限会被浏览器钳制并强制分页。因此纸张只取「内容高 + 余量」(≈1 倍)，
                // 绝不 ×3 —— ×3 会把纸张顶过上限，正是“中间分页”的根因。PH 再上限到 MAX_PH 兜底。
                const PW = W, MAX_PH = 16384, SLACK = 24;
                const calcPH = (h) => Math.min(MAX_PH, Math.floor(h + SLACK));
                const printCss = (ph) =>
                    '@page :first { size: ' + PW + 'px ' + ph + 'px; margin: 0; }'
                    + '@page { size: ' + PW + 'px ' + ph + 'px; margin: 0; }'
                    + 'html, body { width: ' + PW + 'px !important; height: auto !important; overflow: visible !important; background: #ffffff !important; }'
                    + OPEN + ' { height: auto !important; min-height: 0 !important; overflow: visible !important; position: static !important; }'
                    + HIDE + ' { display: none !important; }'
                    + '* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }'
                    + '.js-plotly-plot, table, .dt, .metric-table, .brand-table, .main-header, .otc-vds-box, .stDataFrame, div[data-testid="stVerticalBlock"] > div { break-inside: avoid !important; page-break-inside: avoid !important; }';
                let PH = calcPH(H);
                Array.from(doc.styleSheets).forEach((ss) => {
                    let rules;
                    try { rules = ss.cssRules; } catch (e) { return; }
                    for (let i = rules.length - 1; i >= 0; i--) {
                        try {
                            if (rules[i].type === CSSRule.PAGE_RULE) {
                                ruleBackups.push([ss, i, rules[i].cssText]);
                                ss.deleteRule(i);
                            }
                        } catch (e) {}
                    }
                });
                doc.querySelectorAll('style').forEach((el) => {
                    if (el !== injected && /@page\b/.test(el.textContent)) {
                        styleBackups.push([el, el.textContent]);
                        el.setAttribute('data-longpdf-backup', '1');
                        el.textContent = el.textContent.replace(/@page[^{]*\{[^}]*\}/g, '');
                    }
                });
                injected.textContent = printCss(PH);
                await sleep(400);

                // 6.5) 打印样式注入后复测高度：若内容因样式变化长高，按新高度重算纸张，
                // 防止测量误差导致内容尾部溢出到第 2 页
                const H2 = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight,
                                    doc.body.offsetHeight, doc.documentElement.offsetHeight);
                if (H2 > H + 4) {
                    PH = calcPH(H2);
                    injected.textContent = printCss(PH);
                    await sleep(300);
                }

                // 7) 调起打印；关闭打印框后恢复页面
                win.addEventListener('afterprint', restore);
                win.print();
                setTimeout(restore, 60000);  // 兜底：个别浏览器不触发 afterprint
            } catch (e) {
                tip.textContent = '生成失败：' + e + '；可改用浏览器菜单「打印 → 另存为 PDF」';
                restore();
            }
        });
    })();
    </script>
    """, height=95)
# ===== 导出 PDF 按钮结束 =====

# ===== 导出完整网页 PDF 按钮（含全部 Tab） =====
# 勾选后 Tab B 会一次性渲染全部 8 个品类（用于“导出整个网页”时拿到完整内容）；取消则仅当前选中品类，保持页面轻量
exp_all_cat = st.checkbox(
    "导出完整报告时，Tab B 包含全部 8 个品类（取消则仅当前选中品类，页面更轻量）",
    value=False, key="exp_all_cat",
)

col_all1, col_all2, col_all3 = st.columns([1, 2, 1])
with col_all2:
    components.html(r"""
    <div style="text-align:center;">
        <button id="__allpdf_btn" type="button" style="
            background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%);
            color: white; border: none; padding: 9px 22px;
            border-radius: 8px; font-size: 14px; font-weight: 700;
            cursor: pointer; font-family: 'Microsoft YaHei', Arial, sans-serif;
        ">📑 导出整个网页为 PDF（全部 Tab）</button>
        <p id="__allpdf_tip" style="font-size:11px;color:#999;margin-top:6px;margin-bottom:0;line-height:1.5;">
            会把 Tab A 与 Tab B 两个标签页同时收进一份 PDF；打印框中目标选「另存为 PDF」，勾选「背景图形」。<br>
            若已勾选上方“包含全部品类”，Tab B 会包含全部 8 个品类的完整内容。
        </p>
    </div>
    <script>
    (function () {
        const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
        const HIDE = '[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stStatusWidget"],'
            + ' footer, #stBottom, .stDeployButton, [data-testid="stSidebarCollapsedControl"],'
            + ' [data-testid="stSidebar"], iframe[title="st.iframe"], [role="tablist"]';
        const OPEN = '[data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp,'
            + ' main, section, [data-testid="stMainBlockContainer"], [data-testid="stVerticalBlock"]';

        function scrollToLoad(win, doc) {
            return new Promise((resolve) => {
                let prev = -1, stable = 0;
                const t = setInterval(() => {
                    win.scrollTo(0, doc.body.scrollHeight);
                    const h = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
                    if (h === prev) { if (++stable >= 4) { clearInterval(t); resolve(); } }
                    else { stable = 0; prev = h; }
                }, 500);
            });
        }
        function resizePlots(win, doc) {
            try {
                doc.querySelectorAll('.js-plotly-plot').forEach((el) => {
                    if (win.Plotly) { try { win.Plotly.Plots.resize(el); } catch (e) {} }
                });
                win.dispatchEvent(new win.Event('resize'));
            } catch (e) {}
        }
        // 展开所有 Tab 面板（Streamlit 默认只把激活的 Tab 留在可视 DOM，其余加 hidden）
        function revealAllTabs(doc) {
            const backups = [];
            const panels = doc.querySelectorAll('[role="tabpanel"]');
            panels.forEach((p, i) => {
                backups.push([p, p.hidden, p.getAttribute('style')]);
                p.hidden = false;
                p.style.display = 'block !important';
                p.style.visibility = 'visible';
                p.style.position = 'static';
                p.style.width = '100%';
                if (i > 0) p.style.pageBreakBefore = 'always';
            });
            const tl = doc.querySelector('[role="tablist"]');
            if (tl) { backups.push([tl, null, tl.getAttribute('style')]); tl.style.display = 'none'; }
            return backups;
        }
        function restoreTabs(backups) {
            if (!backups) return;
            backups.forEach(([el, wasHidden, sty]) => {
                if (wasHidden !== null) el.hidden = wasHidden;
                el.setAttribute('style', sty || '');
            });
        }

        const btn = document.getElementById('__allpdf_btn');
        const tip = document.getElementById('__allpdf_tip');
        btn.addEventListener('click', async function () {
            const win = window.parent;
            const doc = win.document;
            const oldHtml = btn.innerHTML;
            btn.disabled = true;
            btn.style.opacity = '0.65';
            btn.innerHTML = '正在生成，请稍候…';

            const fixedHidden = [];
            const styleBackups = [];
            const ruleBackups = [];
            let injected = null;
            let finished = false;
            let tabBackups = null;

            function restore() {
                if (finished) return;
                finished = true;
                try {
                    if (injected && injected.parentNode) injected.parentNode.removeChild(injected);
                    fixedHidden.forEach(([el, d]) => { el.style.display = d; el.removeAttribute('data-longpdf-hidden'); });
                    styleBackups.forEach(([el, css]) => { el.textContent = css; el.removeAttribute('data-longpdf-backup'); });
                    ruleBackups.forEach(([ss, idx, css]) => { try { ss.insertRule(css, idx); } catch (e) {} });
                    restoreTabs(tabBackups);
                    win.scrollTo(0, 0);
                } catch (e) {}
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.innerHTML = oldHtml;
            }

            try {
                // 0) 展开所有 Tab 面板
                tabBackups = revealAllTabs(doc);

                // 1) 滚动到底，触发懒加载图表
                await scrollToLoad(win, doc);
                win.scrollTo(0, 0);
                await sleep(1000);

                // 2) 注入展开样式（屏幕态先用于测量真实高度）
                injected = doc.createElement('style');
                injected.id = '__allpdf_style__';
                injected.textContent =
                    'html, body { height: auto !important; overflow: visible !important; }'
                    + OPEN + ' { height: auto !important; min-height: 0 !important; overflow: visible !important; }'
                    + HIDE + ' { display: none !important; }';
                doc.head.appendChild(injected);

                // 3) 隐藏 fixed/sticky 悬浮元素
                doc.querySelectorAll('body *').forEach((el) => {
                    const s = win.getComputedStyle(el);
                    if (s.position === 'fixed' || s.position === 'sticky') {
                        fixedHidden.push([el, el.style.display]);
                        el.setAttribute('data-longpdf-hidden', '1');
                        el.style.display = 'none';
                    }
                });

                // 4) Plotly 图表按当前容器宽度重绘
                resizePlots(win, doc);
                await sleep(1200);

                // 4.5) 刚展开的 Tab B 可能还没完全渲染，再滚动 + 重绘一次
                await scrollToLoad(win, doc);
                win.scrollTo(0, 0);
                resizePlots(win, doc);
                await sleep(1000);

                // 5) 测量完整内容宽高
                const W = doc.documentElement.clientWidth || win.innerWidth;
                const H = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight,
                                   doc.body.offsetHeight, doc.documentElement.offsetHeight);

                // 6) 注入 @page：纸张宽 = 内容宽；高 = 内容高 + 余量（贴近 1 倍单页优先；
                //    超过浏览器单页硬上限 16384px 时允许自然分页，图表不撕开）
                const PW = W, MAX_PH = 16384, SLACK = 24;
                const calcPH = (h) => Math.min(MAX_PH, Math.floor(h + SLACK));
                const printCss = (ph) =>
                    '@page :first { size: ' + PW + 'px ' + ph + 'px; margin: 0; }'
                    + '@page { size: ' + PW + 'px ' + ph + 'px; margin: 0; }'
                    + 'html, body { width: ' + PW + 'px !important; height: auto !important; overflow: visible !important; background: #ffffff !important; }'
                    + OPEN + ' { height: auto !important; min-height: 0 !important; overflow: visible !important; position: static !important; }'
                    + HIDE + ' { display: none !important; }'
                    + '* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }'
                    + '.js-plotly-plot, table, .dt, .metric-table, .brand-table, .main-header, .otc-vds-box, .stDataFrame, div[data-testid="stVerticalBlock"] > div { break-inside: avoid !important; page-break-inside: avoid !important; }';
                let PH = calcPH(H);
                Array.from(doc.styleSheets).forEach((ss) => {
                    let rules;
                    try { rules = ss.cssRules; } catch (e) { return; }
                    for (let i = rules.length - 1; i >= 0; i--) {
                        try {
                            if (rules[i].type === CSSRule.PAGE_RULE) {
                                ruleBackups.push([ss, i, rules[i].cssText]);
                                ss.deleteRule(i);
                            }
                        } catch (e) {}
                    }
                });
                doc.querySelectorAll('style').forEach((el) => {
                    if (el !== injected && /@page\b/.test(el.textContent)) {
                        styleBackups.push([el, el.textContent]);
                        el.setAttribute('data-longpdf-backup', '1');
                        el.textContent = el.textContent.replace(/@page[^{]*\{[^}]*\}/g, '');
                    }
                });
                injected.textContent = printCss(PH);
                await sleep(400);

                // 6.5) 复测高度，防样式变化导致尾部溢出
                const H2 = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight,
                                    doc.body.offsetHeight, doc.documentElement.offsetHeight);
                if (H2 > H + 4) {
                    PH = calcPH(H2);
                    injected.textContent = printCss(PH);
                    await sleep(300);
                }

                // 7) 调起打印；关闭打印框后恢复页面
                win.addEventListener('afterprint', restore);
                win.print();
                setTimeout(restore, 60000);
            } catch (e) {
                tip.textContent = '生成失败：' + e + '；可改用浏览器菜单「打印 → 另存为 PDF」';
                restore();
            }
        });
    })();
    </script>
    """, height=120)
# ===== 导出完整网页 PDF 按钮结束 =====
