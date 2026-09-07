"""
slide_16_9.py

16:9 PPT-style slide layout for Streamlit dashboard.

Two modes:
  - Screen: JS wraps content into 16:9 aspect-ratio containers with auto-scaling
  - Print: CSS page-break on markers forces each section to its own page

Usage in dashboard.py:
    from slide_16_9 import apply_layout, page_start, page_end

    apply_layout()

    page_start("Page 1")
    page1(sel_ym, sel_m)
    page_end()

    page_start("Page 2")
    page2(sel_ym, sel_m)
    page_end()
"""

import streamlit as st
import streamlit.components.v1 as components

# ===================== CSS =====================
_CSS = r"""
<style>
/* ====== Hide Streamlit chrome ====== */
footer { display: none !important; }
#st-bottom { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
a[href*="streamlit.app"] { display: none !important; }

/* Hide JS injection iframe */
iframe[title="streamlit_slideshow_js"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    border: none !important;
}

/* ====== Screen: 16:9 slide containers ====== */
.ppt-slide-16x9 {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: #FFFFFF;
    border: 2px solid #00B050;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    margin: 0 auto 12px;
}
.ppt-slide-inner-16x9 {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    transform-origin: top left;
    padding: 6px;
    box-sizing: border-box;
}
.slide-marker-16x9 { display: none !important; }
.ppt-slide-label-16x9 {
    font-size: 12px;
    color: #94A3B8;
    font-weight: 600;
    text-align: center;
    margin: 0 0 4px;
    letter-spacing: 1px;
}
.ppt-slide-inner-16x9 > div { margin-bottom: 0 !important; }
.ppt-slide-inner-16x9 .stMarkdown { margin-bottom: 0 !important; }

/* ====== Print: pure CSS page breaks on markers (no JS needed) ====== */
@media print {
    /* Hide all Streamlit UI */
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stHeader"],
    [data-testid="stAppViewBlockContainer"],
    footer, #st-bottom, .stDeployButton,
    .ppt-slide-label-16x9,
    iframe[title="streamlit_slideshow_js"],
    button { display: none !important; }

    @page {
        size: A4 landscape;
        margin: 1cm;
    }

    body { background: white !important; }

    /* The start marker itself becomes a page-break point.
       We use :before pseudo-element to force a page break. */
    .slide-marker-16x9[data-slide="start"] {
        display: block !important;
        page-break-before: always;
        break-before: page;
        height: 0;
        margin: 0;
        padding: 0;
        overflow: hidden;
        visibility: hidden;
    }
    /* First start marker: no break before (it's the first page) */
    .slide-marker-16x9[data-slide="start"]:first-of-type {
        page-break-before: avoid;
        break-before: avoid;
    }
    .slide-marker-16x9[data-slide="end"] {
        display: block !important;
        height: 0;
        margin: 0;
        padding: 0;
        overflow: hidden;
        visibility: hidden;
    }

    /* If JS wrapping succeeded, use slide containers for page breaks */
    .ppt-slide-16x9 {
        page-break-after: always;
        break-after: page;
        page-break-inside: avoid;
        break-inside: avoid;
        border: none;
        box-shadow: none;
        margin: 0;
        border-radius: 0;
        width: 100%;
        aspect-ratio: 16 / 9;
        overflow: hidden;
    }
    .ppt-slide-16x9:last-child {
        page-break-after: auto;
        break-after: auto;
    }
    .ppt-slide-inner-16x9 {
        width: 100% !important;
        height: 100% !important;
        transform: none !important;
    }

    /* Make sure all Streamlit content is visible in print */
    [data-testid="stVerticalBlock"],
    [data-testid="stAppViewContainer"] {
        overflow: visible !important;
        height: auto !important;
    }
}
</style>
"""

