"""
slide_16x9.py v4

16:9 slide layout - CSS-only approach, no JS scaling.
- Charts: fixed heights via CSS (no transform: scale)
- Conclusions: smaller fonts, tighter line-height
- Tables: ultra-compact
- All sizing via CSS, JS only wraps content into slide containers

Usage:
    from slide_16x9 import apply_layout, page_start, page_end
    apply_layout()
    page_start("Page 1")
    page1(...)
    page_end()
"""

import streamlit as st
import streamlit.components.v1 as components

_page_count = 0

_CSS = r"""
<style>
/* Hide Streamlit chrome */
footer { display: none !important; }
#st-bottom { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
a[href*="streamlit.app"] { display: none !important; }

/* Markers invisible */
.slide-marker-start, .slide-marker-end { display: none !important; }

/* ===== 16:9 slide container ===== */
.ppt-slide-16x9 {
    width: 100%;
    aspect-ratio: 16 / 9;
    max-width: calc((100vh - 40px) * 16 / 9);
    margin: 4px auto;
    overflow: hidden;
    position: relative;
    background: white;
    border: 1px solid #d0d5dd;
    border-radius: 3px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}

/* Slide title label */
.ppt-slide-title {
    position: absolute; top: 1px; left: 8px;
    font-size: 9px; color: #94A3B8; font-weight: 600;
    z-index: 100; pointer-events: none; letter-spacing: 1px;
}

/* ===== Content wrapper ===== */
.ppt-slide-content {
    width: 100%; height: 100%;
    overflow: hidden; position: relative;
}

/* ===== Block gaps: near zero ===== */
.ppt-slide-content [data-testid="stVerticalBlock"] { gap: 0.1rem !important; }
.ppt-slide-content [data-testid="stVerticalBlock"] > div {
    padding-top: 0.1rem !important; padding-bottom: 0.1rem !important;
}
.ppt-slide-content .main .block-container,
.ppt-slide-content .block-container {
    padding: 0.1rem 0.3rem !important; max-width: 100% !important;
}

/* ===== Markdown: zero spacing ===== */
.ppt-slide-content [data-testid="stMarkdown"] { margin: 0 !important; padding: 0 !important; }
.ppt-slide-content [data-testid="stMarkdown"] > div { margin: 0 !important; padding: 0 !important; }
.ppt-slide-content p { margin: 1px 0 !important; line-height: 1.2 !important; }
.ppt-slide-content hr { margin: 1px 0 !important; border: none !important; border-top: 1px solid #E4E9F0 !important; }

/* ===== Plotly charts: FIXED HEIGHTS (no scaling) ===== */
.ppt-slide-content [data-testid="stPlotlyChart"] {
    margin: 0 !important; padding: 0 !important;
    height: 200px !important;
}
.ppt-slide-content [data-testid="stPlotlyChart"] > div {
    height: 200px !important;
    max-height: 200px !important;
}
/* Smaller charts in 2-column layouts */
.ppt-slide-content [data-testid="stHorizontalBlock"] [data-testid="stPlotlyChart"] {
    height: 170px !important;
}
.ppt-slide-content [data-testid="stHorizontalBlock"] [data-testid="stPlotlyChart"] > div {
    height: 170px !important;
    max-height: 170px !important;
}
/* Plotly svg responsive */
.ppt-slide-content .js-plotly-plot .plotly-notifier { display: none !important; }

/* ===== Columns: minimal gap ===== */
.ppt-slide-content [data-testid="stHorizontalBlock"] { gap: 0.1rem !important; }
.ppt-slide-content [data-testid="stHorizontalBlock"] > div {
    padding-left: 0.1rem !important; padding-right: 0.1rem !important;
}

/* ===== Tables: ultra-compact ===== */
.ppt-slide-content .dt, .ppt-slide-content .dt-p2, .ppt-slide-content .dt-p3,
.ppt-slide-content .dashboard-table, .ppt-slide-content .metric-table,
.ppt-slide-content .brand-table, .ppt-slide-content .growth-table {
    font-size: 9px !important; line-height: 1.1 !important;
}
.ppt-slide-content .dt th, .ppt-slide-content .dt td {
    padding: 1px 3px !important; height: auto !important; font-size: 9px !important; line-height: 1.1 !important;
}
.ppt-slide-content .dt-p2 th, .ppt-slide-content .dt-p2 td {
    padding: 1px 3px !important; height: auto !important; font-size: 9px !important; line-height: 1.1 !important;
}
.ppt-slide-content .dt-p2, .ppt-slide-content .dt-p2 tr { height: auto !important; }
.ppt-slide-content .dt-p3 th, .ppt-slide-content .dt-p3 td {
    padding: 1px 3px !important; font-size: 9px !important; height: auto !important;
}
.ppt-slide-content .dashboard-table th, .ppt-slide-content .dashboard-table td {
    padding: 1px 3px !important; font-size: 9px !important; height: auto !important; line-height: 1.1 !important;
}
.ppt-slide-content .metric-table th, .ppt-slide-content .metric-table td {
    padding: 1px 3px !important; font-size: 9px !important; height: auto !important; line-height: 1.1 !important;
}
.ppt-slide-content .brand-table th, .ppt-slide-content .brand-table td {
    padding: 1px 2px !important; font-size: 8px !important; height: auto !important; line-height: 1.1 !important;
}
.ppt-slide-content .brand-table tr, .ppt-slide-content .brand-table { height: auto !important; }
.ppt-slide-content .growth-table th, .ppt-slide-content .growth-table td {
    padding: 1px 2px !important; font-size: 8px !important; height: auto !important;
}

/* ===== Headers/overlays ===== */
.ppt-slide-content .phdr { padding: 2px 8px !important; }
.ppt-slide-content .phdr h2 { font-size: 10px !important; line-height: 1.2 !important; margin: 0 !important; }
.ppt-slide-content .partb-header { padding: 2px 8px !important; margin: 0 !important; font-size: 10px !important; }
.ppt-slide-content .time-selector-wrap, .ppt-slide-content .cat-selector-wrap {
    margin: 0 !important; padding: 1px 6px !important;
}

/* ===== CONCLUSION BOXES: smaller font + tighter line-height ===== */
/* Title "结论 (26M6)" */
.ppt-slide-content div[style*="font-size:20px;font-weight:700;color:#9A5B00"] {
    font-size: 11px !important; margin-bottom: 1px !important; padding-left: 2px !important;
}
/* Conclusion content box (gold gradient) */
.ppt-slide-content div[style*="background:linear-gradient(135deg,#FFFBF0"] {
    padding: 4px 8px !important; font-size: 10px !important; line-height: 1.3 !important;
    border-radius: 4px !important; border-width: 1px !important;
}
/* Conclusion text area */
.ppt-slide-content [data-testid="stTextArea"] textarea {
    font-size: 10px !important; line-height: 1.3 !important;
}
.ppt-slide-content [data-testid="stTextArea"] {
    padding: 4px 8px !important;
}
/* Conclusion paragraph spacing */
.ppt-slide-content div[style*="margin-top:8px"],
.ppt-slide-content div[style*="margin-top: 8px"] {
    margin-top: 2px !important;
}
/* Markup spans inside conclusions */
.ppt-slide-content span[style*="font-size:1.1em"] { font-size: 11px !important; }
.ppt-slide-content span[style*="font-size:0.85em"] { font-size: 8.5px !important; }

/* ===== Tabs: smaller ===== */
.ppt-slide-content .stTabs [data-baseweb="tab"] {
    padding: 1px 6px !important; font-size: 10px !important; height: auto !important;
}

/* ===== stMetric ===== */
.ppt-slide-content [data-testid="stMetric"] { padding: 2px 4px !important; }
.ppt-slide-content [data-testid="stMetricLabel"] { font-size: 9px !important; }
.ppt-slide-content [data-testid="stMetricValue"] { font-size: 12px !important; }

/* ===== Selectbox ===== */
.ppt-slide-content [data-testid="stSelectbox"] > div > div {
    min-height: 24px !important; padding: 0 6px !important; font-size: 10px !important;
}

/* ===== Print ===== */
@media print {
    @page { size: 338.7mm 190.5mm; margin: 0; }
    body { background: white !important; }
    [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"],
    footer, #st-bottom, .stDeployButton, .ppt-slide-title, button { display: none !important; }
    .ppt-slide-16x9 {
        page-break-after: always; page-break-inside: avoid;
        border: none !important; box-shadow: none !important; border-radius: 0 !important;
        margin: 0 !important; width: 338.7mm !important; height: 190.5mm !important;
        aspect-ratio: auto !important; max-width: none !important; overflow: hidden !important;
    }
    .ppt-slide-content { width: 100% !important; height: 100% !important; }
}
</style>
"""

