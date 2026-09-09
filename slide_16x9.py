"""
slide_16x9.py

Improved 16:9 slide layout for Streamlit dashboard.
Each page is wrapped in a 16:9 container (338.7mm x 190.5mm).
Uses lightweight JS (setTimeout, no MutationObserver) to wrap content.

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

/* Markers are invisible on screen */
.slide-marker-start, .slide-marker-end {
    display: none !important;
}

/* 16:9 slide container */
.ppt-slide-16x9 {
    width: 100%;
    aspect-ratio: 16 / 9;
    max-width: calc((100vh - 80px) * 16 / 9);
    margin: 10px auto;
    overflow: hidden;
    position: relative;
    background: white;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}

/* Slide title label */
.ppt-slide-title {
    position: absolute;
    top: 4px;
    left: 12px;
    font-size: 11px;
    color: #94A3B8;
    font-weight: 600;
    z-index: 100;
    pointer-events: none;
    letter-spacing: 1px;
}

/* Content inside slide scales to fit */
.ppt-slide-content {
    width: 100%;
    height: 100%;
    transform-origin: top left;
    overflow: hidden;
}

/* Print: 16:9 page size = 338.7mm x 190.5mm */
@media print {
    @page {
        size: 338.7mm 190.5mm;
        margin: 0;
    }

    body { background: white !important; }

    /* Hide all Streamlit UI elements */
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stAppViewBlockContainer"] > *:not(div[data-testid="stMainBlockContainer"]),
    footer, #st-bottom, .stDeployButton,
    .ppt-slide-title,
    button { display: none !important; }

    /* Each slide is one print page */
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

    /* Remove gap between elements inside slides */
    .ppt-slide-content > * {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
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
    var MAX_RUNS = 20;

    function wrapSlides() {
        if (runCount >= MAX_RUNS) return;
        runCount++;

        var markers = doc.querySelectorAll('.slide-marker-start:not([data-wrapped="true"])');
        if (markers.length === 0) {
            if (runCount < MAX_RUNS) {
                setTimeout(wrapSlides, 600);
            }
            return;
        }

        // Collect all markers and find their Streamlit wrappers
        var markerData = [];
        for (var i = 0; i < markers.length; i++) {
            var m = markers[i];
            // Find the closest Streamlit element wrapper (stMarkdown, stVerticalBlock child, etc.)
            var wrapper = m.closest('[data-testid="stMarkdown"]') || m.parentElement;
            // Walk up to find the direct child of stVerticalBlock or main container
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

            // Find the parent block
            var blockParent = startNode.parentElement;
            if (!blockParent) continue;

            // Find the next marker's blockChild
            var nextBlockChild = null;
            if (i + 1 < markerData.length) {
                nextBlockChild = markerData[i + 1].blockChild;
            }

            // Create slide container
            var slide = doc.createElement('div');
            slide.className = 'ppt-slide-16x9';
            slide.setAttribute('data-slide-num', data.pageNum);

            // Add title label
            if (data.title) {
                var label = doc.createElement('div');
                label.className = 'ppt-slide-title';
                label.textContent = data.title;
                slide.appendChild(label);
            }

            // Create content wrapper
            var content = doc.createElement('div');
            content.className = 'ppt-slide-content';
            slide.appendChild(content);

            // Move all siblings between startNode and nextBlockChild into content
            var node = startNode.nextElementSibling;
            var moved = 0;
            while (node && node !== nextBlockChild) {
                var next = node.nextElementSibling;
                content.appendChild(node);
                moved++;
                node = next;
            }

            if (moved > 0 || true) {
                // Insert slide where startNode was
                if (nextBlockChild) {
                    blockParent.insertBefore(slide, nextBlockChild);
                } else {
                    blockParent.appendChild(slide);
                }
            }

            // Remove the marker wrapper (stMarkdown that contained the marker)
            if (data.wrapper && data.wrapper !== blockParent) {
                data.wrapper.remove();
            } else if (startNode && startNode.parentElement === blockParent) {
                startNode.remove();
            }

            // Mark marker as wrapped
            data.marker.setAttribute('data-wrapped', 'true');
        }

        // Clean up end markers
        var endMarkers = doc.querySelectorAll('.slide-marker-end');
        endMarkers.forEach(function(e) {
            var wrapper = e.closest('[data-testid="stMarkdown"]') || e.parentElement;
            if (wrapper) wrapper.remove();
        });

        // Schedule next run to catch dynamic content
        if (runCount < MAX_RUNS) {
            setTimeout(wrapSlides, 600);
        }
    }

    // Start after Streamlit renders initial content
    setTimeout(wrapSlides, 1200);

    // Also run before printing
    window.addEventListener('beforeprint', function() {
        runCount = 0;
        wrapSlides();
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