# ===================== JavaScript =====================
_JS = r"""
<script>
(function() {
    var doc = window.parent.document;
    var win = window.parent;
    var processed = new WeakSet();
    var debounceTimer = null;

    function wrapSlides() {
        var starts = doc.querySelectorAll('.slide-marker-16x9[data-slide="start"]');
        for (var i = 0; i < starts.length; i++) {
            var start = starts[i];
            if (processed.has(start)) continue;

            var end = null;
            var node = start.nextElementSibling;
            while (node) {
                if (node.classList && node.classList.contains('slide-marker-16x9')
                    && node.getAttribute('data-slide') === 'end') {
                    end = node;
                    break;
                }
                node = node.nextElementSibling;
            }
            if (!end) continue;

            var parent = start.parentElement;
            var children = Array.from(parent.children);
            var si = children.indexOf(start);
            var ei = children.indexOf(end);
            if (si < 0 || ei < 0 || ei <= si) continue;

            var slide = doc.createElement('div');
            slide.className = 'ppt-slide-16x9';
            var inner = doc.createElement('div');
            inner.className = 'ppt-slide-inner-16x9';

            var elems = children.slice(si + 1, ei);
            for (var j = 0; j < elems.length; j++) {
                inner.appendChild(elems[j]);
            }

            slide.appendChild(inner);
            parent.insertBefore(slide, end);

            autoScale(slide, inner);
            processed.add(start);
            processed.add(end);
        }
    }

    function autoScale(slide, inner) {
        var sw = slide.clientWidth;
        var sh = slide.clientHeight;
        if (sw === 0 || sh === 0) {
            setTimeout(function() { autoScale(slide, inner); }, 300);
            return;
        }
        inner.style.transform = 'none';
        inner.style.width = sw + 'px';
        void inner.offsetHeight;
        var ch = inner.scrollHeight;
        var cw = inner.scrollWidth;
        if (ch === 0 || cw === 0) {
            setTimeout(function() { autoScale(slide, inner); }, 500);
            return;
        }
        var scale = Math.min(sw / cw, sh / ch, 1);
        inner.style.transform = 'scale(' + scale + ')';
        inner.style.width = (sw / scale) + 'px';
        var scaledH = ch * scale;
        if (scaledH < sh) {
            inner.style.top = ((sh - scaledH) / 2) + 'px';
        } else {
            inner.style.top = '0px';
        }
    }

    function rescaleAll() {
        var slides = doc.querySelectorAll('.ppt-slide-16x9');
        for (var i = 0; i < slides.length; i++) {
            var inner = slides[i].querySelector('.ppt-slide-inner-16x9');
            if (inner) autoScale(slides[i], inner);
        }
    }

    function debounce(fn, delay) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fn, delay);
    }

    function initSlides() { wrapSlides(); rescaleAll(); }

    if (doc.readyState === 'complete') {
        [200,800,2000,4000,6000].forEach(function(t){ setTimeout(initSlides, t); });
    } else {
        win.addEventListener('load', function() {
            [200,800,2000,4000,6000].forEach(function(t){ setTimeout(initSlides, t); });
        });
    }

    win.addEventListener('resize', function() { debounce(rescaleAll, 250); });

    var observer = new MutationObserver(function() {
        debounce(function() { wrapSlides(); rescaleAll(); }, 500);
    });
    function startObserver() {
        var body = doc.querySelector('body');
        if (body) { observer.observe(body, {childList:true, subtree:true}); }
        else { setTimeout(startObserver, 100); }
    }
    startObserver();
})();
</script>
"""


def apply_layout():
    st.markdown(_CSS, unsafe_allow_html=True)
    components.html(_JS, height=0, width=0)


def page_start(title=""):
    if title:
        st.markdown(
            f'<div class="ppt-slide-label-16x9">{title}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        '<div class="slide-marker-16x9" data-slide="start"></div>',
        unsafe_allow_html=True,
    )


def page_end():
    st.markdown(
        '<div class="slide-marker-16x9" data-slide="end"></div>',
        unsafe_allow_html=True,
    )