_JS = r"""
<script>
(function() {
    var doc;
    try { doc = window.parent.document; } catch(e) { doc = document; }
    var runCount = 0;
    var MAX_RUNS = 30;

    function wrapSlides() {
        if (runCount >= MAX_RUNS) return;
        runCount++;
        var markers = doc.querySelectorAll('.slide-marker-start:not([data-wrapped="true"])');
        if (markers.length === 0) {
            if (runCount < MAX_RUNS) setTimeout(wrapSlides, 400);
            return;
        }

        var md = [];
        for (var i = 0; i < markers.length; i++) {
            var m = markers[i];
            var w = m.closest('[data-testid="stMarkdown"]') || m.parentElement;
            var bc = w, s = 0;
            while (bc && bc.parentElement && bc.parentElement.getAttribute &&
                   bc.parentElement.getAttribute('data-testid') !== 'stVerticalBlock' &&
                   bc.parentElement.getAttribute('data-testid') !== 'stMainBlockContainer' && s < 15) {
                bc = bc.parentElement; s++;
            }
            md.push({ m: m, w: w, bc: bc, t: m.getAttribute('data-title')||'', p: m.getAttribute('data-page')||'0' });
        }

        for (var i = 0; i < md.length; i++) {
            var d = md[i];
            if (d.m.getAttribute('data-wrapped') === 'true') continue;
            var sn = d.bc; if (!sn) continue;
            var bp = sn.parentElement; if (!bp) continue;
            var nbc = (i+1 < md.length) ? md[i+1].bc : null;

            var slide = doc.createElement('div');
            slide.className = 'ppt-slide-16x9';
            slide.setAttribute('data-slide-num', d.p);
            if (d.t) { var lb = doc.createElement('div'); lb.className='ppt-slide-title'; lb.textContent=d.t; slide.appendChild(lb); }
            var content = doc.createElement('div');
            content.className = 'ppt-slide-content';
            slide.appendChild(content);

            var node = sn.nextElementSibling;
            while (node && node !== nbc) { var nx = node.nextElementSibling; content.appendChild(node); node = nx; }
            if (nbc) bp.insertBefore(slide, nbc); else bp.appendChild(slide);
            if (d.w && d.w !== bp) d.w.remove();
            else if (sn && sn.parentElement === bp) sn.remove();
            d.m.setAttribute('data-wrapped', 'true');
        }

        var ems = doc.querySelectorAll('.slide-marker-end');
        ems.forEach(function(e) { var w = e.closest('[data-testid="stMarkdown"]') || e.parentElement; if (w) w.remove(); });

        if (runCount < MAX_RUNS) setTimeout(wrapSlides, 400);
    }

    setTimeout(wrapSlides, 800);
})();
</script>
"""


def apply_layout():
    global _page_count
    _page_count = 0
    st.markdown(_CSS, unsafe_allow_html=True)
    components.html(_JS, height=0)


def page_start(title=""):
    global _page_count
    _page_count += 1
    st.markdown(
        f'<div class="slide-marker-start" data-title="{title}" data-page="{_page_count}"></div>',
        unsafe_allow_html=True,
    )


def page_end():
    st.markdown('<div class="slide-marker-end"></div>', unsafe_allow_html=True)
