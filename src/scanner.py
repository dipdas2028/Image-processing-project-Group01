"""Core classical Image Processing pipeline for Automatic Document Scanning.

Supports local desktop/CLI execution and Streamlit Cloud deployment across both
controlled benchmarks and high-resolution smartphone/camera document captures.
"""

import time
from typing import Dict, Optional, Tuple
import cv2
import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 corner coordinates canonically: [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]      # Top-left minimizes (x + y)
    rect[2] = pts[np.argmax(s)]      # Bottom-right maximizes (x + y)

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]   # Top-right minimizes (y - x)
    rect[3] = pts[np.argmax(diff)]   # Bottom-left maximizes (y - x)
    return rect


def four_point_transform(
    image: np.ndarray,
    pts: np.ndarray,
    out_size: Optional[Tuple[int, int]] = None,
    max_out_dim: int = 2800,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute 3x3 projective homography and warp quadrilateral using Lanczos4 interpolation."""
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    if out_size is None:
        width_a = np.linalg.norm(br - bl)
        width_b = np.linalg.norm(tr - tl)
        max_w = max(int(round(width_a)), int(round(width_b)), 100)

        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_h = max(int(round(height_a)), int(round(height_b)), 100)

        longest = max(max_w, max_h)
        if longest > max_out_dim:
            scale = max_out_dim / float(longest)
            max_w = max(100, int(round(max_w * scale)))
            max_h = max(100, int(round(max_h * scale)))

        out_size = (max_w, max_h)

    dst = np.array(
        [
            [0, 0],
            [out_size[0] - 1, 0],
            [out_size[0] - 1, out_size[1] - 1],
            [0, out_size[1] - 1],
        ],
        dtype="float32",
    )

    homography_matrix = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, homography_matrix, out_size, flags=cv2.INTER_LANCZOS4)
    return warped, rect


def scan_document(
    image: np.ndarray,
    out_size: Optional[Tuple[int, int]] = None,
    target_height: float = 700.0,
) -> Dict[str, object]:
    """Run the 6-stage classical computer vision document scanning pipeline."""
    t0 = time.perf_counter()
    orig = image.copy()

    # Stage 1: Aspect-ratio preserving resize with scale ratio tracking
    ratio = orig.shape[0] / target_height
    new_w = max(1, int(round(orig.shape[1] / ratio)))
    resized = cv2.resize(orig, (new_w, int(target_height)), interpolation=cv2.INTER_AREA)
    h_r, w_r = resized.shape[:2]
    frame_area = float(h_r * w_r)

    # Stage 2: Pre-processing (LAB Lightness + Grayscale + Median Smoothing + CLAHE)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    lab_l = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB)[:, :, 0]
    smooth = cv2.medianBlur(lab_l, 9)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(smooth)

    # Gradient magnitude for boundary alignment scoring
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(gx, gy)

    # Stage 3: Multi-threshold Otsu Morphology + Canny Edge Detection
    otsu_t, otsu_mask = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

    masks_to_try = []
    for delta in (-6, 0, 8, 14):
        _, m = cv2.threshold(smooth, min(240, max(30, int(otsu_t) + delta)), 255, cv2.THRESH_BINARY)
        m_clean = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_open)
        m_clean = cv2.morphologyEx(m_clean, cv2.MORPH_CLOSE, k_close, iterations=2)
        masks_to_try.append(m_clean)

    edged = cv2.Canny(enhanced, max(25, 0.45 * otsu_t), max(75, 1.15 * otsu_t))
    closed_edges = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, k_close, iterations=2)
    masks_to_try.append(closed_edges)

    # Stage 4: External Contour Detection & Purity-Scored 4-Point Polygon Approximation
    candidates = []
    for mask_src in masks_to_try:
        cnts, _ = cv2.findContours(mask_src, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
        for c in cnts:
            c_area = cv2.contourArea(c)
            if c_area < 0.18 * frame_area:
                continue
            for geom in (c, cv2.convexHull(c)):
                peri = cv2.arcLength(geom, True)
                for eps in (0.015, 0.02, 0.025, 0.03, 0.04, 0.05):
                    approx = cv2.approxPolyDP(geom, eps * peri, True)
                    if len(approx) == 4 and cv2.isContourConvex(approx):
                        quad = approx.reshape(4, 2).astype("float32")
                        q_mask = np.zeros((h_r, w_r), dtype=np.uint8)
                        cv2.fillConvexPoly(q_mask, quad.astype(np.int32), 255)
                        q_area = float(np.count_nonzero(q_mask))
                        if q_area < 0.18 * frame_area:
                            continue

                        # Tightness check: reject hulls that balloon across dark background patches
                        tightness = min(1.0, c_area / max(1.0, q_area))
                        if tightness < 0.85:
                            continue

                        in_mean = cv2.mean(lab_l, mask=q_mask)[0]
                        out_mean = cv2.mean(lab_l, mask=cv2.bitwise_not(q_mask))[0]
                        contrast_diff = max(0.0, in_mean - out_mean)

                        fg_inside = np.count_nonzero(cv2.bitwise_and(otsu_mask, q_mask))
                        purity = fg_inside / max(1.0, q_area)

                        border_mask = np.zeros((h_r, w_r), dtype=np.uint8)
                        cv2.polylines(border_mask, [quad.astype(np.int32)], True, 255, 5)
                        edge_score = cv2.mean(grad_mag, mask=border_mask)[0]

                        score = (
                            (purity ** 4)
                            * (tightness ** 3)
                            * (contrast_diff * (0.45 + 0.55 * (q_area / frame_area)) + 0.35 * edge_score)
                        )
                        candidates.append((score, quad))
                        break

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        doc_cnt = candidates[0][1]
    else:
        doc_cnt = np.array([[0, 0], [w_r - 1, 0], [w_r - 1, h_r - 1], [0, h_r - 1]], dtype="float32")

    # Stage 5: Projective Homography Perspective Warp on Native-Resolution Image
    detected_pts_orig = doc_cnt.astype("float32") * ratio
    warped_bgr, ordered_pts = four_point_transform(orig, detected_pts_orig, out_size=out_size)
    warped_gray = cv2.cvtColor(warped_bgr, cv2.COLOR_BGR2GRAY)

    # Stage 6: Scale-Adaptive Illumination Normalization + Unsharp Masking + Adaptive Thresholding
    min_side = min(warped_gray.shape[:2])
    bg_ksize = max(25, (min_side // 14) | 1)
    block_size = max(17, (min_side // 22) | 1)

    bg_est = cv2.medianBlur(warped_gray, bg_ksize)
    norm_gray = cv2.divide(warped_gray, bg_est, scale=255)

    # High-clarity anti-aliased grayscale output via unsharp masking
    gaussian_soft = cv2.GaussianBlur(norm_gray, (0, 0), sigmaX=1.4)
    enhanced_scan = cv2.addWeighted(norm_gray, 1.4, gaussian_soft, -0.4, 0)

    scanned_raw = cv2.adaptiveThreshold(
        enhanced_scan, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, 15
    )
    scanned_bin = cv2.medianBlur(scanned_raw, 3)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Baseline Method 1 (for benchmark comparison): Resize + Global Otsu without warp
    base_target = (warped_bgr.shape[1], warped_bgr.shape[0])
    base_gray = cv2.cvtColor(cv2.resize(orig, base_target), cv2.COLOR_BGR2GRAY)
    _, base_otsu = cv2.threshold(base_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return {
        "resized": resized,
        "gray": gray,
        "enhanced": enhanced,
        "edged": edged,
        "closed_edges": masks_to_try[1],
        "corners": ordered_pts,
        "warped_color": warped_bgr,
        "warped_gray": warped_gray,
        "norm_gray": norm_gray,
        "enhanced_scan": enhanced_scan,
        "scanned_binary": scanned_bin,
        "baseline_otsu": base_otsu,
        "processing_time_ms": elapsed_ms,
    }
