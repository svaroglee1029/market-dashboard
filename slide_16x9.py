"""
slide_16x9.py v2

16:9 slide layout with content auto-scaling.
Each page is wrapped in a 16:9 container (338.7mm x 190.5mm for print).
JS measures content height and applies transform: scale() to fit.

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
    max-width: calc((100vh - 60px) * 16 / 9);
    margin: 6px auto;
    overflow: hidden;
    position: relative;
    background: white;
    border: 1px solid #d0d5dd;
    border-radius: 4px;
    box-shadow: 0 1px 8px rgba(0,0,0,0.05);
}

/* Slide title label */
.ppt-slide-title {
    position: absolute;
    top: 2px;
    left: 10px;
    font-size: 10px;
    color: #94A3B8;
    font-weight: 600;
    z-index: 100;
    pointer-events: none;
    letter-spacing: 1px;
}

/* ===== Content wrapper: scaled by JS ===== */
.ppt-slide-content {
    width: 100%;
    height: 100%;
    transform-origin: top left;
    overflow: hidden;
    position: relative;
}

/* ===== Adapt content inside slides ===== */
/* Reduce Streamlit block gaps inside slides */
.ppt-slide-content [data-testid="stVerticalBlock"] {
    gap: 0.3rem !important;
}
.ppt-slide-content [data-testid="stVerticalBlock"] > div {
    padding-top: 0.2rem !important;
    padding-bottom: 0.2rem !important;
}

/* Streamlit main container inside slides */
.ppt-slide-content .main .block-container,
.ppt-slide-content .block-container {
    padding: 0.2rem 0.5rem !important;
    max-width: 100% !important;
}

/* Reduce markdown element spacing */
.ppt-slide-content [data-testid="stMarkdown"] {
    margin: 0 !important;
    padding: 0 !important;
}
.ppt-slide-content [data-testid="stMarkdown"] > div {
    margin: 0 !important;
    padding: 0 !important;
}
.ppt-slide-content p {
    margin: 2px 0 !important;
}
.ppt-slide-content hr {
    margin: 2px 0 !important;
    border: none !important;
    border-top: 1px solid #E4E9F0 !important;
}

/* Plotly charts: full width, reduce container padding */
.ppt-slide-content [data-testid="stPlotlyChart"] {
    margin: 0 !important;
    padding: 0 !important;
}
.ppt-slide-content .stPlotlyChart,
.ppt-slide-content div[data-testid="stPlotlyChart"] > div {
    margin: 0 !important;
    padding: 0 !important;
    height: auto !important;
}

/* Streamlit columns: reduce gap */
.ppt-slide-content [data-testid="stHorizontalBlock"] {
    gap: 0.3rem !important;
}
.ppt-slide-content [data-testid="stHorizontalBlock"] > div {
    padding-left: 0.2rem !important;
    padding-right: 0.2rem !important;
}

/* Tables: reduce cell padding inside slides */
.ppt-slide-content .dt,
.ppt-slide-content .dt-p2,
.ppt-slide-content .dt-p3,
.ppt-slide-content .dashboard-table,
.ppt-slide-content .metric-table,
.ppt-slide-content .brand-table,
.ppt-slide-content .growth-table {
    font-size: 11px !important;
}
.ppt-slide-content .dt th,
.ppt-slide-content .dt td {
    padding: 3px 5px !important;
    height: auto !important;
    font-size: 11px !important;
}
.ppt-slide-content .dt-p2 th,
.ppt-slide-content .dt-p2 td {
    padding: 3px 5px !important;
    height: auto !important;
    font-size: 11px !important;
}
.ppt-slide-content .dt-p2,
.ppt-slide-content .dt-p2 tr {
    height: auto !important;
}
.ppt-slide-content .dashboard-table th,
.ppt-slide-content .dashboard-table td {
    padding: 3px 4px !important;
    font-size: 11px !important;
}
.ppt-slide-content .metric-table th,
.ppt-slide-content .metric-table td {
    padding: 3px 5px !important;
    font-size: 11px !important;
}
.ppt-slide-content .brand-table th,
.ppt-slide-content .brand-table td {
    padding: 2px 4px !important;
    font-size: 10px !important;
    height: auto !important;
}
.ppt-slide-content .brand-table tr {
    height: auto !important;
}
.ppt-slide-content .growth-table th,
.ppt-slide-content .growth-table td {
    padding: 2px 4px !important;
    font-size: 10px !important;
}

/* Reduce header/overview area padding */
.ppt-slide-content .phdr {
    padding: 3px 12px !important;
}
.ppt-slide-content .partb-header {
    padding: 3px 12px !important;
    margin: 0 !important;
}
.ppt-slide-content .time-selector-wrap {
    margin: 0 !important;
    padding: 2px 8px !important;
}
.ppt-slide-content .cat-selector-wrap {
    margin: 0 !important;
    padding: 2px 8px !important;
}

/* Conclusion boxes: reduce padding */
.ppt-slide-content .conclusion-box {
    padding: 4px 8px !important;
    margin: 2px 0 !important;
}

/* Tab buttons: smaller */
.ppt-slide-content .stTabs [data-baseweb="tab"] {
    padding: 2px 8px !important;
    font-size: 12px !important;
}

/* ===== Print: 338.7mm x 190.5mm ===== */
@media print {
    @page {
        size: 338.7mm 190.5mm;
        margin: 0;
    }

    body { background: white !important; }

    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    footer, #st-bottom, .stDeployButton,
    .ppt-slide-title,
    button { display: none !important; }

    .ppt-slide-16x9 {
        page-break-after: always;
        page-break-inside: avoid;
        border: none !important;
        box-shadow: none !important;
        border-radius: 0 !important;
        margin: 0 !important;
        width: 338.7mm !important;
        height: 190.5mm !important;
        aspect-ratio: auto !important;
        max-width: none !important;
        overflow: hidden !important;
    }

    .ppt-slide-content {
        transform: none !important;
        width: 100% !important;
        height: 100% !important;
    }
}
</style>
"""

