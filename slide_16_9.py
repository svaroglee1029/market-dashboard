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

    page_start("Page 2")
    page2(sel_ym, sel_m)
    page_end()
"""

import streamlit as st
import streamlit.components.v1 as components

# ===================== CSS =====================
_CSS = """
<style>
/* Slide container: 16:9 aspect ratio, fills viewport width */
.ppt-slide-16x9 {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: #FFFFFF;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    margin: 0 auto 16px;
}
/* Inner content wrapper for scaling */
.ppt-slide-inner-16x9 {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    transform-origin: top left;
    padding: 8px;
    box-sizing: border-box;
}
/* Hide markers (they are just anchors for JS) */
.slide-marker-16x9 {
    display: none !important;
}
/* Optional slide label above each slide */
.ppt-slide-label-16x9 {
    font-size: 12px;
    color: #94A3B8;
    font-weight: 600;
    text-align: center;
    margin: 0 0 6px;
    letter-spacing: 1px;
}
/* Hide the components.html iframe used for JS injection */
iframe[title="streamlit_slideshow_js"] {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    border: none !important;
}
</style>
"""

# ===================== JavaScript =====================
_JS = """
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

            // Find matching end marker (next sibling)
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

    function autoScale(slide, inner) {
        var sw = slide.clientWidth;
        var sh = slide.clientHeight;

        // Reset to measure natural size
        inner.style.transform = 'none';
        inner.style.width = sw + 'px';

        // Wait for content to render, then measure
        var ch = inner.scrollHeight;
        var cw = inner.scrollWidth;

        if (ch === 0 || cw === 0) {
            // Content not ready, retry
            setTimeout(function() { autoScale(slide, inner); }, 500);
            return;
        }

        var scaleX = sw / cw;
        var scaleY = sh / ch;
        var scale = Math.min(scaleX, scaleY, 1);

        inner.style.transform = 'scale(' + scale + ')';
        // Adjust width to compensate for scaling
        inner.style.width = (sw / scale) + 'px';
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

    // Initial wrapping with retries for Streamlit/Plotly rendering
    win.addEventListener('load', function() {
        setTimeout(function() { wrapSlides(); rescaleAll(); }, 500);
        setTimeout(function() { wrapSlides(); rescaleAll(); }, 1500);
        setTimeout(function() { wrapSlides(); rescaleAll(); }, 3000);
        setTimeout(function() { wrapSlides(); rescaleAll(); }, 5000);
    });

    // Re-scale on resize (debounced)
    win.addEventListener('resize', function() {
        debounce(rescaleAll, 200);
    });

    // Watch for DOM changes (Streamlit re-renders)
    var observer = new MutationObserver(function() {
        debounce(function() {
            wrapSlides();
            rescaleAll();
        }, 300);
    });

    // Start observing when DOM is ready
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

    Args:
        title: Optional label displayed above the slide (e.g., "Page 1: Market Overview")
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
