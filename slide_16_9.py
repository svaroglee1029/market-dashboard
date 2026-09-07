"""
slide_16_9.py

16:9 PPT-style slide layout for Streamlit dashboard.

Each page section is displayed as a 16:9 aspect ratio slide with all
content auto-scaled to fit on one screen without pagination.

Usage in dashboard.py:
    from slide_16_9 import apply_layout, page_start, page_end

    # Call once after st.set_page_config
    apply_layout()

    # Wrap each page:
    page_start("Page 1")
    page1(sel_ym, sel_m)
    page_end()
"""

import streamlit as st
import streamlit.components.v1 as components

# ===================== CSS =====================
_CSS = r"""
<style>
/* ====== Global: hide Streamlit chrome that shows URLs etc. ====== */
footer { display: none !important; }
#st-bottom { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
/* Hide the "Made with Streamlit" + URL footer */
[class^="stViewer"] [class*="footer"] { display: none !important; }
/* Hide any auto-generated link text containing https */
a[href*="streamlit.app"] { display: none !important; }
/* Hide the components iframe used for JS */
iframe[title="streamlit_slideshow_js"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    border: none !important;
}

/* ====== Slide layout ====== */
/* Each slide is a 16:9 container with hidden overflow */
.ppt-slide-16x9 {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: #FFFFFF;
    border: 2px solid #00B050;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    margin: 0 auto 12px;
}
/* Inner content: absolute positioned to fill slide, scaled by JS */
.ppt-slide-inner-16x9 {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    transform-origin: top left;
    padding: 6px;
    box-sizing: border-box;
}
/* Markers are invisible anchors */
.slide-marker-16x9 {
    display: none !important;
}
/* Slide label */
.ppt-slide-label-16x9 {
    font-size: 12px;
    color: #94A3B8;
    font-weight: 600;
    text-align: center;
    margin: 0 0 4px;
    letter-spacing: 1px;
}

/* Make Streamlit elements inside slides not add extra margin */
.ppt-slide-inner-16x9 > div {
    margin-bottom: 0 !important;
}
.ppt-slide-inner-16x9 .stMarkdown {
    margin-bottom: 0 !important;
}

/* ====== Print: force each slide to a separate page ====== */
@media print {
    /* Hide all Streamlit chrome, sidebars, buttons */
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    [data-testid="stHeader"],
    footer,
    #st-bottom,
    .stDeployButton,
    .ppt-slide-label-16x9,
    iframe[title="streamlit_slideshow_js"],
    .streamlit-expainer,
    button {
        display: none !important;
    }

    /* Reset page margins */
    @page {
        size: landscape;
        margin: 0;
    }

    /* Each slide = one printed page */
    .ppt-slide-16x9 {
        width: 100vw;
        height: 100vh;
        aspect-ratio: unset;
        page-break-after: always;
        break-after: page;
        page-break-inside: avoid;
        break-inside: avoid;
        border: none;
        box-shadow: none;
        margin: 0;
        border-radius: 0;
        overflow: hidden;
    }
    .ppt-slide-16x9:last-child {
        page-break-after: auto;
        break-after: auto;
    }

    /* Fill the page */
    .ppt-slide-inner-16x9 {
        width: 100vw !important;
        height: 100vh !important;
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

    // ====== Core: wrap markers into slides ======
    function wrapSlides() {
        var starts = doc.querySelectorAll('.slide-marker-16x9[data-slide="start"]');
        for (var i = 0; i < starts.length; i++) {
            var start = starts[i];
            if (processed.has(start)) continue;

            // Walk up to find the main Streamlit content container
            // Markers are inside <div data-testid="stVerticalBlock">
            // We need to grab all sibling elements between start and end markers
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

            // Get parent and collect elements between markers
            var parent = start.parentElement;
            var children = Array.from(parent.children);
            var si = children.indexOf(start);
            var ei = children.indexOf(end);
            if (si < 0 || ei < 0 || ei <= si) continue;

            // Create slide wrapper
            var slide = doc.createElement('div');
            slide.className = 'ppt-slide-16x9';

            var inner = doc.createElement('div');
            inner.className = 'ppt-slide-inner-16x9';

            // Move content elements to inner container
            var elems = children.slice(si + 1, ei);
            for (var j = 0; j < elems.length; j++) {
                inner.appendChild(elems[j]);
            }

            slide.appendChild(inner);
            parent.insertBefore(slide, end);

            // Auto-scale content to fit
            autoScale(slide, inner);
            processed.add(start);
            processed.add(end);
        }
    }

    // ====== Auto-scale: shrink content to fit 16:9 slide ======
    function autoScale(slide, inner) {
        var sw = slide.clientWidth;
        var sh = slide.clientHeight;
        if (sw === 0 || sh === 0) {
            setTimeout(function() { autoScale(slide, inner); }, 300);
            return;
        }

        // Reset to measure natural size
        inner.style.transform = 'none';
        inner.style.width = sw + 'px';

        // Force reflow
        void inner.offsetHeight;

        // Measure natural content height
        var ch = inner.scrollHeight;
        var cw = inner.scrollWidth;

        if (ch === 0 || cw === 0) {
            setTimeout(function() { autoScale(slide, inner); }, 500);
            return;
        }

        // Scale down to fit (never scale up beyond 1)
        var scaleX = sw / cw;
        var scaleY = sh / ch;
        var scale = Math.min(scaleX, scaleY, 1);

        inner.style.transform = 'scale(' + scale + ')';
        inner.style.width = (sw / scale) + 'px';

        // If content is shorter than slide, center vertically
        var scaledHeight = ch * scale;
        if (scaledHeight < sh) {
            var offsetY = (sh - scaledHeight) / 2;
            inner.style.top = offsetY + 'px';
        } else {
            inner.style.top = '0px';
        }
    }

    // ====== Rescale all slides ======
    function rescaleAll() {
        var slides = doc.querySelectorAll('.ppt-slide-16x9');
        for (var i = 0; i < slides.length; i++) {
            var inner = slides[i].querySelector('.ppt-slide-inner-16x9');
            if (inner) autoScale(slides[i], inner);
        }
    }

    // ====== Debounce helper ======
    function debounce(fn, delay) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fn, delay);
    }

    // ====== Init ======
    // Multiple retries because Streamlit/Plotly render asynchronously
    function initSlides() {
        wrapSlides();
        rescaleAll();
    }

    // Run on load
    if (doc.readyState === 'complete') {
        setTimeout(initSlides, 200);
        setTimeout(initSlides, 800);
        setTimeout(initSlides, 2000);
        setTimeout(initSlides, 4000);
        setTimeout(initSlides, 6000);
    } else {
        win.addEventListener('load', function() {
            setTimeout(initSlides, 200);
            setTimeout(initSlides, 800);
            setTimeout(initSlides, 2000);
            setTimeout(initSlides, 4000);
            setTimeout(initSlides, 6000);
        });
    }

    // Re-scale on resize
    win.addEventListener('resize', function() {
        debounce(rescaleAll, 250);
    });

    // Re-scale before print (each slide fills a full landscape page)
    win.addEventListener('beforeprint', function() {
        // Reset transforms so content uses natural size for print
        var inners = doc.querySelectorAll('.ppt-slide-inner-16x9');
        for (var i = 0; i < inners.length; i++) {
            inners[i].style.transform = 'none';
            inners[i].style.width = '100vw';
            inners[i].style.top = '0px';
        }
        // Re-scale to fit full page (not 16:9 aspect-ratio)
        setTimeout(function() {
            var slides = doc.querySelectorAll('.ppt-slide-16x9');
            for (var i = 0; i < slides.length; i++) {
                var inner = slides[i].querySelector('.ppt-slide-inner-16x9');
                if (!inner) continue;
                var sw = win.innerWidth;
                var sh = win.innerHeight;
                inner.style.transform = 'none';
                inner.style.width = sw + 'px';
                void inner.offsetHeight;
                var ch = inner.scrollHeight;
                var cw = inner.scrollWidth;
                if (ch === 0) continue;
                var scale = Math.min(sw / cw, sh / ch, 1);
                inner.style.transform = 'scale(' + scale + ')';
                inner.style.width = (sw / scale) + 'px';
                var scaledH = ch * scale;
                if (scaledH < sh) {
                    inner.style.top = ((sh - scaledH) / 2) + 'px';
                }
            }
        }, 100);
    });

    // Restore screen layout after print
    win.addEventListener('afterprint', function() {
        rescaleAll();
    });

    // Watch for DOM changes (Streamlit re-renders on interaction)
    var observer = new MutationObserver(function() {
        debounce(function() {
            wrapSlides();
            rescaleAll();
        }, 500);
    });

    function startObserver() {
        var body = doc.querySelector('body');
        if (body) {
            observer.observe(body, { childList: true, subtree: true });
        } else {
            setTimeout(startObserver, 100);
        }
    }
    startObserver();
})();
</script>
"""


def apply_layout():
    """
    Inject CSS and JavaScript for 16:9 slide layout.
    Call this once after st.set_page_config().
    """
    st.markdown(_CSS, unsafe_allow_html=True)
    components.html(_JS, height=0, width=0)


def page_start(title=""):
    """
    Insert a slide start marker.
    Call this before each page's content.
    """
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
    """
    Insert a slide end marker.
    Call this after each page's content.
    """
    st.markdown(
        '<div class="slide-marker-16x9" data-slide="end"></div>',
        unsafe_allow_html=True,
    )