_JS = r"""
<script>
(function() {
    var doc;
    try {
        doc = window.parent.document;
    } catch(e) {
        doc = document;
    }

    var runCount = 0;
    var MAX_RUNS = 30;
    var scaleRunCount = 0;
    var MAX_SCALE_RUNS = 30;

    function wrapSlides() {
        if (runCount >= MAX_RUNS) return;
        runCount++;

        var markers = doc.querySelectorAll('.slide-marker-start:not([data-wrapped="true"])');
        if (markers.length === 0) {
            if (runCount < MAX_RUNS) {
                setTimeout(wrapSlides, 500);
            }
            return;
        }

        var markerData = [];
        for (var i = 0; i < markers.length; i++) {
            var m = markers[i];
            var wrapper = m.closest('[data-testid="stMarkdown"]') || m.parentElement;
            var blockChild = wrapper;
            var safety = 0;
            while (blockChild && blockChild.parentElement &&
                   blockChild.parentElement.getAttribute &&
                   blockChild.parentElement.getAttribute('data-testid') !== 'stVerticalBlock' &&
                   blockChild.parentElement.getAttribute('data-testid') !== 'stMainBlockContainer' &&
                   safety < 15) {
                blockChild = blockChild.parentElement;
                safety++;
            }
            markerData.push({
                marker: m,
                wrapper: wrapper,
                blockChild: blockChild,
                title: m.getAttribute('data-title') || '',
                pageNum: m.getAttribute('data-page') || '0'
            });
        }

        for (var i = 0; i < markerData.length; i++) {
            var data = markerData[i];
            if (data.marker.getAttribute('data-wrapped') === 'true') continue;

            var startNode = data.blockChild;
            if (!startNode) continue;

            var blockParent = startNode.parentElement;
            if (!blockParent) continue;

            var nextBlockChild = null;
            if (i + 1 < markerData.length) {
                nextBlockChild = markerData[i + 1].blockChild;
            }

            var slide = doc.createElement('div');
            slide.className = 'ppt-slide-16x9';
            slide.setAttribute('data-slide-num', data.pageNum);

            if (data.title) {
                var label = doc.createElement('div');
                label.className = 'ppt-slide-title';
                label.textContent = data.title;
                slide.appendChild(label);
            }

            var content = doc.createElement('div');
            content.className = 'ppt-slide-content';
            slide.appendChild(content);

            var node = startNode.nextElementSibling;
            while (node && node !== nextBlockChild) {
                var next = node.nextElementSibling;
                content.appendChild(node);
                node = next;
            }

            if (nextBlockChild) {
                blockParent.insertBefore(slide, nextBlockChild);
            } else {
                blockParent.appendChild(slide);
            }

            if (data.wrapper && data.wrapper !== blockParent) {
                data.wrapper.remove();
            } else if (startNode && startNode.parentElement === blockParent) {
                startNode.remove();
            }

            data.marker.setAttribute('data-wrapped', 'true');
        }

        var endMarkers = doc.querySelectorAll('.slide-marker-end');
        endMarkers.forEach(function(e) {
            var wrapper = e.closest('[data-testid="stMarkdown"]') || e.parentElement;
            if (wrapper) wrapper.remove();
        });

        // Start scaling after wrapping
        setTimeout(scaleSlides, 100);

        if (runCount < MAX_RUNS) {
            setTimeout(wrapSlides, 500);
        }
    }

    function scaleSlides() {
        var slides = doc.querySelectorAll('.ppt-slide-16x9');
        for (var i = 0; i < slides.length; i++) {
            var slide = slides[i];
            var content = slide.querySelector('.ppt-slide-content');
            if (!content) continue;

            // Reset previous scale
            content.style.transform = 'none';
            content.style.width = '100%';

            // Wait for layout
            var slideH = slide.clientHeight;
            if (slideH < 10) continue;

            // Measure content natural height
            // Temporarily set height to auto to measure
            var savedH = content.style.height;
            content.style.height = 'auto';
            var contentH = content.scrollHeight;
            content.style.height = savedH || '100%';

            if (contentH < 10) continue;

            // Calculate scale
            var scale = slideH / contentH;
            
            // Only scale down, never scale up beyond 1.0
            if (scale < 0.98) {
                content.style.transform = 'scale(1, ' + scale + ')';
                content.style.transformOrigin = 'top left';
                // Adjust width to compensate for vertical scale
                content.style.width = (100 / scale * 1) + '%';
                // But this makes content wider, so also scale X
                // Better: use uniform scale
                content.style.transform = 'scale(' + scale + ')';
                content.style.width = (100 / scale) + '%';
            } else {
                content.style.transform = 'none';
                content.style.width = '100%';
            }
        }

        // Re-run to catch charts that finished loading
        scaleRunCount++;
        if (scaleRunCount < MAX_SCALE_RUNS) {
            setTimeout(scaleSlides, 500);
        }
    }

    // Start after Streamlit renders
    setTimeout(wrapSlides, 1000);

    // Run scaling on window resize
    window.addEventListener('resize', function() {
        scaleRunCount = 0;
        setTimeout(scaleSlides, 200);
    });

    // Run before printing
    window.addEventListener('beforeprint', function() {
        runCount = 0;
        scaleRunCount = 0;
        wrapSlides();
        setTimeout(function() {
            // For print: remove transform, let CSS handle it
            var slides = doc.querySelectorAll('.ppt-slide-16x9');
            slides.forEach(function(slide) {
                var content = slide.querySelector('.ppt-slide-content');
                if (content) {
                    content.style.transform = 'none';
                    content.style.width = '100%';
                }
            });
        }, 500);
    });
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
