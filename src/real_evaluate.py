"""Batch processing, no-reference quality evaluation, and visual export for real document photos."""

import glob
import os
from typing import List
import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .scanner import scan_document


def compute_no_reference_metrics(orig_bgr: np.ndarray, res: dict) -> dict:
    """Compute objective quality & geometric metrics for real-world photos without synthetic ground truth."""
    h_orig, w_orig = orig_bgr.shape[:2]
    frame_area = float(h_orig * w_orig)

    # 1. Detected quadrilateral area coverage (%) and rectified aspect ratio
    quad_area = float(cv2.contourArea(res["corners"].astype(np.float32)))
    area_pct = 100.0 * quad_area / max(1.0, frame_area)

    h_w, w_w = res["warped_gray"].shape[:2]
    aspect_ratio = round(w_w / max(1.0, float(h_w)), 2)

    # 2. RMS Contrast before (raw warped grayscale) vs. after illumination normalization
    raw_std = float(np.std(res["warped_gray"].astype(np.float64)))
    norm_std = float(np.std(res["norm_gray"].astype(np.float64)))
    contrast_gain = norm_std / max(1e-6, raw_std)

    # 3. Edge Sharpness (Variance of Laplacian on normalized grayscale scan)
    lap_var = float(cv2.Laplacian(res["norm_gray"], cv2.CV_64F).var())

    # 4. Otsu Foreground-Background Separability (eta in [0, 1], higher = cleaner bimodal text/paper split)
    hist = cv2.calcHist([res["norm_gray"]], [0], None, [256], [0, 256]).ravel()
    prob = hist / max(1.0, hist.sum())
    bins = np.arange(256, dtype=np.float64)
    total_mean = np.sum(bins * prob)
    total_var = np.sum(((bins - total_mean) ** 2) * prob)

    best_between_var = 0.0
    w_bg = 0.0
    sum_bg = 0.0
    for t in range(256):
        w_bg += prob[t]
        if w_bg <= 0.0 or w_bg >= 1.0:
            continue
        sum_bg += t * prob[t]
        mean_bg = sum_bg / w_bg
        mean_fg = (total_mean - sum_bg) / (1.0 - w_bg)
        between_var = w_bg * (1.0 - w_bg) * ((mean_bg - mean_fg) ** 2)
        if between_var > best_between_var:
            best_between_var = between_var

    separability = best_between_var / max(1e-6, total_var)

    return {
        "Input_Resolution": f"{w_orig}x{h_orig}",
        "Output_Resolution": f"{w_w}x{h_w}",
        "Aspect_Ratio": aspect_ratio,
        "Doc_Area_pct": round(area_pct, 2),
        "Contrast_Gain": round(contrast_gain, 2),
        "Sharpness_LapVar": round(lap_var, 1),
        "Bimodal_Separability": round(separability, 3),
        "Latency_ms": round(res["processing_time_ms"], 2),
    }


def list_image_files(folder: str) -> List[str]:
    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp", "*.JPG", "*.JPEG", "*.PNG")
    files = []
    for ext in exts:
        files.extend(glob.glob(os.path.join(folder, ext)))
    # Exclude ground_truth_doc if falling back to sample_inputs
    files = [f for f in sorted(set(files)) if "ground_truth" not in os.path.basename(f).lower()]
    return files


