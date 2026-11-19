"""Synthetic document capture dataset generator with exact geometric ground truth."""

import os
from typing import Dict, List, Tuple
import cv2
import numpy as np


def create_ground_truth_document(width: int = 600, height: int = 800) -> np.ndarray:
    """Create a structured fronto-parallel ground-truth technical document page."""
    doc = np.full((height, width), 250, dtype=np.uint8)
    cv2.rectangle(doc, (35, 35), (width - 35, height - 35), 30, 2)
    cv2.rectangle(doc, (35, 35), (width - 35, 115), 225, -1)
    cv2.putText(doc, "PCC-IT-502: IMAGE PROCESSING", (55, 72),
                cv2.FONT_HERSHEY_SIMPLEX, 0.78, 15, 2, cv2.LINE_AA)
    cv2.putText(doc, "GROUP 1 - AUTOMATIC DOCUMENT SCANNER", (55, 102),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, 40, 1, cv2.LINE_AA)

    lines = [
        "1. Abstract: Classical computer vision pipeline",
        "   for automated document boundary extraction",
        "   and perspective rectification.",
        "2. Techniques: Grayscale, Gaussian Filtering,",
        "   CLAHE, Canny Edge Detection, Morphology,",
        "   Contour Approximation, 4-Point Homography,",
        "   and Adaptive Gaussian Thresholding.",
        "3. Evaluation Metrics:",
        "   - Corner Localization Error (pixels)",
        "   - Document Region IoU (%)",
        "   - Peak Signal-to-Noise Ratio (PSNR in dB)",
        "   - Mean Squared Error (MSE)",
        "   - Per-Image Processing Latency (ms)",
    ]
    y = 160
    for line in lines:
        cv2.putText(doc, line, (55, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, 20, 1, cv2.LINE_AA)
        y += 32

    table_top = 595
    cv2.rectangle(doc, (55, table_top), (width - 55, table_top + 145), 25, 2)
    for r in range(1, 4):
        ry = table_top + r * 36
        cv2.line(doc, (55, ry), (width - 55, ry), 25, 1)
    cv2.line(doc, (260, table_top), (260, table_top + 145), 25, 1)
    cv2.line(doc, (410, table_top), (410, table_top + 145), 25, 1)

    rows = [
        ("Stage", "Operator", "Complexity"),
        ("Filtering", "Gaussian 5x5", "O(W*H)"),
        ("Edges", "Canny + Close", "O(W*H)"),
        ("Rectify", "Homography 3x3", "O(W*H)"),
    ]
    for i, (c1, c2, c3) in enumerate(rows):
        ty = table_top + 24 + i * 36
        cv2.putText(doc, c1, (68, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.48, 15, 1, cv2.LINE_AA)
        cv2.putText(doc, c2, (272, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.48, 15, 1, cv2.LINE_AA)
        cv2.putText(doc, c3, (422, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.48, 15, 1, cv2.LINE_AA)

    return doc


def create_test_scene(
    gt_doc: np.ndarray,
    dst_pts: List[List[float]],
    canvas_size: Tuple[int, int] = (1150, 950),
    bg_color: Tuple[int, int, int] = (68, 82, 98),
    shadow: bool = False,
    noise_sigma: float = 0.0,
    low_contrast: bool = False,
    clutter: bool = False,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """Warp ground-truth document onto a realistic background with controlled degradations."""
    rng = np.random.default_rng(seed)
    ch, cw = canvas_size
    bg = np.full((ch, cw, 3), bg_color, dtype=np.uint8)
    tex = rng.normal(0, 5, (ch, cw, 1))
    bg = np.clip(bg.astype(np.float32) + tex, 0, 255).astype(np.uint8)

    if clutter:
        cv2.rectangle(bg, (25, 30), (125, 210), (105, 92, 78), -1)
        cv2.line(bg, (cw - 65, 50), (cw - 25, 390), (42, 48, 58), 14)
        cv2.circle(bg, (85, ch - 85), 42, (95, 108, 120), -1)

    h, w = gt_doc.shape
    src_pts = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    dst_arr = np.array(dst_pts, dtype=np.float32)
    homography = cv2.getPerspectiveTransform(src_pts, dst_arr)

    doc_bgr = cv2.cvtColor(gt_doc, cv2.COLOR_GRAY2BGR)
    warped_doc = cv2.warpPerspective(doc_bgr, homography, (cw, ch), flags=cv2.INTER_CUBIC)
    mask = cv2.warpPerspective(np.full((h, w), 255, dtype=np.uint8), homography, (cw, ch))
    mask_3 = cv2.merge([mask, mask, mask]) > 127

    scene = np.where(mask_3, warped_doc, bg)

    if low_contrast:
        scene = np.clip(scene.astype(np.float32) * 0.60 + 58, 0, 255).astype(np.uint8)

    if shadow:
        yy, xx = np.mgrid[0:ch, 0:cw].astype(np.float32)
        illum = 1.04 - 0.48 * (0.55 * xx / cw + 0.45 * yy / ch)
        scene = np.clip(scene.astype(np.float32) * illum[..., None], 0, 255).astype(np.uint8)

    if noise_sigma > 0:
        noise = rng.normal(0, noise_sigma, scene.shape)
        scene = np.clip(scene.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return scene, dst_arr


def generate_benchmark_dataset(output_dir: str = "data/sample_inputs") -> List[Dict[str, object]]:
    """Generate and save all 4 benchmark scenarios plus the ground-truth reference."""
    os.makedirs(output_dir, exist_ok=True)
    gt_doc = create_ground_truth_document(600, 800)
    cv2.imwrite(os.path.join(output_dir, "ground_truth_doc.png"), gt_doc)

    scenarios = [
        (
            "sample_1_tilted_clean",
            "Img 1: Tilted Clean",
            [[170, 130], [745, 165], [780, 995], [135, 960]],
            dict(shadow=False, noise_sigma=2.0, low_contrast=False, clutter=False, seed=10),
        ),
        (
            "sample_2_shadow_noise",
            "Img 2: Shadow + Noise",
            [[190, 145], [730, 120], [790, 975], [140, 1005]],
            dict(shadow=True, noise_sigma=6.5, low_contrast=False, clutter=False, seed=20),
        ),
        (
            "sample_3_skew_low_contrast",
            "Img 3: Skew + Low Contrast",
            [[145, 175], [715, 115], [805, 955], [180, 1015]],
            dict(shadow=False, noise_sigma=5.0, low_contrast=True, clutter=False, seed=30),
        ),
        (
            "sample_4_cluttered_shadow",
            "Img 4: Cluttered Desk + Shadow",
            [[180, 135], [735, 170], [775, 990], [145, 970]],
            dict(shadow=True, noise_sigma=6.0, low_contrast=False, clutter=True, seed=40),
        ),
    ]

    dataset = []
    for slug, label, pts, kwargs in scenarios:
        scene, gt_pts = create_test_scene(gt_doc, pts, **kwargs)
        img_path = os.path.join(output_dir, f"{slug}.jpg")
        cv2.imwrite(img_path, scene)
        dataset.append(
            {
                "slug": slug,
                "label": label,
                "image_path": img_path,
                "image": scene,
                "gt_pts": gt_pts,
                "gt_doc": gt_doc,
            }
        )
    return dataset
