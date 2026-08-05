# ============================================================
# 市场分析综合仪表盘 - 合并版
# Tab 1: 全国药店VDS市场表现 (page1-page4)
# Tab 2: 重点品类汤臣市场表现 (render_first_page/render_brand_analysis/render_sku_analysis)
# ============================================================

# ====================== 1. Imports ======================
import streamlit as st
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import plotly.graph_objects as go
from datetime import datetime
import calendar
import json

st.set_page_config(page_title="市场分析综合仪表盘", layout="wide")

# ====================== 2. Constants ======================
# --- 来自 merged_dashboard 的常量 ---
SALES_COL = "销售额('000 RMB)"
QTY_COL = "销售量-Pack('00))"
DIST_COL = "加权铺货率"

SKU_COLS = ["year_month", "品类", "品牌", "品牌产品", "产品包装", "品名(含属性)", SALES_COL, QTY_COL, DIST_COL]
BRAND_COLS = ["year_month", "品类", "品牌", "品牌产品", SALES_COL, QTY_COL, DIST_COL]
DIST_COLS = ["year_month", "品牌_NEW", DIST_COL, SALES_COL]

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

# ====================== 3. Engine (SQLite) ======================
import os
import gzip
import shutil
import sqlite3

_DB_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_DB_DIR, "dashboard_data.db")
_DB_GZ_PATH = os.path.join(_DB_DIR, "dashboard_data.db.gz")


def _verify_db_integrity(db_path):
    """检查 SQLite 数据库完整性，返回 True/False。"""
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute("PRAGMA integrity_check;")
        result = cur.fetchone()[0]
        conn.close()
        return result == "ok"
    except Exception:
        return False


