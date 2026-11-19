"""Interactive Streamlit Web App for Group 1 Automatic Document Scanner (PCC-IT-502).

Runs locally via `streamlit run app.py` and deploys directly from GitHub to
Streamlit Community Cloud. Supports one-click testing on all 7 real mobile phone
captures as well as custom photo uploads with a Full-Resolution Quality Inspector.
"""

import os
import cv2
import numpy as np
import pandas as pd
import streamlit as st

from src.scanner import scan_document

st.set_page_config(
    page_title="Automatic Document Scanner — Group 1 (PCC-IT-502)",
    page_icon="📄",
    layout="wide",
)

st.title("Automatic Document Scanner")
st.caption(
    "Haldia Institute of Technology • Dept. of IT • Image Processing (PCC-IT-502) • Group 1 (Roll Nos. 76–80)"
)

with st.expander("Pipeline Overview & Classical Image Processing Techniques", expanded=False):
    st.markdown(
        """
        1. **Pre-processing:** Aspect-ratio preserving resize (`700 px` height), grayscale & CIE `LAB` lightness extraction, `9×9` median smoothing, and **CLAHE** (`8×8` tiles).
        2. **Edge & Morphological Segmentation:** Multi-threshold Otsu foreground masks + **Otsu-guided Canny** edge detection + `9×9` morphological opening & `7×7` closing.
        3. **Boundary Extraction:** External contour tracing + **Ramer–Douglas–Peucker** 4-point polygon approximation scored by interior purity and Sobel edge gradient.
        4. **Perspective Rectification:** Canonical corner ordering (`TL, TR, BR, BL`) + **$3 \times 3$ projective homography** (`cv2.warpPerspective` with Lanczos4).
        5. **Shadow Removal & Enhancement:** Resolution-adaptive median background division + **Unsharp Masking** + **Adaptive Gaussian Thresholding**.
        """
    )

st.sidebar.header("1. Choose Input Source")
mode = st.sidebar.radio(
    "Select how to load a document image:",
    ["Built-in Real Mobile Captures (7 Photos)", "Upload Your Own Photo"],
)

bgr = None
img_label = ""

if mode == "Built-in Real Mobile Captures (7 Photos)":
    real_dir = "data/real_inputs"
    sample_options = {
        "1. Printed Report — Straight Overhead": os.path.join(real_dir, "1_mobile_straight.jpg"),
        "2. Printed Report — Tilted Right": os.path.join(real_dir, "2_mobile_tilted_right.jpg"),
        "3. Printed Report — Tilted Left": os.path.join(real_dir, "3_mobile_tilted_left.jpg"),
        "4. Printed Report — Full-Frame Close-up": os.path.join(real_dir, "4_mobile_closeup.jpg"),
        "5. Handwritten Notes — Op-Amp Circuit": os.path.join(real_dir, "5_handwritten_opamp_notes.jpg"),
        "6. Handwritten Notes — KCL & KVL Equations": os.path.join(real_dir, "6_handwritten_kcl_kvl_notes.jpg"),
        "7. Landscape Admit Card Instructions": os.path.join(real_dir, "7_landscape_admit_card.jpg"),
    }
    available = {k: v for k, v in sample_options.items() if os.path.exists(v)}
    if available:
        choice = st.sidebar.selectbox("Select a real mobile photo:", list(available.keys()))
        bgr = cv2.imread(available[choice])
        img_label = os.path.basename(available[choice])
    else:
        st.warning("Sample mobile captures not found in `data/real_inputs/`. Switch to 'Upload Your Own Photo'.")
else:
    uploaded = st.sidebar.file_uploader(
        "Upload a document photo (JPG / PNG / WEBP)", type=["jpg", "jpeg", "png", "webp"]
    )
    if uploaded is not None:
        file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
        bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        img_label = uploaded.name

if bgr is not None:
    res = scan_document(bgr, out_size=None)

    contour_vis = bgr.copy()
    thick = max(4, min(bgr.shape[:2]) // 180)
    rad = max(10, min(bgr.shape[:2]) // 70)
    cv2.polylines(contour_vis, [res["corners"].astype(np.int32)], True, (0, 220, 0), thick)
    for px, py in res["corners"]:
        cv2.circle(contour_vis, (int(px), int(py)), rad, (255, 40, 40), -1)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Input Resolution", f"{bgr.shape[1]} × {bgr.shape[0]} px")
    m2.metric("Rectified Resolution", f"{res['warped_color'].shape[1]} × {res['warped_color'].shape[0]} px")
    m3.metric("Processing Latency", f"{res['processing_time_ms']:.1f} ms")
    m4.metric("Contrast Gain", f"{np.std(res['norm_gray']) / max(1e-6, np.std(res['warped_gray'])):.2f}×")

    st.subheader("Step-by-Step Visual Comparison")
    c1, c2, c3, c4 = st.columns(4)
    c1.image(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), caption="1. Original Mobile Photo", use_container_width=True)
    c2.image(cv2.cvtColor(contour_vis, cv2.COLOR_BGR2RGB), caption="2. Detected 4-Point Contour", use_container_width=True)
    c3.image(cv2.cvtColor(res["warped_color"], cv2.COLOR_BGR2RGB), caption="3. Perspective-Warped Color", use_container_width=True)
    c4.image(res["scanned_binary"], caption="4. Final Adaptive Binary Scan", use_container_width=True)

    st.subheader("Full-Resolution Quality Inspector")
    view_mode = st.radio(
        "Inspect full-width scan output:",
        ["Enhanced Grayscale (Anti-Aliased)", "Adaptive Binary Scan", "Perspective-Warped Color"],
        horizontal=True,
    )
    if view_mode == "Enhanced Grayscale (Anti-Aliased)":
        st.image(res["enhanced_scan"], use_container_width=True)
    elif view_mode == "Adaptive Binary Scan":
        st.image(res["scanned_binary"], use_container_width=True)
    else:
        st.image(cv2.cvtColor(res["warped_color"], cv2.COLOR_BGR2RGB), use_container_width=True)

    with st.expander("View Intermediate Processing Stages (Grayscale, CLAHE, Closed Mask)"):
        ic1, ic2, ic3 = st.columns(3)
        ic1.image(res["gray"], caption="Luminance Grayscale", use_container_width=True)
        ic2.image(res["enhanced"], caption="CLAHE Enhanced Lightness", use_container_width=True)
        ic3.image(res["closed_edges"], caption="Morphologically Closed Mask", use_container_width=True)

    dl1, dl2, dl3 = st.columns(3)
    _, buf_enh = cv2.imencode(".png", res["enhanced_scan"])
    _, buf_bin = cv2.imencode(".png", res["scanned_binary"])
    _, buf_col = cv2.imencode(".png", res["warped_color"])
    stem = os.path.splitext(img_label)[0] or "document"
    dl1.download_button(
        "Download Enhanced Grayscale (PNG)", buf_enh.tobytes(), file_name=f"{stem}_enhanced_gray.png", mime="image/png"
    )
    dl2.download_button(
        "Download Adaptive Binary Scan (PNG)", buf_bin.tobytes(), file_name=f"{stem}_scanned_binary.png", mime="image/png"
    )
    dl3.download_button(
        "Download Color Rectified Scan (PNG)", buf_col.tobytes(), file_name=f"{stem}_warped_color.png", mime="image/png"
    )

    if os.path.exists("results/real_evaluation_metrics.csv"):
        with st.expander("View All 7 Real Mobile Capture Metrics"):
            st.dataframe(pd.read_csv("results/real_evaluation_metrics.csv"), use_container_width=True)
else:
    st.info("Upload a document image from the left sidebar to scan it live.")
