"""
slide_16_9.py

Pure CSS 16:9 slide layout for Streamlit dashboard.
No JavaScript - avoids Streamlit Cloud rendering issues.

Usage:
    from slide_16_9 import apply_layout, page_start, page_end
    apply_layout()
    page_start("Page 1")
    page1(...)
    page_end()
    page_start("Page 2")
    page2(...)
    page_end()
"""

import streamlit as st

_page_count = 0

_CSS = r"""
<style>
/* Hide Streamlit chrome */
footer { display: none !important; }
#st-bottom { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
a[href*="streamlit.app"] { display: none !important; }

/* Slide label */
.ppt-slide-label-16x9 {
    font-size: 12px; color: #94A3B8; font-weight: 600;
    text-align: center; margin: 0 0 4px; letter-spacing: 1px;
}

/* Page break marker (invisible on screen) */
.ppt-pagebreak-16x9 { display: none; }

/* ====== Print: page breaks ====== */
@media print {
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stHeader"],
    [data-testid="stAppViewBlockContainer"],
    footer, #st-bottom, .stDeployButton,
    .ppt-slide-label-16x9,
    button { display: none !important; }

    @page { size: A4 landscape; margin: 1cm; }
    body { background: white !important; }

    /* Page break before each pagebreak marker's Streamlit wrapper */
    [data-testid="stMarkdown"]:has(> div > .ppt-pagebreak-16x9),
    [data-testid="stVerticalBlock"] > div:has(> [data-testid="stMarkdown"] > div > .ppt-pagebreak-16x9) {
        page-break-before: always;
        break-before: page;
        display: block !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden;
    }

    .ppt-pagebreak-16x9 { display: none !important; }

    [data-testid="stVerticalBlock"], [data-testid="stAppViewContainer"] {
        overflow: visible !important; height: auto !important;
    }
}
</style>
"""


def apply_layout():
    global _page_count
    _page_count = 0
    st.markdown(_CSS, unsafe_allow_html=True)


def page_start(title=""):
    global _page_count
    _page_count += 1
    if _page_count > 1:
        st.markdown(
            '<div class="ppt-pagebreak-16x9"></div>',
            unsafe_allow_html=True,
        )
    if title:
        st.markdown(
            f'<div class="ppt-slide-label-16x9">{title}</div>',
            unsafe_allow_html=True,
        )


def page_end():
    pass  # No-op for pure CSS mode