def _decompress_db():
    """从 gz 解压 db 文件。"""
    with gzip.open(_DB_GZ_PATH, "rb") as f_in, open(_DB_PATH, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


def _verify_gz_integrity():
    """校验 gz 文件完整性（通过尝试解压前1MB）。"""
    if not os.path.exists(_DB_GZ_PATH):
        return False
    try:
        with gzip.open(_DB_GZ_PATH, "rb") as f:
            f.read(1024 * 1024)
        return True
    except Exception:
        return False


def _ensure_db():
    """
    确保 dashboard_data.db 存在且完整。
    - 不存在则从 gz 解压
    - 存在但损坏则删除重新解压
    - 重新解压后仍损坏则报错
    """
    # 校验 gz 文件
    if os.path.exists(_DB_GZ_PATH) and not _verify_gz_integrity():
        st.error(
            "dashboard_data.db.gz 文件已损坏（可能是 Git 传输导致）。\n\n"
            "请在本地运行 `python update_cloud.py` 重新生成并推送数据。"
        )
        st.stop()

    # 情况1：db 不存在，从 gz 解压
    if not os.path.exists(_DB_PATH):
        if not os.path.exists(_DB_GZ_PATH):
            st.error("数据库文件缺失：dashboard_data.db 和 dashboard_data.db.gz 均不存在。")
            st.stop()
        with st.spinner("正在解压数据库 (首次启动约需30秒)..."):
            _decompress_db()

    # 情况2：db 存在，校验完整性
    if not _verify_db_integrity(_DB_PATH):
        st.warning("数据库文件损坏，正在从 gz 重新解压 ...")
        try:
            os.remove(_DB_PATH)
        except Exception:
            pass
        if os.path.exists(_DB_GZ_PATH):
            with st.spinner("重新解压数据库中 ..."):
                _decompress_db()
            if not _verify_db_integrity(_DB_PATH):
                st.error(
                    "数据库重新解压后仍然损坏。\n\n"
                    "可能原因：\n"
                    "1. dashboard_data.db.gz 文件在 Git 传输中损坏\n"
                    "2. 磁盘空间不足\n\n"
                    "解决方法：在本地运行 `python update_cloud.py` 重新推送数据"
                )
                st.stop()
        else:
            st.error("数据库损坏且 gz 备份不存在，无法恢复。")
            st.stop()


# 启动时确保数据库可用
_ensure_db()

engine = create_engine(f"sqlite:///{_DB_PATH}", echo=False)

# ====================== 4. Data Loading ======================
@st.cache_data(ttl=1800, show_spinner=False)
def load_sku_df():
    """sku_df：全量 sku 表，三个 section 共享。"""
    try:
        df = pd.read_sql(text("SELECT * FROM sku;"), con=engine)
    except Exception as e:
        st.error(f"读取 sku 表失败：{e}")
        st.cache_data.clear()
        try:
            df = pd.read_sql(text("SELECT * FROM sku;"), con=engine)
        except Exception as e2:
            st.error(
                f"重试仍然失败：{e2}\n\n"
                "数据库可能已损坏。请删除 dashboard_data.db 后重启，"
                "或在本地运行 `python update_cloud.py` 重新推送数据。"
            )
            st.stop()
    df.columns = [str(c).strip() for c in df.columns]
    for col in [SALES_COL, QTY_COL, DIST_COL]:
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
        raw_conn = engine.raw_connection()
        if table_name == "brand":
            cols = BRAND_COLS
        elif table_name == "brand_distribution_rate":
            cols = DIST_COLS
        else:
            cols = None
        if cols:
            col_sql = ", ".join(f"`{c}`" for c in cols)
            sql = f"SELECT {col_sql} FROM `{table_name}`"
        else:
            sql = f"SELECT * FROM `{table_name}`"
        df = pd.read_sql(sql, con=raw_conn)
        raw_conn.close()
    except Exception as e:
        st.error(f"读取 test.{table_name} 失败：{e}")
        st.stop()
    df.columns = [str(c).strip() for c in df.columns]
    if "year_month" in df.columns:
        df["year_month"] = df["year_month"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    for col in [SALES_COL, QTY_COL, DIST_COL]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def load_industry():
    """industry 表，Part A (page1-page4) 专用。"""
    try:
        df = pd.read_sql(text("SELECT * FROM `industry`;"), con=engine)
    except Exception as e:
        st.error(f"读取 industry 表失败：{e}")
        st.stop()
    if SALES_COL in df.columns:
        df[SALES_COL] = pd.to_numeric(df[SALES_COL], errors="coerce")
    if "year_month" in df.columns:
        df["year_month"] = df["year_month"].astype(str)
    if "销售量-Pack('00))" in df.columns:
        df["销售量-Pack('00))"] = pd.to_numeric(df["销售量-Pack('00))"], errors="coerce")
    df["year"] = df["year_month"].str[:4].astype(int)
    df["mon"] = df["year_month"].str[4:].astype(int)
    df["ym_id"] = df["year"] * 12 + df["mon"]
    return df


# 模块级加载（带容错）
try:
    sku_df = load_sku_df()
    brand_df = load_table("brand")
    dist_df = load_table("brand_distribution_rate")
    df_ind = load_industry()
except Exception as e:
    st.error(
        f"数据加载失败：{e}\n\n"
        "请尝试刷新页面。如持续失败，请在本地运行 `python update_cloud.py` 重新推送数据。"
    )
    st.stop()

if df_ind.empty:
    st.error("industry 表中没有数据，请检查数据源。")
    st.stop()

# ====================== 5. Shared Utils ======================
def ym_lab(ym):
    return f"{str(ym)[2:4]}M{int(str(ym)[4:])}"


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
    html, body, [class*="css"] { font-size: 14px !important; }
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

    /* 口径栏 code 样式 (Part A) */
    .ibar code {
        background: rgba(27,79,142,0.08); color: #1B4F8E;
        padding: 1px 5px; border-radius: 3px; font-size: 11px;
    }

    /* 统一表格 dt (Part A) */
    .dt {
        width: 100%; border-collapse: collapse; font-size: 13px;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .dt th, .dt td { border: 1px solid #E4E9F0; padding: 8px 10px; text-align: center; vertical-align: middle; }
    .dt th { background: #EEF2FA; font-weight: 600; color: #1A1A2E; font-size: 12px; }
    .dt td:first-child { text-align: left; font-weight: 600; }
    .dt tr:hover td { background: #F0F4FF; }

    /* page2 专用表格 */
    .dt-p2 {
        width: 100%; border-collapse: collapse; font-size: 13px;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        table-layout: fixed;
        height: 400px;
    }
    .dt-p2 tr { height: calc(400px / 6); }
    .dt-p2 th { border: 1px solid #E4E9F0; background: #EEF2FA; font-weight: 600; color: #1A1A2E; font-size: 11px; padding: 2px 4px; line-height: 1; text-align: center; vertical-align: middle; }
    .dt-p2 td { border: 1px solid #E4E9F0; padding: 0 8px; text-align: center; vertical-align: middle; font-size: 12px; }
    .dt-p2 td:first-child { text-align: left; font-weight: 600; }
    .dt-p2 tbody tr:hover td { background: #F0F4FF; }

    /* page3 专用表格 */
    .dt-p3 {
        width: 100%; border-collapse: collapse; font-size: 12px;
        border-radius: 8px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .dt-p3 th, .dt-p3 td { border: 1px solid #E4E9F0; padding: 5px 3px; text-align: center; vertical-align: middle; }
    .dt-p3 th { background: #EEF2FA; font-weight: 600; color: #1A1A2E; font-size: 11px; }
    .dt-p3 td:first-child { text-align: left; font-weight: 600; padding-left: 10px; }
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
        font-size: 12px;
        font-family: "Microsoft YaHei", Arial, sans-serif;
        table-layout: auto;
        white-space: nowrap;
        margin: 0 auto;
    }
    .dashboard-table th, .dashboard-table td {
        border: 1px solid #D9D9D9;
        padding: 5px 7px;
        text-align: center;
        vertical-align: middle;
    }
    .top-header th { color: white; font-weight: 600; padding: 6px 5px; line-height: 1.3; font-size: 12px; }
    .cat-header { background: #2E5E3A; }
    .sales-header-a { background: #6B5B2E; }
    .growth-header-a { background: #6B5B2E; }
    .brand-header { background: #1B4F8E; }
    .sales-header-b { background: #1B4F8E; }
    .growth-header-b { background: #1B4F8E; }
    .share-header { background: #1B4F8E; }
    .sub-header th { color: white; font-weight: 600; font-size: 11px; padding: 4px 5px; }
    .dashboard-table tbody tr:nth-child(odd) { background: #FAFBFC; }
    .dashboard-table tbody tr:nth-child(even) { background: #FFFFFF; }
    .dashboard-table tbody tr:hover { background: #F0F4FF; }
    .cat-name { text-align: left; font-weight: 600; color: #2E5E3A; padding-left: 10px !important; width: 120px; }
    .cat-name .sub { font-size: 10px; color: #888; font-weight: normal; margin-left: 3px; }
    .brand-name { font-weight: 600; color: #1B4F8E; width: 100px; }
    .num { font-variant-numeric: tabular-nums; width: 65px; position: relative; }
    .sales-bold { font-weight: 700; }
    .bar-cell { position: relative; overflow: hidden; }
    .bar-bg { position: absolute; left: 0; top: 0; bottom: 0; z-index: 1; opacity: 0.75; }
    .bar-text { position: relative; z-index: 2; font-weight: 700; }
    .share-change { display: table-cell; }
    .share-change span { display: inline-block; vertical-align: middle; }

    .footer-note {
        margin-top: 10px;
        font-size: 11px;
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
    .note-bar { background: #EBF0FA; border-left: 4px solid #1B4F8E; border-radius: 0 8px 8px 0; padding: 8px 13px; margin: 8px 0 12px; color: #334155; font-size: 12px; line-height: 1.55; }
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
        background: linear-gradient(135deg, #1B4F8E, #163a70);
        color: white;
        border-radius: 0 0 8px 8px;
        padding: 12px 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .phdr h2 { margin: 0; font-size: 17px; color: white; }
    .fcard {
        background: #fff;
        border: 1px solid #DCE3EF;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .frow { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
    .ibar {
        background: #EBF0FA;
        border-left: 4px solid #1B4F8E;
        border-radius: 0 6px 6px 0;
        padding: 8px 14px;
        margin: 8px 0 12px;
        font-size: 12px;
        color: #334155;
        line-height: 1.5;
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
    .metric-table th { line-height: 1.5; background: #EEF2FA; font-weight: 700; color: #1A1A2E; font-size: 16px; padding: 12px 6px; }
    .metric-table td { line-height: 1.5; padding: 28px 6px; font-size: 17px; }
    .metric-table.compact td { line-height: 1.5; padding: 40px 6px; font-size: 18px; }
    .metric-table td:first-child { text-align: left; font-weight: 700; padding-left: 12px; min-width: 126px; }
    .metric-table .value { font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
    .metric-table tbody tr:hover td { background: #F0F4FF; }
    .metric-table .cat-h { background: #F7D794; color: #1A1A2E; }
    .metric-table .otc-h { background: #FFF3CD; color: #1A1A2E; }
    .metric-table .vds-h { background: #FFEBC1; color: #1A1A2E; }
    .metric-table .brand-h { background: #D6EAF8; color: #1A1A2E; }
    .left-content-wrap {
        height: 590px;
        display: flex;
        flex-direction: column;
    }
    .left-content-wrap .metric-table {
        flex: 1 1 auto;
        height: 100%;
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
        font-size: 15px;
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
        font-size: 12px;
    }
    .growth-table td:first-child { text-align: left; font-weight: 600; padding-left: 8px; width: 100px; }
    .growth-table tbody tr:hover td { background: #F0F4FF; }
    .neg { color: #E53935; }
    .pos10 { color: #00B050; }
    .caption { font-size: 11px; color: #666; margin-top: 10px; }
    div[data-testid="stPlotlyChart"] {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    /* brand_analysis 表格 */
    .brand-table { width: 100%; border-collapse: collapse; table-layout: fixed; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 5px rgba(0,0,0,0.08); font-size: 13px; }
    .brand-table th, .brand-table td { border: 1px solid #D6DDE8; padding: 6px 4px; text-align: center; vertical-align: middle !important; white-space: nowrap; line-height: 1.35; height: 29px; }
    .brand-table th { background: #B0B0B0; color: #111827; font-weight: 800; }
    .brand-table .brand-col { width: 88px; font-weight: 800; }
    .brand-table .group-head { background: #B0B0B0; font-size: 13px; }
    .brand-table .sub-head { background: #B0B0B0; font-size: 12px; }
    .brand-table .cat-row td { background: #F2F2F2; font-weight: 800; }
    .brand-table .affiliate-row td { background: #FFF2CC; }
    .brand-table .focus-row td { background: #FFFFFF; }
    .brand-table .share-growth-row td { background: #E2F0D9; }
    .brand-table .neg { color: #E53935; font-style: italic; font-weight: 800; }
    .brand-table .pos { color: #00A85A; font-style: italic; font-weight: 800; }
    .brand-table .plain { color: #111827; }
    .brand-table tr:hover td { background: #EEF4FF; }

    /* ====== Tab 导航美化 ====== */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 10px 10px 0 0 !important;
        border: 1px solid #D8E2F0 !important;
        border-bottom: none !important;
        background: linear-gradient(180deg, #F8FAFF, #EEF2FA) !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        color: #5B7A9E !important;
        padding: 0 28px !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: linear-gradient(180deg, #FFF8E8, #FFF1CC) !important;
        color: #9A5B00 !important;
        border-color: #F5A623 !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%) !important;
        color: white !important;
        border-color: #1B4F8E !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #F5A623 !important;
        height: 3px !important;
    }
    .stTabs [data-baseweb="tab-border"] {
        border: none !important;
    }

    /* ====== Part B 美化 ====== */
    /* 主标题（Part B 顶部） */
    .partb-header {
        background: linear-gradient(135deg, #1B4F8E 0%, #102F57 100%);
        color: white;
        padding: 14px 22px;
        border-radius: 10px;
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0.02em;
        margin-bottom: 14px;
        box-shadow: 0 3px 12px rgba(27,79,142,0.18);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .partb-header .sub { font-size: 12px; font-weight: 400; opacity: 0.85; }

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
        padding: 10px 20px;
        border-radius: 8px;
        font-size: 16px;
        font-weight: 700;
        margin: 22px 0 14px;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0 2px 8px rgba(27,79,142,0.12);
    }
    .section-header .num {
        background: #F5A623;
        color: white;
        border-radius: 50%;
        width: 28px;
        height: 28px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 800;
        flex-shrink: 0;
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

    /* ====== selectbox 美化 ====== */
    div[data-baseweb="select"] > div {
        border-radius: 8px !important;
        border-color: #B8D4F0 !important;
    }
    div[data-baseweb="select"] > div:hover {
        border-color: #F5A623 !important;
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
    c = "#E53935" if p < 0 else ("#2E7D32" if p > 10 else "#555")
    w = "600" if (p < 0 or p > 10) else "400"
    return f'<span style="color:{c};font-weight:{w}">{t}</span>'

# page2 工具函数
def total_vds_sales(df, months):
    mask = (df["品类"] == "VDS") & (df["year_month"].isin(months))
    return df.loc[mask, SALES_COL].sum()

def brand_sales(df, months, brand=None):
    mask = (df["品类"] == "VDS") & (df["year_month"].isin(months))
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
    if abs(v) < 0.1:
        s = f"{v:+.2f}"
    else:
        s = f"{v:+.1f}"
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
    df = df_ind if source == "industry" else sku_df
    mask = df["year_month"].isin(months)
    for k, v in filters.items():
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
    sl_l = ym_lab(SEL_M[0])
    sl_r = ym_lab(SEL_M[-1])
    st.markdown(f"""
    <div class="phdr">
        <h2>全国零售药店 — VDS+OTC 品类市场规模</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="ibar">
    <b>口径：</b>YTD=<code>{int(sel_ym[:4])}-01 ~ {sel_ym}</code>累计 &nbsp;|&nbsp;
    同比=(本期/去年同期)-1 &nbsp;|&nbsp;
    月度范围：<code>{sl_l} ~ {sl_r}</code>（{len(SEL_M)}个月）
    </div>
    """, unsafe_allow_html=True)

    sel_y = int(sel_ym[:4])
    sel_m = int(sel_ym[4:])
    ymid = sel_y * 12 + sel_m

    # 图例复选框
    lg1, lg2, _ = st.columns([2, 2, 8], gap="large")
    with lg1:
        _cb, _lab = st.columns([1, 3], gap="small")
        show_vds = _cb.checkbox("vds", value=True, label_visibility="collapsed", key="p1_vds")
        _lab.markdown(f'<div style="display:flex;align-items:center;gap:8px;height:32px;"><span style="width:14px;height:14px;border-radius:3px;background:{C_VDS};flex-shrink:0;"></span><span style="font-size:13px;color:{C_TXT};font-weight:500;">VDS</span></div>', unsafe_allow_html=True)
    with lg2:
        _cb, _lab = st.columns([1, 3], gap="small")
        show_otc = _cb.checkbox("otc", value=True, label_visibility="collapsed", key="p1_otc")
        _lab.markdown(f'<div style="display:flex;align-items:center;gap:8px;height:32px;"><span style="width:14px;height:14px;border-radius:3px;background:{C_OTC};flex-shrink:0;"></span><span style="font-size:13px;color:{C_TXT};font-weight:500;">OTC</span></div>', unsafe_allow_html=True)

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
    FZ = 13
    BW = 0.75
    BASE = dict(
        height=H,
        margin=dict(t=60, b=24, l=8, r=55),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(size=13, family="PingFang SC,Microsoft YaHei,sans-serif"),
        yaxis=dict(gridcolor="#EEF0F5", showticklabels=False, zeroline=False),
        legend=dict(orientation="v", yanchor="top", y=1.0, xanchor="left", x=1.0)
    )

    cL, cR = st.columns([0.47, 0.53], gap="medium")

    with cL:
        cc1, cc2, cc3 = st.columns(3, gap="small")
        with cc1:
            f1 = go.Figure()
            if show_otc:
                f1.add_bar(x=["LY", "YTD"], y=[low, cow], name="OTC",
                           marker_color=C_OTC, width=BW,
                           text=[fn(low), fn(cow)], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white"),
                           textangle=0, cliponaxis=False, legendrank=2)
            if show_vds:
                vds_base = [low, cow] if show_otc else [0, 0]
                f1.add_bar(x=["LY", "YTD"], y=[lvw, cvw], name="VDS",
                           marker_color=C_VDS, base=vds_base, width=BW,
                           text=[fn(lvw), fn(cvw)], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white"),
                           textangle=0, cliponaxis=False, legendrank=1)
            f1.update_layout(**BASE,
                title=dict(text="品类销售额<br><sup>(亿元)</sup>", font_size=13),
                barmode="stack", bargap=0.30, showlegend=False)
            st.plotly_chart(f1, use_container_width=True)

        with cc2:
            f2 = go.Figure()
            if show_otc:
                f2.add_bar(x=["LY", "YTD"], y=[lqow, cqow], name="OTC",
                           marker_color=C_OTC, width=BW,
                           text=[fn(lqow), fn(cqow)], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white"),
                           textangle=0, cliponaxis=False, legendrank=2)
            if show_vds:
                vds_base = [lqow, cqow] if show_otc else [0, 0]
                f2.add_bar(x=["LY", "YTD"], y=[lqvw, cqvw], name="VDS",
                           marker_color=C_VDS, base=vds_base, width=BW,
                           text=[fn(lqvw), fn(cqvw)], textposition="outside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color=C_TXT),
                           textangle=0, cliponaxis=False, legendrank=1)
            f2.update_layout(**BASE,
                title=dict(text="品类销售量<br><sup>(亿盒)</sup>", font_size=13),
                barmode="stack", bargap=0.30, showlegend=False)
            st.plotly_chart(f2, use_container_width=True)

        with cc3:
            f3 = go.Figure()
            if show_vds:
                f3.add_bar(x=["LY", "YTD"], y=[lpv, cpv], name="VDS",
                           marker_color=C_VDS, width=0.38,
                           text=[f"{lpv}", f"{cpv}"], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white"),
                           cliponaxis=False, legendrank=1)
            if show_otc:
                f3.add_bar(x=["LY", "YTD"], y=[lpo, cpo], name="OTC",
                           marker_color=C_OTC, width=0.38,
                           text=[f"{lpo}", f"{cpo}"], textposition="inside",
                           insidetextanchor="middle", textfont=dict(size=FZ, color="white"),
                           cliponaxis=False, legendrank=2)
            f3.update_layout(**BASE,
                title=dict(text="品类平均单价<br><sup>(元/盒)</sup>", font_size=13),
                barmode="group", bargap=0.30, bargroupgap=0.08, showlegend=False)
            st.plotly_chart(f3, use_container_width=True)

        st.markdown(f"<b class='chart-title'>YTD 同比增速</b>", unsafe_allow_html=True)
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
                        insidetextanchor="middle", textfont=dict(size=FZ, color="white")))
                if show_vds:
                    vds_base_m = mm["OTCc"] if show_otc else [0] * len(mm)
                    fm.add_trace(go.Bar(x=mm["lb"], y=mm["VDSc"], name="VDS",
                        marker_color=C_VDS, base=vds_base_m, width=BW, marker_line_width=0,
                        text=[fn(v) for v in mm["VDSc"]], textposition="inside",
                        insidetextanchor="middle", textfont=dict(size=FZ, color="white"),
                        textangle=0))
                fm.update_layout(**BASE, barmode="stack", bargap=0.15, showlegend=False,
                                 title=dict(text="品类销售额by月度<br><sup>(单位：亿元)</sup>", font_size=13),
                                 xaxis=dict(tickangle=-45, tickfont=dict(size=13)))
                st.plotly_chart(fm, use_container_width=True)

                st.markdown(f"<b class='chart-title'>月度同比明细</b>", unsafe_allow_html=True)
                mlst = mm["lb"].tolist()
                n_m = len(mlst)
                tfs = "12px" if n_m > 12 else "13px"
                tdp = "6px 8px" if n_m > 12 else "8px 10px"
                hdr = "".join(f"<th style='font-size:{tfs};padding:{tdp}'>{m}</th>" for m in mlst)
                vr = "".join(f"<td style='font-size:{tfs};padding:{tdp}'>{gh(v)}</td>" for v in mm["VG"])
                orr = "".join(f"<td style='font-size:{tfs};padding:{tdp}'>{gh(v)}</td>" for v in mm["OG"])
                trr = "".join(f"<td style='font-size:{tfs};padding:{tdp}'>{gh(v)}</td>" for v in mm["TG"])

                st.markdown(f"""
                <div style='overflow-x:auto'>
                <table class="dt" style='min-width:{max(n_m*48,300)}px'>
                <tr>{hdr}</tr>
                <tr>{vr}</tr>
                <tr>{orr}</tr>
                <tr style='background:#F5F7FF'>{trr}</tr>
                </table></div>""", unsafe_allow_html=True)
            else:
                st.warning(f"范围内无数据 ({sl_l} ~ {sl_r})")

    st.divider()
    st.caption("""数据来源：中康全国零售药店
*注：VDS+OTC包含蓝帽子产品、健康食品及相关OTC产品（不含纯治疗作用OTC药品如感冒、止咳等）""")

# ====================== Part A PAGE 2: VDS 品牌份额 ======================
def page2(sel_month, trend_months):
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

    st.markdown(f"""
    <div class="ibar">
    <b>口径：</b>YTD = {sel_year}年1-{sel_mon}月累计；YTD-LY = {sel_year-1}年同期；
    {sel_month[2:4]}M{sel_mon} = {sel_month}；环期 = {ring_month}；
    份额 = 品牌销售额 / VDS品类销售额 × 100；份额同比/环比 = (当期份额 - 对比期份额) × 100，保留一位小数。
    </div>
    """, unsafe_allow_html=True)

    vds_ytd_total = total_vds_sales(df_ind, ytd_months)
    vds_ly_total = total_vds_sales(df_ind, ly_ytd_months)
    vds_curr_total = total_vds_sales(df_ind, [sel_month])
    vds_ring_total = total_vds_sales(df_ind, [ring_month])

    brand_ytd = df_ind[(df_ind["品类"] == "VDS") & (df_ind["year_month"].isin(ytd_months)) &
                       (~df_ind["品牌"].str.contains("others|其他", case=False, na=False))].groupby("品牌")[SALES_COL].sum().sort_values(ascending=False)
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
                    x=["LY"], y=[m["LY份额"]], name=b,
                    marker_color=color_map[b], width=0.6,
                    text=[f"{m['LY份额']:.1f}"], textposition="inside",
                    insidetextanchor="middle", textfont=dict(size=11, color="white"),
                    showlegend=False
                ))
                fig.add_trace(go.Bar(
                    x=["YTD"], y=[m["YTD份额"]], name=b,
                    marker_color=color_map[b], width=0.6,
                    text=[f"{m['YTD份额']:.1f}"], textposition="inside",
                    insidetextanchor="middle", textfont=dict(size=11, color="white"),
                    showlegend=False
                ))

            cr5_ly = metrics_df["LY份额"].sum()
            cr5_ytd = metrics_df["YTD份额"].sum()
            fig.add_annotation(x="LY", y=cr5_ly, text=f"{cr5_ly:.1f}",
                               showarrow=False, font=dict(size=11, color=C_TXT), yshift=10)
            fig.add_annotation(x="YTD", y=cr5_ytd, text=f"{cr5_ytd:.1f}",
                               showarrow=False, font=dict(size=11, color=C_TXT), yshift=10)

            fig.update_layout(
                height=400,
                barmode="stack",
                bargap=0.35,
                margin=dict(t=30, b=30, l=10, r=10),
                paper_bgcolor="white",
                plot_bgcolor="white",
                font=dict(size=13, family="Microsoft YaHei, sans-serif"),
                xaxis=dict(showgrid=False, tickfont=dict(size=13)),
                yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                showlegend=False,
                uniformtext=dict(mode="show", minsize=11),
            )
            st.plotly_chart(fig, use_container_width=True)

        with cL_table:
            st.markdown("<b class='chart-title'>YTD 规模同比 & 份额变化</b>", unsafe_allow_html=True)
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
                f"<thead><tr><th>品牌</th><th>YTD<br>规模同比</th><th>YTD<br>份额同比</th><th>{sel_month[2:4]}M{sel_mon}<br>份额环比</th></tr></thead>"
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
                line=dict(color=color_map[b], width=2),
                text=[f"{v:.1f}" if (show_label and not pd.isna(v)) else "" for v in shares],
                textposition="top center" if "汤臣倍健" in b else "bottom center",
                textfont=dict(size=9, color=color_map[b]),
                showlegend=True
            ))

        fig2.update_layout(
            height=400,
            margin=dict(t=30, b=30, l=40, r=20),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=13, family="Microsoft YaHei, sans-serif"),
            xaxis=dict(showgrid=False, tickfont=dict(size=11), tickangle=-45),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                        font=dict(size=11), itemsizing="constant",
                        itemwidth=30, tracegroupgap=5),
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.caption("数据来源：中康全国零售药店")

# ====================== Part A PAGE 3: 汤臣倍健销售规模及市场份额 ======================
def page3(SEL_MONTHS):
    sl_l = ym_lab(SEL_MONTHS[0])
    sl_r = ym_lab(SEL_MONTHS[-1])
    st.markdown(f"""
    <div class="phdr">
        <h2>全国零售药店 - 汤臣倍健销售规模及市场份额</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="ibar">
    <b>口径：</b>VDS品类 = industry 表 品类为 VDS 的月度销售额；汤臣倍健集团 = industry 表 品类 = VDS 且 品牌 = 汤臣倍健 的月度销售额；
    汤臣重点品类 = sku 表 集团权益 = 汤臣倍健 的月度销售额；汤臣其它品类 = 汤臣倍健集团 - 汤臣重点品类；
    市场份额 = 汤臣倍健集团 / VDS品类 × 100；同比 = (本期 / 去年同期 - 1) × 100。
    </div>
    """, unsafe_allow_html=True)

    all_records = []
    for m in ind_months:
        vds_total = ind_sales(m, {"品类": "VDS"})
        tang_group_total = ind_sales(m, {"品类": "VDS", "品牌": "汤臣倍健"})
        tang_key = sku_sales(m, {"集团权益": "汤臣倍健"})
        tang_other = tang_group_total - tang_key
        share = (tang_group_total / vds_total * 100) if vds_total > 0 else np.nan

        all_records.append({
            "year_month": m,
            "label": ym_lab(m),
            "VDS": vds_total,
            "汤臣倍健集团": tang_group_total,
            "汤臣重点品类": tang_key,
            "汤臣其它品类": tang_other,
            "市场份额": share,
        })

    df_full = pd.DataFrame(all_records)
    df_data = df_full[df_full["year_month"].isin(SEL_MONTHS)].reset_index(drop=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_data["label"],
        y=df_data["汤臣重点品类"],
        name="汤臣重点品类销售额-百万元",
        marker_color=C_KEY,
        text=[f"{v:.0f}" if v > 0 else "" for v in df_data["汤臣重点品类"]],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=9, color="white"),
    ))

    fig.add_trace(go.Bar(
        x=df_data["label"],
        y=df_data["汤臣其它品类"],
        name="汤臣其它品类销售额-百万元",
        marker_color=C_OTHER,
        text=[f"{v:.0f}" if v > 0 else "" for v in df_data["汤臣其它品类"]],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=9, color="white"),
    ))

    fig.add_trace(go.Scatter(
        x=df_data["label"],
        y=df_data["汤臣倍健集团"],
        mode="text",
        text=[f"{v:.0f}" if v > 0 else "" for v in df_data["汤臣倍健集团"]],
        textposition="top center",
        textfont=dict(size=9, color=C_TXT),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=df_data["label"],
        y=df_data["市场份额"],
        name="市场份额%（占 total VDS）",
        mode="lines+markers+text",
        marker=dict(color=C_SHARE, size=5),
        line=dict(color=C_SHARE, width=2),
        text=[f"{v:.1f}" if not pd.isna(v) else "" for v in df_data["市场份额"]],
        textposition="top center",
        textfont=dict(size=9, color=C_SHARE),
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
            font=dict(size=11, color="#555"),
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
        bargap=0.3,
        margin=dict(t=130, b=50, l=40, r=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(size=13, family="Microsoft YaHei, sans-serif"),
        xaxis=dict(showgrid=False, tickfont=dict(size=11)),
        yaxis=dict(
            title="",
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, y1_max] if y1_max else None
        ),
        yaxis2=dict(
            title="",
            overlaying="y",
            side="right",
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            range=[0, y2_max] if y2_max else None
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

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<b class='chart-title'>销售同比增速</b>", unsafe_allow_html=True)

    table_rows = []
    row_map = {
        "VDS品类": "VDS",
        "汤臣倍健集团": "汤臣倍健集团",
        "汤臣重点品类": "汤臣重点品类",
    }
    for row_name, key in row_map.items():
        cells = [f"<td>{row_name}</td>"]
        for m in SEL_MONTHS:
            v = calc_yoy_p3(df_full, m, key)
            if pd.isna(v):
                cells.append("<td>-</td>")
            else:
                color = "#FF0000" if v < 0 else ("#00B050" if v > 10 else C_TXT)
                cells.append(f"<td style='color:{color}'>{v:+.0f}%</td>")
        table_rows.append("<tr>" + "".join(cells) + "</tr>")

    header_cells = ["<th>销售同比增速</th>"] + [f"<th>{ym_lab(m)}</th>" for m in SEL_MONTHS]
    table_html = (
        f"<table class='dt-p3'><thead><tr>{''.join(header_cells)}</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    st.divider()
    st.caption("数据来源：中康全国零售药店")
    st.caption("注：重点品类包括蛋白粉、钙、多维、鱼油、氨糖、益生菌，包含OTC。")

# ====================== Part A PAGE 4: 市场份额分析表 ======================
def page4(selected_month):
    st.markdown(f"""
    <div class="phdr">
        <h2>全国零售药店 - 汤臣倍健市场份额分析</h2>
    </div>
    """, unsafe_allow_html=True)

    CUR_YEAR = int(selected_month[:4])
    CUR_MONTH = int(selected_month[4:])

    YTD_MONTHS = get_months(CUR_YEAR, CUR_MONTH, CUR_MONTH)
    L3M_MONTHS = get_months(CUR_YEAR, CUR_MONTH, 3)
    CUR_MONTH_STR = f"{CUR_YEAR}{str(CUR_MONTH).zfill(2)}"
    PRE_MONTH_STR = get_months(CUR_YEAR, CUR_MONTH, 2)[0]

    YTD_LY_MONTHS = get_months(CUR_YEAR - 1, CUR_MONTH, CUR_MONTH)
    L3M_LY_MONTHS = get_months(CUR_YEAR - 1, CUR_MONTH, 3)
    CUR_LY_MONTH_STR = f"{CUR_YEAR - 1}{str(CUR_MONTH).zfill(2)}"

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
            "brand_source": "industry", "brand_filter": {"品类": "VDS", "品牌": "汤臣倍健"},
            "brand_display": "汤臣倍健集团", "has_bar": False,
        },
        {"name": "蛋白粉", "sub": "（不含OTC）", "cat_source": "sku", "cat_filter": {"品类": "蛋白粉"}, "brand_source": "sku", "brand_filter": {"品类": "蛋白粉", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "成人钙", "sub": "（含OTC）", "cat_source": "sku", "cat_filter": {"品类": "钙-成人"}, "brand_source": "sku", "brand_filter": {"品类": "钙-成人", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "儿童钙", "sub": "（含OTC）", "cat_source": "sku", "cat_filter": {"品类": "钙-儿童"}, "brand_source": "sku", "brand_filter": {"品类": "钙-儿童", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "成人多维", "sub": "（含OTC）", "cat_source": "sku", "cat_filter": {"品类": "多维-成人"}, "brand_source": "sku", "brand_filter": {"品类": "多维-成人", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "儿童多维", "sub": "（含OTC）", "cat_source": "sku", "cat_filter": {"品类": "多维-儿童"}, "brand_source": "sku", "brand_filter": {"品类": "多维-儿童", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "鱼油", "sub": "（不含OTC）", "cat_source": "sku", "cat_filter": {"品类": "鱼油"}, "brand_source": "sku", "brand_filter": {"品类": "鱼油", "品牌": "汤臣倍健"}, "brand_display": "汤臣倍健", "has_bar": True},
        {"name": "氨糖", "sub": "（含OTC）", "cat_source": "sku", "cat_filter": {"品类": "关节护理"}, "brand_source": "sku", "brand_filter": {"品类": "关节护理", "品牌": "健力多"}, "brand_display": "健力多", "has_bar": True},
        {"name": "益生菌", "sub": "（含OTC）", "cat_source": "sku", "cat_filter": {"品类": "益生菌"}, "brand_source": "sku", "brand_filter": {"品类": "益生菌", "品牌": "Life-Space"}, "brand_display": "Life-Space", "has_bar": True},
    ]

    table_data = []
    for r in ROWS:
        cat_ytd = sales_by_source(r["cat_source"], YTD_MONTHS, r["cat_filter"])
        cat_l3m = sales_by_source(r["cat_source"], L3M_MONTHS, r["cat_filter"])
        cat_m4 = sales_by_source(r["cat_source"], [CUR_MONTH_STR], r["cat_filter"])
        cat_m3 = sales_by_source(r["cat_source"], [PRE_MONTH_STR], r["cat_filter"])
        cat_ytd_ly = sales_by_source(r["cat_source"], YTD_LY_MONTHS, r["cat_filter"])
        cat_l3m_ly = sales_by_source(r["cat_source"], L3M_LY_MONTHS, r["cat_filter"])
        cat_m4_ly = sales_by_source(r["cat_source"], [CUR_LY_MONTH_STR], r["cat_filter"])

        brand_ytd = sales_by_source(r["brand_source"], YTD_MONTHS, r["brand_filter"])
        brand_l3m = sales_by_source(r["brand_source"], L3M_MONTHS, r["brand_filter"])
        brand_m4 = sales_by_source(r["brand_source"], [CUR_MONTH_STR], r["brand_filter"])
        brand_m3 = sales_by_source(r["brand_source"], [PRE_MONTH_STR], r["brand_filter"])
        brand_ytd_ly = sales_by_source(r["brand_source"], YTD_LY_MONTHS, r["brand_filter"])
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
          <th class="sales-header-a">销售额<br><span style="font-size:10px;font-weight:normal;">百万元</span></th>
          <th colspan="4" class="growth-header-a">销售额增速</th>
          <th rowspan="2" class="brand-header">汤臣品牌</th>
          <th class="sales-header-b">销售额<br><span style="font-size:10px;font-weight:normal;">百万元</span></th>
          <th colspan="4" class="growth-header-b">销售额增速</th>
          <th colspan="7" class="share-header">汤臣倍健市场份额 (%)</th>
        </tr>
        <tr class="sub-header">
          <th class="sales-header-a">YTD</th>
          <th class="growth-header-a">YTD<br>同比</th>
          <th class="growth-header-a">L3M<br>同比</th>
          <th class="growth-header-a">{str(CUR_YEAR)[2:]}M{CUR_MONTH}<br>同比</th>
          <th class="growth-header-a">{str(CUR_YEAR)[2:]}M{CUR_MONTH}<br>环比</th>
          <th class="sales-header-b">YTD</th>
          <th class="growth-header-b">YTD<br>同比</th>
          <th class="growth-header-b">L3M<br>同比</th>
          <th class="growth-header-b">{str(CUR_YEAR)[2:]}M{CUR_MONTH}<br>同比</th>
          <th class="growth-header-b">{str(CUR_YEAR)[2:]}M{CUR_MONTH}<br>环比</th>
          <th class="share-header">YTD</th>
          <th class="share-header">同比</th>
          <th class="share-header">L3M</th>
          <th class="share-header">同比</th>
          <th class="share-header">{str(CUR_YEAR)[2:]}M{CUR_MONTH}</th>
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
        c_color, f_color = share_change_color(v)
        s = format_share(v)
        if not pd.isna(v):
            s = f"{v:+.1f}"
        return f'<td class="num share-change" style="color:{f_color}">{circle_svg(c_color)}<span>{s}</span></td>'

    def td_sales_plain(v):
        if pd.isna(v):
            return '<td class="num sales-bold">-</td>'
        return f'<td class="num sales-bold">{format_sales(v)}</td>'

    def build_row(row):
        name_cell = f'<td class="cat-name">{row["name"]}<span class="sub">{row["sub"]}</span></td>'
        cat_sales = td_bar_sales(row["cat_ytd"], max_cat_ytd, BAR_A_START, BAR_A_END) if row["has_bar"] else td_sales_plain(row["cat_ytd"])
        cat_growth = "".join([
            td_growth(row["cat_ytd_yoy"]),
            td_growth(row["cat_l3m_yoy"]),
            td_growth(row["cat_m4_yoy"]),
            td_growth(row["cat_m4_mom"]),
        ])
        brand_cell = f'<td class="brand-name">{row["brand_display"]}</td>'
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
    if v >= 10:
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
    LY_M_STR = fp_get_ly_month(selected_month)
    YTD_MONTHS = fp_get_ytd_months(CUR_YEAR, CUR_MONTH)
    YTD_LY_MONTHS = fp_get_ytd_months(CUR_YEAR - 1, CUR_MONTH)

    st.markdown(f"""
    <div class="ibar">
    <b>口径：</b>当前月 = {CUR_M_STR}（{ym_lab(CUR_M_STR)}）&nbsp;|&nbsp;
    YTD = {CUR_YEAR}年1-{CUR_MONTH}月累计 &nbsp;|&nbsp;
    同比 = 本期 / 去年同期 - 1 &nbsp;|&nbsp;
    销售额单位：百万元；销售量单位：百盒；单价单位：元/盒
    </div>
    """, unsafe_allow_html=True)

    metric_rows = []
    metric_rows.append(fp_build_metric_row(selected_cat, "cat-h", {"品类": config["cat"]}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))
    if has_otc:
        metric_rows.append(fp_build_metric_row(f"{selected_cat}OTC", "otc-h", {"品类": config["cat"], "处方性质": "OTC"}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))
        metric_rows.append(fp_build_metric_row(f"{selected_cat}VDS", "vds-h", {"品类": config["cat"], "处方性质": "VDS"}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))
    metric_rows.append(fp_build_metric_row(config["brand_label"], "brand-h", {"品类": config["cat"], "品牌": config["brand"]}, CUR_M_STR, LY_M_STR, YTD_MONTHS, YTD_LY_MONTHS))

    monthly_df = fp_build_monthly_data(display_months, config["cat"], config["brand"], has_otc)
    is_kids_ca = (selected_cat == "儿童钙")

    left_content_height = 590 if has_otc else 520
    if is_kids_ca:
        right_chart_height = 430
    elif has_otc:
        right_chart_height = 408
    else:
        right_chart_height = 430

    cL, cR = st.columns([0.49, 0.51], gap="medium")
    with cL:
        st.markdown(f"<div class='cat-badge'>{selected_cat}品类 & {config['brand_label']}情况</div>", unsafe_allow_html=True)
        st.markdown("<div id='left-table-wrap'>", unsafe_allow_html=True)
        metric_value_col_count = len(metric_rows) * 2
        colgroup = "<colgroup><col style='width:126px'>" + "".join(["<col>" for _ in range(metric_value_col_count)]) + "</colgroup>"
        top_header = "<tr><th rowspan='2' style='width:126px'>维度</th>"
        for r in metric_rows:
            top_header += f"<th colspan='2' class='{r['header_class']}'>{r['label']}</th>"
        top_header += "</tr>"
        sub_header = "<tr>"
        for _ in metric_rows:
            sub_header += f"<th>{ym_lab(CUR_M_STR)}</th><th>YTD</th>"
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
                textfont=dict(size=14, color="white", family="Microsoft YaHei, sans-serif"),
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
                textfont=dict(size=14, color="white", family="Microsoft YaHei, sans-serif"),
                showlegend=False, hoverinfo="skip",
                cliponaxis=False,
            ))
            cat_total = monthly_df["otc"] + monthly_df["vds"]
            fig.add_trace(go.Scatter(
                x=monthly_df["label"], y=cat_total, name="品类总计",
                mode="text",
                text=[fmt_num(v) for v in cat_total],
                textposition="top center",
                textfont=dict(size=14, color="#333", family="Microsoft YaHei, sans-serif"),
                showlegend=False, hoverinfo="skip",
            ))
        else:
            fig.add_trace(go.Bar(
                x=monthly_df["label"], y=monthly_df["cat"], name=selected_cat,
                marker_color=FP_COLORS["cat"],
                text=[fmt_num(v) for v in monthly_df["cat"]], textposition="inside",
                textfont=dict(size=14, color="white", family="Microsoft YaHei, sans-serif"),
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
            line=dict(color=FP_COLORS["brand_line"], width=2.5),
            text=[fmt_num(v) for v in monthly_df["brand"]],
            textposition="top center",
            textfont=dict(size=14, color=FP_COLORS["brand_line"], family="Microsoft YaHei, sans-serif"),
            yaxis="y2",
            cliponaxis=False,
            showlegend=True, hoverinfo="skip",
        ))
        fig.update_layout(
            barmode="stack",
            bargap=0.25,
            height=right_chart_height,
            margin=dict(t=42, b=22, l=20, r=40),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=14, family="Microsoft YaHei, sans-serif"),
            xaxis=dict(showgrid=False, tickfont=dict(size=13), tickangle=-45),
            uniformtext=dict(minsize=14, mode="show"),
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
        st.plotly_chart(fig, use_container_width=True)

        # 下方增长率表
        growth_rows = []
        growth_rows.append({
            "label": f"{selected_cat}同比",
            "values": [fp_calc_yoy(r["cat"], r["cat_ly"]) for _, r in monthly_df.iterrows()]
        })
        if has_otc:
            growth_rows.append({
                "label": "OTC同比",
                "values": [fp_calc_yoy(r["otc"], r["otc_ly"]) for _, r in monthly_df.iterrows()]
            })
            growth_rows.append({
                "label": "VDS同比",
                "values": [fp_calc_yoy(r["vds"], r["vds_ly"]) for _, r in monthly_df.iterrows()]
            })
        growth_rows.append({
            "label": f"{config['brand_label']}同比",
            "values": [fp_calc_yoy(r["brand"], r["brand_ly"]) for _, r in monthly_df.iterrows()]
        })
        header = "<tr><th style='width:110px;white-space:nowrap'>增长率</th>" + "".join([f"<th>{ym_lab(m)}</th>" for m in display_months]) + "</tr>"
        body = ""
        for gr in growth_rows:
            cells = [f"<td style='white-space:nowrap'>{gr['label']}</td>"]
            for v in gr["values"]:
                cells.append(f"<td style='color:{fp_growth_color(v)};white-space:nowrap'>{fp_fmt_pct(v)}</td>")
            body += "<tr>" + "".join(cells) + "</tr>"

        growth_html = "<table class='growth-table' style='font-size:13px'>" + header + body + "</table>"
        st.markdown(growth_html, unsafe_allow_html=True)

    st.markdown("<hr style='margin:20px 0;border:none;border-top:2px solid #1B4F8E'/>", unsafe_allow_html=True)
    st.caption("*注：VDS+OTC包含蓝帽子产品、健康食品、相关OTC，不含感冒止咳纯药品")


# ====================== Part B BA_CATEGORY_CONFIG, AFFILIATE_BRANDS, BRAND_ALIAS, COLOR_PALETTE ======================
BA_CATEGORY_CONFIG = {
    "蛋白粉": {"cat": "蛋白粉", "focus": ["汤臣倍健", "维诺健"]},
    "成人钙": {"cat": "钙-成人", "focus": ["钙尔奇", "迪巧", "励全", "汤臣倍健"]},
    "儿童钙": {"cat": "钙-儿童", "focus": ["锌钙特", "仁合益康", "汤臣倍健"]},
    "成人多维": {"cat": "多维-成人", "focus": ["善存", "汤臣倍健"]},
    "儿童多维": {"cat": "多维-儿童", "focus": ["草仙药业", "汤臣倍健"]},
    "鱼油": {"cat": "鱼油", "focus": ["汤臣倍健", "维诺健"]},
    "氨糖": {"cat": "关节护理", "focus": ["健力多", "九力"]},
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
    if v > 10:
        return "pos"
    return "plain"


def cls_delta(v):
    if pd.isna(v):
        return "plain"
    return "pos" if v >= 0 else "neg"


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


def build_table_html(cat_label, cat, table_brands, current_ym):
    rows = [row_metrics(cat_label, cat, None, current_ym)]
    rows.extend([row_metrics(brand_name(b), cat, b, current_ym) for b in table_brands])
    html = [
        "<table class='brand-table'>",
        "<tr><th rowspan='2' class='brand-col'>TOP品牌</th><th colspan='1' class='group-head'>销售额<br>百万元</th><th colspan='3' class='group-head'>同比增长率</th><th colspan='2' class='group-head'>销售额增长率</th><th colspan='5' class='group-head'>市场份额(%)</th></tr>",
        f"<tr><th class='sub-head'>YTD</th><th class='sub-head'>销售额</th><th class='sub-head'>销售量</th><th class='sub-head'>单盒均价</th><th class='sub-head'>{ym_lab(current_ym)}<br>同比</th><th class='sub-head'>{ym_lab(current_ym)}<br>环比</th><th class='sub-head'>{ym_lab(current_ym)}</th><th class='sub-head'>同比</th><th class='sub-head'>环比</th><th class='sub-head'>YTD</th><th class='sub-head'>同比</th></tr>",
    ]
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
                x=["LY", "YTD"],
                y=[0 if pd.isna(ly_val) else ly_val, 0 if pd.isna(ytd_val) else ytd_val],
                name=brand_name(brand),
                marker=dict(
                    color=COLOR_PALETTE[i % len(COLOR_PALETTE)],
                    line=dict(color=["#FF0000" if inc else "rgba(0,0,0,0)", "#FF0000" if inc else "rgba(0,0,0,0)"], width=[3 if inc else 0, 3 if inc else 0]),
                ),
                text=[fmt_share(ly_val) if show_text else "", fmt_share(ytd_val) if show_text else ""],
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="white", size=11 if show_text else 9, family="Microsoft YaHei"),
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
            line=dict(color="#FF0000" if inc else "rgba(0,0,0,0)", width=2 if inc else 0),
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
            font=dict(size=12, color="#333", family="Microsoft YaHei"),
        )

    fig.add_annotation(x="LY", y=total_ly + 1.2, text=f"<b>{fmt_share(total_ly)}</b>", showarrow=False, font=dict(size=15, color="#111"))
    fig.add_annotation(x="YTD", y=total_ytd + 1.2, text=f"<b>{fmt_share(total_ytd)}</b>", showarrow=False, font=dict(size=15, color="#111"))
    fig.add_annotation(
        x=0.5, y=1.02,
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
        font=dict(family="Microsoft YaHei", size=13),
        xaxis=dict(showgrid=False, tickfont=dict(size=15)),
        yaxis=dict(showgrid=False, showticklabels=False, range=[0, max(total_ly, total_ytd) + 3]),
        showlegend=False,
    )
    return fig


def make_trend_chart(cat_label, cat, brands, months):
    fig = go.Figure()
    for i, brand in enumerate(brands):
        vals = [calc_share([m], cat, brand) for m in months]
        fig.add_trace(
            go.Scatter(
                x=[ym_lab(m) for m in months],
                y=vals,
                mode="lines+markers+text",
                name=brand_name(brand),
                line=dict(width=3, color=COLOR_PALETTE[i % len(COLOR_PALETTE)]),
                marker=dict(size=6),
                text=[fmt_share(v) if not pd.isna(v) else "" for v in vals],
                textposition="top center",
                textfont=dict(size=10, color=COLOR_PALETTE[i % len(COLOR_PALETTE)]),
                hovertemplate="%{fullData.name}<br>%{x}份额：%{y:.3f}%<extra></extra>",
            )
        )
    fig.update_layout(
        title=dict(text=f"{cat_label}-重点品牌份额(%)趋势", x=0.5, font=dict(size=16, color="#666")),
        height=315,
        margin=dict(t=46, b=48, l=0, r=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Microsoft YaHei", size=12),
        xaxis=dict(showgrid=False, tickangle=-45, automargin=False),
        yaxis=dict(showgrid=True, gridcolor="#EEF2FA", showticklabels=False, zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(range=[-0.5, len(months) - 0.5])
    return fig


# ====================== Part B render_brand_analysis() (WITH 氨糖/益生菌 mod) ======================
def render_brand_analysis(selected_cat, selected_month, display_months):
    st.markdown("<hr style='margin:20px 0;border:none;border-top:2px solid #1B4F8E'/>", unsafe_allow_html=True)
    config = BA_CATEGORY_CONFIG[selected_cat]
    source_cat = config["cat"]

    st.markdown(
        f"""
        <div class="note-bar">
        <b>口径：</b>数据来自 <b>test.sku</b>；当前月 = {selected_month}（{ym_lab(selected_month)}）；
        YTD = 当年1月至当前月；MAT = 含当期向上滚动12个月；L3M = 含当期过去3个月；
        销售额单位由千元换算为百万元，销售量单位为百盒，平均单价 = 销售额 / 销售量 × 10。
        </div>
        """,
        unsafe_allow_html=True,
    )

    ytd_months = period_months("YTD", selected_month)
    top10_brands = build_top10(source_cat, ytd_months)
    table_brands = list(top10_brands)
    if selected_cat in ("氨糖", "益生菌"):
        # 氨糖&益生菌：品牌表格中去掉汤臣倍健
        table_brands = [b for b in table_brands if b != "汤臣倍健"]
    else:
        if "汤臣倍健" not in table_brands and ba_calc_agg(ytd_months, cat=source_cat, brand="汤臣倍健")["sales"] > 0:
            table_brands.append("汤臣倍健")
    left_chart_height = 735 + max(0, len(table_brands) - 10) * 28

    left_col, right_col = st.columns([0.28, 0.72], gap="medium")
    with left_col:
        st.plotly_chart(make_top10_share_chart(selected_cat, source_cat, top10_brands, selected_month, left_chart_height), use_container_width=True)
    with right_col:
        st.markdown(build_table_html(selected_cat, source_cat, table_brands, selected_month), unsafe_allow_html=True)
        st.plotly_chart(make_trend_chart(selected_cat, source_cat, config["focus"], display_months), use_container_width=True)


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
        ],
    },
    "儿童多维": {
        "cat": "多维-儿童",
        "rows": [
            {"name": "汤臣倍健多维咀嚼片60片", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "汤臣倍健(多种维生素咀嚼片)", "产品包装": "1gx60s"}},
            {"name": "仁合堂药业五维赖氨酸口服液12袋", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "五维赖氨酸口服溶液(黑龙江仁合堂药业)", "产品包装": "10mlx12z"}},
            {"name": "草仙药业五维赖氨酸片36片", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "五维赖氨酸片(草仙药业)", "产品包装": "36s"}},
            {"name": "小施尔康多维咀嚼片(10)30片", "source": "sku", "filters": {"品类": "多维-儿童", "品牌产品": "小施尔康(小儿多维生素咀嚼片(10))", "产品包装": "30s"}},
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
    "儿童多维": "汤臣儿童多维-SKU市场指标趋势分析",
    "鱼油": "汤臣鱼油各规格-线下药店市场指标趋势",
    "氨糖": "健力多各系列-线下药店市场指标趋势",
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
    "儿童多维": 0,
    "鱼油": 0,
    "氨糖": 0,
    "益生菌": 0,
}

CHART_NAMES = {
    "蛋白粉": {
        "bar":    ["旧品", "金装", "白金", "E钙"],
        "price":  ["金装礼盒装300g*2p", "白金礼盒装330g*2p", "E钙蛋520g"],
        "dist":   ["旧品", "金装", "白金", "E钙", "汤臣整体"],
        "power":  ["旧品", "金装", "白金", "E钙", "汤臣整体"],
    },
    "成人钙": {
        "bar":    ["200粒x2", "120粒", "焕动力120粒", "其他"],
        "price":  ["200粒x2", "120粒", "焕动力120粒", "钙尔奇D600 60片"],
        "dist":   ["200粒x2", "120粒", "焕动力120粒", "汤臣钙DK整体", "钙尔奇D600 60片"],
        "power":  ["200粒x2", "120粒", "焕动力120粒", "汤臣钙DK整体", "钙尔奇D600 60片"],
        "bar_colors": {"200粒x2": "#4472C4", "120粒": "#FFC000", "焕动力120粒": "#ED7D31", "其他": "#A6A6A6"},
    },
    "儿童钙": {
        "bar":    ["牛初乳60片*2", "钙铁锌60片", "钙镁90片", "液体钙12袋"],
        "price":  ["牛初乳60片*2", "钙镁90片", "液体钙12袋", "钙铁锌60片", "锌钙特葡萄糖酸钙锌口服液24袋"],
        "dist":   ["牛初乳60片*2", "钙镁90片", "液体钙12袋", "钙铁锌60片", "锌钙特葡萄糖酸钙锌口服液24袋"],
        "power":  ["牛初乳60片*2", "钙镁90片", "液体钙12袋", "钙铁锌60片", "锌钙特葡萄糖酸钙锌口服液24袋"],
        "bar_colors": {"牛初乳60片*2": "#9C6ADE", "钙铁锌60片": "#FFC000", "钙镁90片": "#ED7D31", "液体钙12袋": "#92D050"},
    },
    "成人多维": {
        "bar":    ["女维120片", "女维60片", "男维120片", "男维60片"],
        "price":  ["女维120片", "女维60片", "男维120片", "男维60片", "银善存91sx2p", "善存多维元素片(29)91sx2p"],
        "dist":   ["女维120片", "女维60片", "男维120片", "男维60片", "银善存91sx2p", "善存多维元素片(29)91sx2p"],
        "power":  ["女维120片", "女维60片", "男维120片", "男维60片", "银善存91sx2p", "善存多维元素片(29)91sx2p"],
    },
    "儿童多维": {
        "bar":    ["汤臣倍健多维咀嚼片60片"],
        "price":  ["汤臣倍健多维咀嚼片60片", "仁合堂药业五维赖氨酸口服液12袋", "草仙药业五维赖氨酸片36片", "小施尔康多维咀嚼片(10)30片"],
        "dist":   ["汤臣倍健多维咀嚼片60片", "仁合堂药业五维赖氨酸口服液12袋", "草仙药业五维赖氨酸片36片", "小施尔康多维咀嚼片(10)30片"],
        "power":  ["汤臣倍健多维咀嚼片60片", "仁合堂药业五维赖氨酸口服液12袋", "草仙药业五维赖氨酸片36片", "小施尔康多维咀嚼片(10)30片"],
        "bar_colors": {"汤臣倍健多维咀嚼片60片": "#4472C4"},
    },
    "鱼油": {
        "bar":    ["200粒", "100粒", "晶纯60粒"],
        "price":  ["200粒", "100粒", "晶纯60粒"],
        "dist":   ["200粒", "100粒", "晶纯60粒", "汤臣鱼油总体"],
        "power":  ["200粒", "100粒", "晶纯60粒", "汤臣鱼油总体"],
        "bar_colors": {"200粒": "#4472C4", "100粒": "#FFC000", "晶纯60粒": "#ED7D31"},
    },
    "氨糖": {
        "bar":    ["旧品", "金装", "白金", "OTC"],
        "price":  ["金装280片礼盒装", "白金150片", "OTC60粒", "蓝氨糖120片"],
        "dist":   ["旧品", "金装", "白金", "OTC"],
        "power":  ["旧品", "金装", "白金", "OTC"],
    },
    "益生菌": {
        "bar":    ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "其他"],
        "price":  ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "益君康30片"],
        "dist":   ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "益倍适总体", "益君康30片"],
        "power":  ["蓝帽20袋", "蓝帽48袋", "畅护10袋", "B420 20袋", "益倍适总体", "益君康30片"],
        "bar_colors": {"蓝帽20袋": "#4472C4", "蓝帽48袋": "#FFC000", "畅护10袋": "#ED7D31", "B420 20袋": "#92D050", "其他": "#A6A6A6"},
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


_CACHE_VER = 15


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
            if ddf.empty or DIST_COL not in ddf.columns:
                dist = np.nan
            else:
                valid = ddf[DIST_COL].notna()
                if not valid.any():
                    dist = np.nan
                else:
                    if SALES_COL in ddf.columns and ddf.loc[valid, SALES_COL].sum() > 0:
                        rate = np.average(ddf.loc[valid, DIST_COL], weights=ddf.loc[valid, SALES_COL])
                    else:
                        rate = ddf.loc[valid, DIST_COL].mean()
                    dist = rate * 100

            power = share / dist * 100 if dist else np.nan
            records.append({
                "month": m, "label": ym_lab(m), "name": row["name"],
                "sales_m": sales_m, "share": share, "price": price,
                "dist": dist, "power": power,
            })
    return pd.DataFrame(records)


# ====================== Part B 公共绘图函数 ======================
def _chart_base(fig, title, height=380, legend_y=1.08, show_yaxis=False, legend_below=False):
    if legend_below:
        leg = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10))
        title_y = 0.99
        margin_t = 100
        margin_b = 38
    else:
        leg = dict(orientation="h", yanchor="bottom", y=legend_y, xanchor="center", x=0.5, font=dict(size=10))
        title_y = 0.97
        margin_t = 90
        margin_b = 38
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.5, xanchor="center", y=title_y, yanchor="top", font=dict(size=15, color="#333")),
        height=height, margin=dict(t=margin_t, b=margin_b, l=10, r=54),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Microsoft YaHei", size=11),
        xaxis=dict(showgrid=False, tickangle=-45),
        yaxis=dict(showgrid=False, zeroline=False, visible=show_yaxis),
        legend=leg,
    )
    return fig


def make_stacked_bar(df, metric, title, names, colors, text_decimals=0, height=380, legend_y=1.08, y_max=None):
    fig = go.Figure()
    labels = df["label"].drop_duplicates().tolist()
    for idx, name in enumerate(names):
        sub = df[df["name"] == name].set_index("label").reindex(labels)
        vals = pd.to_numeric(sub[metric], errors="coerce").fillna(0)
        c = colors.get(name, SA_COLORS[idx % len(SA_COLORS)])
        # 根据值大小动态调整字体：小于1的小数字用更小字体
        text_labels = []
        for v in vals:
            if v <= 0:
                text_labels.append("")
            elif v < 1:
                text_labels.append(f"{v:.{text_decimals}f}")
            else:
                text_labels.append(f"{v:.{text_decimals}f}")
        fig.add_bar(
            x=labels, y=vals, name=name, marker_color=c,
            text=text_labels,
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=8, color="white"),
            textangle=0,
            hovertemplate=f"{name}<br>%{{x}}：%{{y:.{text_decimals}f}}<extra></extra>",
        )
    fig.update_layout(barmode="stack")
    if metric == "share" and len(labels) >= 2:
        last_label, prev_label = labels[-1], labels[-2]
        month_num = last_label.split("M")[-1] if "M" in last_label else ""
        ymax = y_max if y_max is not None else 100
        fig.add_annotation(
            x=last_label, y=ymax * 1.10, text=f"<b>{month_num}月环比<br>(pts)</b>", showarrow=False,
            xshift=28, yshift=0, font=dict(size=10, color="#555"),
        )
        y_cursor = 0.0
        for name in names:
            last_v = pd.to_numeric(df.loc[(df["label"] == last_label) & (df["name"] == name), metric], errors="coerce")
            prev_v = pd.to_numeric(df.loc[(df["label"] == prev_label) & (df["name"] == name), metric], errors="coerce")
            if last_v.notna().any() and prev_v.notna().any():
                val = float(last_v.iloc[0]); base = float(prev_v.iloc[0])
                diff = val - base
                y_center = y_cursor + val / 2
                fig.add_annotation(
                    x=last_label, y=y_center, text=f"{diff:+.1f}", showarrow=False,
                    xshift=28, yshift=0,
                    font=dict(size=11, color="#00A85A" if diff >= 0 else "#E53935", family="Microsoft YaHei"),
                )
                y_cursor += val
            else:
                y_cursor += float(last_v.iloc[0]) if last_v.notna().any() else 0
    fig = _chart_base(fig, title, height, legend_y, show_yaxis=True)
    fig.update_layout(showlegend=True)
    if metric == "share":
        ymax = y_max if y_max is not None else 100
        fig.update_layout(yaxis=dict(showgrid=False, zeroline=False, visible=True, range=[0, ymax * 1.18]))
    return fig


def make_line_chart(df, metric, title, names, colors, decimals=0, height=380, label_mode="endpoints"):
    fig = go.Figure()
    labels = df["label"].drop_duplicates().tolist()
    for idx, name in enumerate(names):
        sub = df[df["name"] == name].set_index("label").reindex(labels)
        vals = pd.to_numeric(sub[metric], errors="coerce")
        c = colors.get(name, SA_COLORS[idx % len(SA_COLORS)])
        fig.add_scatter(
            x=labels, y=vals, mode="lines+markers", name=name,
            line=dict(width=2.3, shape="spline", smoothing=1.2, color=c),
            marker=dict(size=5),
            hovertemplate=f"{name}<br>%{{x}}：%{{y:.{decimals}f}}<extra></extra>",
        )
        valid = [i for i, v in enumerate(vals) if not pd.isna(v)]
        if not valid:
            continue
        annotate_indices = set()
        if label_mode == "endpoints":
            annotate_indices = {valid[0], valid[-1]}
        elif label_mode == "skip_start":
            annotate_indices = set(valid[1:])
        elif label_mode == "all":
            annotate_indices = set(valid)
        for i in annotate_indices:
            fig.add_annotation(
                x=labels[i], y=vals.iloc[i], text=f"{vals.iloc[i]:.{decimals}f}",
                showarrow=False, xshift=0, yshift=12,
                font=dict(size=10, color=c),
            )
    return _chart_base(fig, title, height, 1.08, legend_below=True)


def render_charts(metric_df, cat_label):
    cfg = CHART_NAMES.get(cat_label, {})
    all_names = metric_df["name"].drop_duplicates().tolist()
    colors = {n: SA_COLORS[i % len(SA_COLORS)] for i, n in enumerate(all_names)}
    colors.update(cfg.get("bar_colors", {}))

    left, mid, right = st.columns([0.34, 0.33, 0.33], gap="medium")
    with left:
        bar_names = cfg.get("bar", all_names)
        share_ymax = SHARE_YMAX.get(cat_label, 100)
        share_dec = SHARE_DECIMALS.get(cat_label, 0)
        st.plotly_chart(make_stacked_bar(metric_df, "sales_m", "销售额（百万元）", bar_names, colors, text_decimals=0, height=380), use_container_width=True)
        st.plotly_chart(make_stacked_bar(metric_df, "share", "销售额份额（%）", bar_names, colors, text_decimals=share_dec, height=380, y_max=share_ymax), use_container_width=True)
    with mid:
        price_names = cfg.get("price", all_names)
        st.plotly_chart(make_line_chart(metric_df, "price", "平均单价（元/盒）", price_names, colors, decimals=0, height=760, label_mode="endpoints"), use_container_width=True)
    with right:
        dist_names = cfg.get("dist", all_names)
        power_names = cfg.get("power", dist_names)
        st.plotly_chart(make_line_chart(metric_df, "dist", "动销铺货率（%）", dist_names, colors, decimals=0, height=380, label_mode="endpoints"), use_container_width=True)
        st.plotly_chart(make_line_chart(metric_df, "power", "单点卖力", power_names, colors, decimals=0, height=380, label_mode="endpoints"), use_container_width=True)
        st.markdown("<p style='font-size:11px;color:#E53935;font-style:italic;margin-top:4px'>*单点卖力 = 销售额份额 / 动销铺货率 * 100</p>", unsafe_allow_html=True)


# ====================== Part B render_sku_analysis() ======================
def render_sku_analysis(selected_cat, selected_month, display_months):
    st.markdown("<hr style='margin:20px 0;border:none;border-top:2px solid #1B4F8E'/>", unsafe_allow_html=True)
    config = SA_CATEGORY_CONFIG[selected_cat]

    st.markdown(
        f"<div class='note-bar'><b>数据来源：</b>test.sku、test.brand、test.brand_distribution_rate；当前月 = {selected_month}（{ym_lab(selected_month)}）</div>",
        unsafe_allow_html=True,
    )

    row_keys_json = json.dumps(config["rows"])
    months_json = json.dumps(display_months)

    with st.spinner("正在加载图表..."):
        metric_df = build_metrics_cached(config["cat"], row_keys_json, months_json)
        st.markdown(f"<h3 style='text-align:center;margin:12px 0 18px;color:#111'>{TITLE_MAP.get(selected_cat, selected_cat)}</h3>", unsafe_allow_html=True)
        render_charts(metric_df, selected_cat)
        st.markdown("<p style='font-size:12px;color:#666'><i>数据源：中康全国零售药店</i></p>", unsafe_allow_html=True)


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

# Tab 导航放在最顶部（主标题下方）
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
    page3(SEL_M_A)
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
            if st.button(cat, key=f"cat_btn_{i}", type="primary" if is_sel else "secondary", use_container_width=True):
                st.session_state.selected_cat = cat
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    selected_cat = st.session_state.selected_cat

    # 月份 + 范围选择器
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

    # ---- Section 一：品类概览 ----
    st.markdown("""
    <div class="section-header">
        <span class="num">1</span>
        <span>品类概览</span>
    </div>
    """, unsafe_allow_html=True)
    render_first_page(selected_cat, selected_month, display_months)

    # ---- Section 二：品牌竞争分析 ----
    st.markdown("""
    <div class="section-header">
        <span class="num">2</span>
        <span>品牌竞争分析</span>
    </div>
    """, unsafe_allow_html=True)
    render_brand_analysis(selected_cat, selected_month, display_months)

    # ---- Section 三：SKU/品线分析 ----
    st.markdown("""
    <div class="section-header">
        <span class="num">3</span>
        <span>SKU/品线分析</span>
    </div>
    """, unsafe_allow_html=True)
    render_sku_analysis(selected_cat, selected_month, display_months)