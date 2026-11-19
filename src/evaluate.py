"""Quantitative evaluation & visualization suite for Automatic Document Scanner."""

import os
import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .dataset_generator import generate_benchmark_dataset
from .scanner import scan_document


def compute_iou(gt_pts: np.ndarray, pred_pts: np.ndarray, shape: tuple) -> float:
    """Compute polygon Intersection-over-Union (%) between ground-truth and predicted corners."""
    mask_gt = np.zeros(shape[:2], dtype=np.uint8)
    mask_pr = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask_gt, gt_pts.astype(np.int32), 255)
    cv2.fillConvexPoly(mask_pr, pred_pts.astype(np.int32), 255)
    inter = np.logical_and(mask_gt > 0, mask_pr > 0).sum()
    union = np.logical_or(mask_gt > 0, mask_pr > 0).sum()
    return float(100.0 * inter / max(1, union))


def run_evaluation(
    input_dir: str = "data/sample_inputs",
    output_dir: str = "results/sample_outputs",
    assets_dir: str = "assets",
    metrics_csv: str = "results/evaluation_metrics.csv",
) -> pd.DataFrame:
    """Execute full benchmark evaluation, export outputs, and save publication-ready charts."""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(assets_dir, exist_ok=True)
    os.makedirs(os.path.dirname(metrics_csv), exist_ok=True)

    dataset = generate_benchmark_dataset(input_dir)
    records = []
    processed_items = []

    for item in dataset:
        scene = item["image"]
        gt_pts = item["gt_pts"]
        gt_doc = item["gt_doc"]
        _, gt_bin = cv2.threshold(gt_doc, 180, 255, cv2.THRESH_BINARY)

        res = scan_document(scene, out_size=(600, 800))

        # Save scanned outputs
        cv2.imwrite(os.path.join(output_dir, f"scanned_{item['slug'].replace('sample_', '')}.png"), res["scanned_binary"])
        if item["slug"] == "sample_2_shadow_noise":
            cv2.imwrite(os.path.join(output_dir, "warped_2_color.png"), res["warped_color"])

        corner_err = float(np.mean(np.linalg.norm(res["corners"] - gt_pts, axis=1)))
        iou_pct = compute_iou(gt_pts, res["corners"], scene.shape)

        mse_base = float(np.mean((gt_bin.astype(np.float64) - res["baseline_otsu"].astype(np.float64)) ** 2))
        psnr_base = 10.0 * np.log10((255.0 ** 2) / max(mse_base, 1e-10))

        mse_prop = float(np.mean((gt_bin.astype(np.float64) - res["scanned_binary"].astype(np.float64)) ** 2))
        psnr_prop = 10.0 * np.log10((255.0 ** 2) / max(mse_prop, 1e-10))

        records.append(
            {
                "Scenario": item["label"],
                "Corner_Error_px": round(corner_err, 2),
                "Boundary_IoU_pct": round(iou_pct, 2),
                "MSE_Baseline_Otsu": round(mse_base, 2),
                "PSNR_Baseline_dB": round(psnr_base, 2),
                "MSE_Proposed": round(mse_prop, 2),
                "PSNR_Proposed_dB": round(psnr_prop, 2),
                "Latency_ms": round(res["processing_time_ms"], 2),
            }
        )
        processed_items.append((item, res))

    df = pd.DataFrame(records)
    df.to_csv(metrics_csv, index=False)

    # Generate Figure 1: Step-by-Step Pipeline Stages on Scenario 2 (Shadow + Noise)
    item2, res2 = processed_items[1]
    contour_vis = item2["image"].copy()
    cv2.polylines(contour_vis, [res2["corners"].astype(np.int32)], True, (0, 220, 0), 6)
    for px, py in res2["corners"]:
        cv2.circle(contour_vis, (int(px), int(py)), 14, (255, 40, 40), -1)

    fig, axes = plt.subplots(2, 3, figsize=(13.5, 10.2), dpi=150)
    stages = [
        (cv2.cvtColor(item2["image"], cv2.COLOR_BGR2RGB), "1. Input Capture (Shadow + Noise)", None),
        (res2["enhanced"], "2. Grayscale + CLAHE Enhancement", "gray"),
        (res2["closed_edges"], "3. Canny + Morphological Closing", "gray"),
        (cv2.cvtColor(contour_vis, cv2.COLOR_BGR2RGB), "4. Detected 4-Point Contour", None),
        (cv2.cvtColor(res2["warped_color"], cv2.COLOR_BGR2RGB), "5. Perspective-Warped Document", None),
        (res2["scanned_binary"], "6. Final Scanned Output (Adaptive)", "gray"),
    ]
    for ax, (img_data, title, cmap) in zip(axes.flat, stages):
        ax.imshow(img_data, cmap=cmap)
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)
        ax.axis("off")

    plt.suptitle(
        "Group 1: Automatic Document Scanner — Step-by-Step Image Processing Pipeline",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(os.path.join(assets_dir, "pipeline_stages.png"), bbox_inches="tight")
    plt.close()

    # Generate Figure 2: Quantitative Benchmark Charts
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), dpi=150)
    x = np.arange(len(df))
    w_bar = 0.35

    rects1 = ax1.bar(x - w_bar / 2, df["PSNR_Baseline_dB"], w_bar, label="Method 1: Global Otsu (No Warp)", color="#94a3b8")
    rects2 = ax1.bar(x + w_bar / 2, df["PSNR_Proposed_dB"], w_bar, label="Proposed: Perspective + Adaptive", color="#2563eb")
    ax1.set_ylabel("PSNR (dB) — Higher is Better", fontsize=10, fontweight="bold")
    ax1.set_title("Scan Fidelity: PSNR Comparison", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(["Img 1\n(Tilted)", "Img 2\n(Shadow)", "Img 3\n(Low-Contrast)", "Img 4\n(Cluttered)"], fontsize=9)
    ax1.set_ylim(0, max(df["PSNR_Proposed_dB"]) * 1.25)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend(frameon=True, fontsize=9)
    for r in rects1:
        ax1.annotate(f"{r.get_height():.2f}", (r.get_x() + r.get_width() / 2, r.get_height() + 0.3), ha="center", fontsize=8)
    for r in rects2:
        ax1.annotate(f"{r.get_height():.2f}", (r.get_x() + r.get_width() / 2, r.get_height() + 0.3), ha="center", fontsize=8, fontweight="bold")

    bars_iou = ax2.bar(x, df["Boundary_IoU_pct"], 0.48, color="#10b981")
    ax2.set_ylabel("Boundary IoU (%) — Higher is Better", fontsize=10, fontweight="bold")
    ax2.set_title("4-Point Document Localization Accuracy (IoU)", fontsize=12, fontweight="bold")
    ax2.set_xticks(x)
    ax2.set_xticklabels(["Img 1\n(Tilted)", "Img 2\n(Shadow)", "Img 3\n(Low-Contrast)", "Img 4\n(Cluttered)"], fontsize=9)
    ax2.set_ylim(95, 101)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    for b, err in zip(bars_iou, df["Corner_Error_px"]):
        ax2.annotate(
            f"{b.get_height():.2f}%\n({err:.2f}px err)",
            (b.get_x() + b.get_width() / 2, b.get_height() + 0.15),
            ha="center",
            fontsize=8,
        )

    plt.suptitle(
        "Quantitative Performance Evaluation Across 4 Document Capture Scenarios",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()
    plt.savefig(os.path.join(assets_dir, "evaluation_comparison.png"), bbox_inches="tight")
    plt.close()

    return df


if __name__ == "__main__":
    metrics_df = run_evaluation()
    print(metrics_df.to_string(index=False))