def run_real_evaluation(
    input_dir: str = "data/real_inputs",
    output_dir: str = "results/real_outputs",
    assets_dir: str = "assets",
    metrics_csv: str = "results/real_evaluation_metrics.csv",
) -> pd.DataFrame:
    """Process all real photos in input_dir, save stage visuals, comparison grid, and CSV metrics."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metrics_csv), exist_ok=True)

    image_paths = list_image_files(input_dir)
    if not image_paths:
        raise FileNotFoundError(
            f"No images found in '{input_dir}'. Copy your .jpg/.png photos into '{input_dir}' first."
        )

    records = []
    grid_items = []

    for img_path in image_paths:
        bgr = cv2.imread(img_path)
        if bgr is None:
            continue

        stem = os.path.splitext(os.path.basename(img_path))[0]
        res = scan_document(bgr, out_size=None)  # Preserve natural document aspect ratio

        # Draw detected 4-point boundary overlay
        contour_vis = bgr.copy()
        thickness = max(4, min(bgr.shape[:2]) // 180)
        radius = max(10, min(bgr.shape[:2]) // 70)
        cv2.polylines(contour_vis, [res["corners"].astype(np.int32)], True, (0, 220, 0), thickness)
        for px, py in res["corners"]:
            cv2.circle(contour_vis, (int(px), int(py)), radius, (255, 40, 40), -1)

        # Save individual outputs
        cv2.imwrite(os.path.join(output_dir, f"{stem}_contour.png"), contour_vis)
        cv2.imwrite(os.path.join(output_dir, f"{stem}_warped_color.png"), res["warped_color"])
        cv2.imwrite(os.path.join(output_dir, f"{stem}_scanned_binary.png"), res["scanned_binary"])

        # Save per-image 6-stage breakdown figure
        fig, axes = plt.subplots(2, 3, figsize=(13.5, 9.5), dpi=220)
        stages = [
            (cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), f"1. Input Capture ({stem})", None),
            (res["enhanced"], "2. Grayscale + CLAHE", "gray"),
            (res["closed_edges"], "3. Canny + Morph. Closing", "gray"),
            (cv2.cvtColor(contour_vis, cv2.COLOR_BGR2RGB), "4. Detected 4-Point Boundary", None),
            (cv2.cvtColor(res["warped_color"], cv2.COLOR_BGR2RGB), "5. Perspective-Warped Color", None),
            (res["scanned_binary"], "6. Final Scanned Binary", "gray"),
        ]
        for ax, (img_data, title, cmap) in zip(axes.flat, stages):
            ax.imshow(img_data, cmap=cmap)
            ax.set_title(title, fontsize=10, fontweight="bold")
            ax.axis("off")
        plt.suptitle(f"Automatic Document Scanner — Pipeline Breakdown ({stem})", fontsize=13, fontweight="bold")
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.savefig(os.path.join(output_dir, f"{stem}_stages.png"), bbox_inches="tight")
        plt.close()

        metrics = {"Image_Name": os.path.basename(img_path)}
        metrics.update(compute_no_reference_metrics(bgr, res))
        records.append(metrics)
        grid_items.append((stem, bgr, contour_vis, res["warped_color"], res["scanned_binary"]))

    df = pd.DataFrame(records)
    df.to_csv(metrics_csv, index=False)

    # Generate multi-image comparison grid (up to 6 images)
    show_items = grid_items[:8]
    n_rows = len(show_items)
    fig, axes = plt.subplots(n_rows, 4, figsize=(14, 3.6 * n_rows), dpi=220)
    if n_rows == 1:
        axes = np.expand_dims(axes, axis=0)

    col_titles = ["Original Capture", "Detected 4-Point Contour", "Perspective-Warped", "Final Binary Scan"]
    for r_idx, (stem, bgr, c_vis, w_col, s_bin) in enumerate(show_items):
        row_imgs = [
            (cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), None),
            (cv2.cvtColor(c_vis, cv2.COLOR_BGR2RGB), None),
            (cv2.cvtColor(w_col, cv2.COLOR_BGR2RGB), None),
            (s_bin, "gray"),
        ]
        for c_idx, (im, cmap) in enumerate(row_imgs):
            ax = axes[r_idx, c_idx]
            ax.imshow(im, cmap=cmap)
            if r_idx == 0:
                ax.set_title(col_titles[c_idx], fontsize=11, fontweight="bold", pad=8)
            if c_idx == 0:
                ax.set_ylabel(stem, fontsize=10, fontweight="bold")
            ax.set_xticks([])
            ax.set_yticks([])

    plt.suptitle("Group 1: Automatic Document Scanner — Real Capture Results", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(assets_dir, "real_results_grid.png"), bbox_inches="tight")
    plt.close()

    return df
