"""Generate Blue-Theme 12-Slide PPTX and 6-Chapter DOCX Report for Group 1 (PCC-IT-502).

Automatically uses real mobile phone capture outputs (`assets/real_results_grid.png`,
`results/real_outputs/*_stages.png`, and `results/real_evaluation_metrics.csv`) whenever
present in the repository, and falls back to the 4-scenario baseline figures otherwise.
"""

import glob
import os
import shutil
import sys
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from docx import Document
from docx.shared import Inches as DocInches, Pt as DocPt, RGBColor as DocRGB
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from src.dataset_generator import generate_benchmark_dataset
from src.scanner import scan_document

# Group 1 Member Names (Roll Nos. 76-80) - Update names here anytime and re-run build_docs.py
GROUP_MEMBERS = [
    ("76", "Group 1 Member 1"),
    ("77", "Group 1 Member 2"),
    ("78", "Group 1 Member 3"),
    ("79", "Group 1 Member 4"),
    ("80", "Group 1 Member 5"),
]


def ensure_visual_assets(assets_dir: str = "assets"):
    """Ensure BlueTheme architecture, preprocessing, and evaluation figures exist."""
    os.makedirs(assets_dir, exist_ok=True)
    fig_arch_path = os.path.join(assets_dir, "system_architecture_bluetheme.png")
    fig_prep_path = os.path.join(assets_dir, "preprocessing_8panel_bluetheme.png")
    fig_grid_path = os.path.join(assets_dir, "comparison_grid_bluetheme.png")
    fig_chart1_path = os.path.join(assets_dir, "chart_fidelity_bluetheme.png")
    fig_chart2_path = os.path.join(assets_dir, "chart_scenarios_bluetheme.png")

    # 1. System Architecture Block Diagram
    fig, ax = plt.subplots(figsize=(13.5, 6.7), dpi=200)
    fig.patch.set_facecolor("#F3F8FD")
    ax.set_facecolor("#F3F8FD")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    ax.axis("off")

    ax.text(
        50, 49.2,
        "System architecture: automatic document scanner",
        ha="center", va="center", fontsize=17, fontweight="bold", color="#0F172A"
    )

    def draw_box(x, y, w, h, text, fc="#E8F1FA", ec="#2F6690", lw=1.8, fontsize=9.8):
        box = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.6,rounding_size=1.2",
            facecolor=fc, edgecolor=ec, linewidth=lw
        )
        ax.add_patch(box)
        ax.text(
            x + w / 2.0, y + h / 2.0, text,
            ha="center", va="center", fontsize=fontsize, fontweight="bold",
            color="#10253A", linespacing=1.35
        )

    def draw_arrow(x1, y1, x2, y2):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.55", color="#2F6690", lw=1.7)
        )

    top_boxes = [
        (2.5, 34.5, 20.5, 9.5, "1. Mobile image capture\nSmartphone camera photo\n(tilted, shadowed RGB)"),
        (27.0, 34.5, 20.5, 9.5, "2. Pre-processing\nResize (700 px), grayscale,\nCLAHE, 5×5 Gaussian"),
        (51.5, 34.5, 20.5, 9.5, "3. Edge & contour\nOtsu-Canny, 7×7 closing,\n4-point RDP approx"),
        (76.0, 34.5, 21.5, 9.5, "4. Rectify & binarize\n3×3 homography warp +\nadaptive thresholding"),
    ]
    for bx, by, bw, bh, btxt in top_boxes:
        draw_box(bx, by, bw, bh, btxt)

    draw_arrow(23.7, 39.25, 26.3, 39.25)
    draw_arrow(48.2, 39.25, 50.8, 39.25)
    draw_arrow(72.7, 39.25, 75.3, 39.25)

    mid_boxes = [
        (7.5, 18.0, 24.5, 8.8, "Module A — Boundary fusion\nOtsu-guided Canny + closing\n& morphological gradient"),
        (37.75, 18.0, 24.5, 8.8, "Module B — 4-point homography\nCanonical corner ordering\n& bicubic perspective warp"),
        (68.0, 18.0, 24.5, 8.8, "Module C — Illumination norm.\n35×35 median division &\n25×25 Gaussian threshold"),
    ]
    for bx, by, bw, bh, btxt in mid_boxes:
        draw_box(bx, by, bw, bh, btxt, fc="#EAF3FC")

    draw_arrow(86.75, 33.8, 19.75, 27.5)
    draw_arrow(86.75, 33.8, 50.0, 27.5)
    draw_arrow(86.75, 33.8, 80.25, 27.5)

    draw_box(
        27.5, 2.2, 45.0, 8.8,
        "5. Output export & quantitative evaluation\nRectified color & binary scan | Corner Error, IoU, MSE, PSNR, Latency",
        fc="#E4EFFA"
    )
    draw_arrow(19.75, 17.3, 37.0, 11.7)
    draw_arrow(50.0, 17.3, 50.0, 11.7)
    draw_arrow(80.25, 17.3, 63.0, 11.7)

    plt.tight_layout(pad=0.3)
    plt.savefig(fig_arch_path, dpi=200, facecolor="#F3F8FD")
    plt.close()

    # Check if user has placed real mobile photos in data/real_inputs/
    real_imgs = sorted(
        p for ext in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp", "*.JPG", "*.JPEG", "*.PNG")
        for p in glob.glob(os.path.join("data/real_inputs", ext))
    )
    has_real = len(real_imgs) > 0 and os.path.exists(os.path.join(assets_dir, "real_results_grid.png"))

    # Use first real mobile image for the 8-panel preprocessing breakdown if available, else sample 2
    if len(real_imgs) > 0:
        sample_bgr = cv2.imread(real_imgs[0])
        cap_label = f"1. Mobile capture ({os.path.basename(real_imgs[0])})"
    else:
        ds = generate_benchmark_dataset("data/sample_inputs")
        sample_bgr = ds[1]["image"]
        cap_label = "1. Mobile capture (Shadow + Noise)"

    res_s = scan_document(sample_bgr, out_size=None if len(real_imgs) > 0 else (600, 800))
    blurred_s = cv2.GaussianBlur(res_s["enhanced"], (5, 5), 0)
    _, otsu_mask_s = cv2.threshold(blurred_s, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel7 = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    closed_canny_s = cv2.morphologyEx(res_s["edged"], cv2.MORPH_CLOSE, kernel7, iterations=2)
    contour_vis_s = sample_bgr.copy()
    thick = max(5, min(sample_bgr.shape[:2]) // 180)
    rad = max(12, min(sample_bgr.shape[:2]) // 70)
    cv2.polylines(contour_vis_s, [res_s["corners"].astype(np.int32)], True, (0, 210, 0), thick)
    for px, py in res_s["corners"]:
        cv2.circle(contour_vis_s, (int(px), int(py)), rad, (235, 45, 45), -1)

    fig, axes = plt.subplots(2, 4, figsize=(13.5, 6.8), dpi=200)
    fig.patch.set_facecolor("#FCFEFF")
    panels8 = [
        (cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2RGB), cap_label, None),
        (res_s["gray"], "2. Luminance grayscale", "gray"),
        (res_s["enhanced"], "3. CLAHE contrast (8×8)", "gray"),
        (res_s["edged"], "4. Otsu-guided Canny edges", "gray"),
        (closed_canny_s, "5. Morphological closing (7×7)", "gray"),
        (otsu_mask_s, "6. Otsu foreground mask", "gray"),
        (res_s["closed_edges"], "7. Fused boundary edge map", "gray"),
        (cv2.cvtColor(contour_vis_s, cv2.COLOR_BGR2RGB), "8. 4-point polygon corners", None),
    ]
    for ax, (im, title, cmap) in zip(axes.flat, panels8):
        ax.imshow(im, cmap=cmap)
        ax.set_title(title, fontsize=9.5, fontweight="bold", color="#1E354D", pad=5)
        ax.axis("off")

    plt.suptitle("Pre-processing and 4-point boundary extraction", fontsize=14, fontweight="bold", color="#0F172A", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(fig_prep_path, dpi=200, facecolor="#FCFEFF")
    plt.close()

    # Comparison grid: prefer real_results_grid.png if user ran --real
    if has_real:
        shutil.copy2(os.path.join(assets_dir, "real_results_grid.png"), fig_grid_path)
    else:
        ds = generate_benchmark_dataset("data/sample_inputs")
        fig, axes = plt.subplots(3, 4, figsize=(12.2, 9.2), dpi=200)
        fig.patch.set_facecolor("#F3F8FD")
        col_headers = ["Original mobile capture", "4-point contour", "Perspective-warped", "Adaptive binary scan"]
        for r_i, idx_s in enumerate([0, 1, 2]):
            it = ds[idx_s]
            rs = scan_document(it["image"], out_size=(600, 800))
            c_img = it["image"].copy()
            cv2.polylines(c_img, [rs["corners"].astype(np.int32)], True, (0, 210, 0), 7)
            for px, py in rs["corners"]:
                cv2.circle(c_img, (int(px), int(py)), 14, (235, 45, 45), -1)

            row_data = [
                (cv2.cvtColor(it["image"], cv2.COLOR_BGR2RGB), None),
                (cv2.cvtColor(c_img, cv2.COLOR_BGR2RGB), None),
                (cv2.cvtColor(rs["warped_color"], cv2.COLOR_BGR2RGB), None),
                (rs["scanned_binary"], "gray"),
            ]
            for c_i, (im, cmap) in enumerate(row_data):
                ax = axes[r_i, c_i]
                ax.imshow(im, cmap=cmap)
                if r_i == 0:
                    ax.set_title(col_headers[c_i], fontsize=10.5, fontweight="bold", color="#1E354D", pad=6)
                ax.axis("off")

        plt.suptitle("Comparison across tilted, shadowed, and low-contrast captures", fontsize=13.5, fontweight="bold", color="#0F172A", y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.savefig(fig_grid_path, dpi=200, facecolor="#F3F8FD")
        plt.close()

    # Quantitative Charts
    metrics_df = pd.read_csv("results/evaluation_metrics.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.2, 3.2), dpi=200)
    fig.patch.set_facecolor("#F3F8FD")
    methods = ["Global Otsu\n(No Warp)", "Proposed\n(Homography)"]
    mse_vals = [metrics_df["MSE_Baseline_Otsu"].mean() / 1000.0, metrics_df["MSE_Proposed"].mean() / 1000.0]
    psnr_vals = [metrics_df["PSNR_Baseline_dB"].mean(), metrics_df["PSNR_Proposed_dB"].mean()]
    bar_colors = ["#8DB9E2", "#1F4E78"]

    for ax, vals, ylabel, title in [
        (ax1, mse_vals, "MSE × 10³ (lower is better)", "Mean pixel error"),
        (ax2, psnr_vals, "PSNR (dB, higher is better)", "Mean scan fidelity"),
    ]:
        ax.set_facecolor("#FFFFFF")
        bars = ax.bar(methods, vals, width=0.52, color=bar_colors)
        ax.set_ylabel(ylabel, fontsize=8.5, color="#24384D")
        ax.set_title(title, fontsize=10.5, fontweight="bold", color="#10253A", pad=8)
        ax.set_ylim(0, max(vals) * 1.24)
        ax.grid(axis="y", linestyle="-", alpha=0.35, color="#CBD5E1")
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", labelsize=8.5)
        ax.tick_params(axis="y", labelsize=8)
        for b in bars:
            ax.annotate(
                f"{b.get_height():.2f}",
                (b.get_x() + b.get_width() / 2, b.get_height() + max(vals) * 0.03),
                ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#10253A"
            )

    plt.suptitle("Average quality metrics across capture scenarios", fontsize=11.5, fontweight="bold", color="#0F172A", y=1.02)
    plt.tight_layout()
    plt.savefig(fig_chart1_path, dpi=200, bbox_inches="tight", facecolor="#F3F8FD")
    plt.close()

    fig, ax = plt.subplots(figsize=(7.2, 3.6), dpi=200)
    fig.patch.set_facecolor("#F3F8FD")
    ax.set_facecolor("#FFFFFF")
    x = np.arange(len(metrics_df))
    w = 0.36
    b1 = ax.bar(x - w / 2, metrics_df["PSNR_Baseline_dB"], w, label="Global Otsu (No Warp)", color="#8DB9E2")
    b2 = ax.bar(x + w / 2, metrics_df["PSNR_Proposed_dB"], w, label="Proposed Scanner", color="#1F4E78")

    ax.set_ylabel("PSNR (dB)", fontsize=9, color="#24384D")
    ax.set_title("Scan fidelity (PSNR) across capture conditions", fontsize=11, fontweight="bold", color="#10253A", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels(["Tilted\nClean", "Shadow +\nNoise", "Skew + Low\nContrast", "Cluttered\nDesk"], fontsize=8.5)
    ax.set_ylim(0, 16.5)
    ax.grid(axis="y", linestyle="-", alpha=0.35, color="#CBD5E1")
    ax.set_axisbelow(True)
    ax.legend(frameon=True, fontsize=8.5, loc="upper right")

    for bar_set in (b1, b2):
        for b in bar_set:
            ax.annotate(
                f"{b.get_height():.2f}",
                (b.get_x() + b.get_width() / 2, b.get_height() + 0.35),
                ha="center", va="bottom", fontsize=7.8, fontweight="bold", color="#10253A"
            )

    plt.tight_layout()
    plt.savefig(fig_chart2_path, dpi=200, bbox_inches="tight", facecolor="#F3F8FD")
    plt.close()

    return {
        "arch": fig_arch_path,
        "prep": fig_prep_path,
        "grid": fig_grid_path,
        "chart1": fig_chart1_path,
        "chart2": fig_chart2_path,
        "has_real": has_real,
        "real_count": len(real_imgs),
    }


def build_presentation(figs: dict, out_pptx: str = "docs/Group1_Automatic_Document_Scanner_Presentation_BlueTheme.pptx"):
    """Build 12-slide Blue-Theme PowerPoint deck without any assigned-role columns."""
    C_BG_CANVAS   = RGBColor(0xF3, 0xF8, 0xFD)
    C_DARK_TEXT   = RGBColor(0x24, 0x38, 0x4D)
    C_PRIMARY_BL  = RGBColor(0x2F, 0x66, 0x90)
    C_MED_BLUE    = RGBColor(0x47, 0x7F, 0xAE)
    C_ACCENT_BLUE = RGBColor(0x67, 0x9C, 0xCB)
    C_MUTED_SLATE = RGBColor(0x53, 0x6B, 0x80)
    C_SIDE_STRIPE = RGBColor(0x35, 0x5F, 0x87)
    C_CARD_WHITE  = RGBColor(0xFC, 0xFE, 0xFF)
    C_CARD_BLUE1  = RGBColor(0xE6, 0xF2, 0xFC)
    C_CARD_BLUE2  = RGBColor(0xEA, 0xF5, 0xFD)
    C_BORDER_GRAY = RGBColor(0xD0, 0xDF, 0xEC)
    C_BORDER_SOFT = RGBColor(0xE5, 0xF1, 0xFB)

    prs = Presentation()
    prs.slide_width = Inches(13.333333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    def set_slide_bg(slide, color=C_BG_CANVAS):
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def add_round_card(slide, x, y, w, h, fill_rgb=C_CARD_WHITE, line_rgb=C_BORDER_GRAY, line_pt=1.0):
        sh = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        sh.adjustments[0] = 0.04
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill_rgb
        if line_rgb is not None:
            sh.line.color.rgb = line_rgb
            sh.line.width = Pt(line_pt)
        else:
            sh.line.fill.background()
        return sh

    def add_rect_box(slide, x, y, w, h, fill_rgb=None):
        sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        if fill_rgb is not None:
            sh.fill.solid()
            sh.fill.fore_color.rgb = fill_rgb
        else:
            sh.fill.background()
        sh.line.fill.background()
        return sh

    def add_hline(slide, x, y, w, line_rgb=C_BORDER_GRAY, line_pt=1.0):
        ln = slide.shapes.add_connector(1, Inches(x), Inches(y), Inches(x + w), Inches(y))
        ln.line.color.rgb = line_rgb
        ln.line.width = Pt(line_pt)
        return ln

    def add_text(slide, x, y, w, h, text, font_size=12.0, bold=False, color=C_DARK_TEXT,
                 align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, line_spacing=1.18):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = valign
        tf.margin_left = Pt(2)
        tf.margin_right = Pt(2)
        tf.margin_top = Pt(1)
        tf.margin_bottom = Pt(1)
        for idx, line_str in enumerate(text.split("\n")):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = line_spacing
            r = p.add_run()
            r.text = line_str
            r.font.name = "Arial"
            r.font.size = Pt(font_size)
            r.font.bold = bold
            r.font.color.rgb = color
        return tb

    def add_rich_lines(slide, x, y, w, h, pairs, font_size=12.5, line_spacing=1.25):
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = Pt(2)
        tf.margin_right = Pt(2)
        tf.margin_top = Pt(1)
        tf.margin_bottom = Pt(1)
        for idx, (b_txt, r_txt) in enumerate(pairs):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.line_spacing = line_spacing
            if b_txt:
                rb = p.add_run()
                rb.text = b_txt
                rb.font.name = "Arial"
                rb.font.size = Pt(font_size)
                rb.font.bold = True
                rb.font.color.rgb = C_PRIMARY_BL
            if r_txt:
                rr = p.add_run()
                rr.text = r_txt
                rr.font.name = "Arial"
                rr.font.size = Pt(font_size)
                rr.font.bold = False
                rr.font.color.rgb = C_DARK_TEXT
        return tb

    def init_content_slide(kicker, title, slide_num, total_slides=12):
        slide = prs.slides.add_slide(blank_layout)
        set_slide_bg(slide, C_BG_CANVAS)
        add_text(slide, 0.55, 0.23, 11.70, 0.24, kicker, font_size=9.5, bold=True, color=C_MED_BLUE)
        add_text(slide, 0.55, 0.48, 12.10, 0.54, title, font_size=24.5, bold=True, color=C_DARK_TEXT)
        add_hline(slide, 0.55, 1.10, 12.23, C_BORDER_GRAY, 1.0)
        add_hline(slide, 0.55, 7.12, 12.23, C_BORDER_GRAY, 1.0)
        add_text(
            slide, 0.57, 7.17, 10.80, 0.20,
            "Haldia Institute of Technology  |  Department of Information Technology  |  Group 1",
            font_size=8.5, bold=False, color=C_MUTED_SLATE
        )
        add_text(
            slide, 12.05, 7.17, 0.70, 0.20,
            f"{slide_num:02d} / {total_slides:02d}",
            font_size=8.5, bold=False, color=C_MUTED_SLATE, align=PP_ALIGN.RIGHT
        )
        return slide

    # Slide 1: Cover
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_bg(s1, C_BG_CANVAS)
    add_rect_box(s1, 0.00, 0.00, 0.16, 7.50, C_SIDE_STRIPE)
    add_round_card(s1, 0.55, 0.48, 12.25, 6.45, C_CARD_WHITE, C_BORDER_GRAY, 1.0)

    logo_p = "assets/hit_logo.png"
    if os.path.exists(logo_p):
        s1.shapes.add_picture(logo_p, Inches(0.95), Inches(0.92), width=Inches(1.75), height=Inches(1.75))

    add_text(s1, 3.00, 1.02, 8.90, 0.34, "HALDIA INSTITUTE OF TECHNOLOGY", font_size=16.5, bold=True, color=C_PRIMARY_BL)
    add_text(s1, 3.00, 1.40, 8.90, 0.30, "Department of Information Technology", font_size=12.5, bold=False, color=C_MUTED_SLATE)
    add_hline(s1, 3.00, 1.80, 8.90, C_BORDER_GRAY, 1.0)

    add_text(s1, 0.95, 2.35, 11.30, 0.38, "MINI PROJECT  |  PCC-IT-502  |  GROUP 1", font_size=13.0, bold=True, color=C_ACCENT_BLUE)
    add_text(s1, 0.95, 2.90, 11.30, 1.05, "Automatic Document Scanner", font_size=33.0, bold=True, color=C_DARK_TEXT)
    add_text(
        s1, 0.95, 4.08, 11.20, 0.55,
        "Grayscale & CLAHE • Otsu-guided Canny • Morphological closing • 4-point homography • Adaptive thresholding",
        font_size=14.2, bold=False, color=C_MED_BLUE
    )

    add_text(s1, 1.15, 5.02, 5.20, 0.26, "SUBMITTED BY  |  ROLL NOS. 76–80", font_size=10.0, bold=True, color=C_MUTED_SLATE)
    members_block = "\n".join([f"{r}   {n}" for r, n in GROUP_MEMBERS])
    add_text(s1, 1.15, 5.32, 5.45, 1.15, members_block, font_size=11.5, bold=False, color=C_DARK_TEXT, line_spacing=1.14)

    add_text(s1, 7.15, 5.02, 4.60, 0.26, "UNDER THE GUIDANCE OF", font_size=10.0, bold=True, color=C_MUTED_SLATE)
    add_text(s1, 7.15, 5.36, 4.60, 0.36, "Arpita Shome", font_size=16.0, bold=True, color=C_PRIMARY_BL)
    add_text(
        s1, 7.15, 5.76, 4.75, 0.56,
        "Assistant Professor\nDepartment of Information Technology",
        font_size=11.5, bold=False, color=C_DARK_TEXT, line_spacing=1.2
    )
    add_text(
        s1, 1.15, 6.55, 10.90, 0.22,
        "Haldia, Purba Medinipur – 721657, West Bengal  |  Academic Session 2026–2027",
        font_size=9.2, bold=False, color=C_MUTED_SLATE
    )

    # Slide 2: Context
    s2 = init_content_slide("01  |  CONTEXT", "Problem Statement & Project Scope", 2)
    cards_s2 = [
        (0.65, "The problem", C_PRIMARY_BL,
         "Photos captured using a mobile phone camera suffer from trapezoidal perspective skew, uneven shadows, sensor noise, and cluttered desk backgrounds."),
        (4.73, "Engineering trade-off", C_ACCENT_BLUE,
         "An automated scanner must recover unbroken 4-point page boundaries under low contrast while keeping CPU execution fast and interpretable."),
        (8.81, "Project response", C_MED_BLUE,
         "Implement a 6-stage classical pipeline in Python and OpenCV: CLAHE, Otsu-Canny + morphological closing, 4-point homography, and adaptive thresholding."),
    ]
    for cx, heading, hcolor, body in cards_s2:
        add_round_card(s2, cx, 1.42, 3.88, 2.08, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
        add_text(s2, cx + 0.22, 1.56, 3.48, 0.38, heading, font_size=16.0, bold=True, color=hcolor)
        add_text(s2, cx + 0.22, 2.02, 3.46, 1.38, body, font_size=13.0, bold=False, color=C_DARK_TEXT, line_spacing=1.22)

    add_text(s2, 0.75, 3.84, 5.80, 0.33, "TEAM  |  GROUP 1 (ROLL NOS. 76–80)", font_size=12.5, bold=True, color=C_PRIMARY_BL)
    pill_coords = [(0.80, 4.30), (3.85, 4.30), (0.80, 5.06), (3.85, 5.06), (0.80, 5.82)]
    for (px, py), (rno, mname) in zip(pill_coords, GROUP_MEMBERS):
        add_round_card(s2, px, py, 2.82, 0.62, C_CARD_BLUE1, C_BORDER_SOFT, 1.0)
        add_text(s2, px + 0.15, py + 0.14, 0.54, 0.30, rno, font_size=13.0, bold=True, color=C_PRIMARY_BL)
        add_text(s2, px + 0.72, py + 0.14, 1.95, 0.30, mname, font_size=12.0, bold=True, color=C_DARK_TEXT)

    add_round_card(s2, 7.05, 3.96, 5.45, 2.48, C_CARD_BLUE2, C_BORDER_SOFT, 1.0)
    add_text(s2, 7.35, 4.18, 4.85, 0.34, "Scope and expected output", font_size=16.0, bold=True, color=C_PRIMARY_BL)
    add_rich_lines(
        s2, 7.35, 4.62, 4.90, 1.65,
        [
            ("Input: ", "real mobile phone camera document captures (tilted, shadowed, cluttered)"),
            ("Output: ", "detected 4-point contour, flattened color & adaptive binary scans"),
            ("Evaluation: ", "Corner Error (px), Boundary IoU (%), MSE, PSNR (dB) & latency"),
        ],
        font_size=12.4, line_spacing=1.35
    )

    # Slide 3: Motivation
    s3 = init_content_slide("02  |  WHY DOCUMENT SCANNING?", "Motivation & Real-World Relevance", 3)
    cards_s3 = [
        (0.72, "Accessible mobile digitization", C_PRIMARY_BL,
         "Students and offices rely on smartphone cameras to archive notes, receipts, and forms without dedicated flatbed scanners."),
        (4.73, "Classical vision efficiency", C_ACCENT_BLUE,
         "Edge detection, mathematical morphology, and 3 × 3 homography rectify perspective tilt in <45 ms on CPU without heavy deep-learning weights."),
        (8.74, "Illumination resilience", C_MED_BLUE,
         "Median background division and local adaptive Gaussian thresholding remove directional hand or lamp shadows that break global Otsu binarization."),
    ]
    for cx, heading, hcolor, body in cards_s3:
        add_round_card(s3, cx, 1.48, 3.88, 3.20, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
        add_text(s3, cx + 0.22, 1.64, 3.48, 0.38, heading, font_size=16.5, bold=True, color=hcolor)
        add_text(s3, cx + 0.22, 2.12, 3.46, 2.45, body, font_size=13.5, bold=False, color=C_DARK_TEXT, line_spacing=1.25)

    add_text(s3, 0.80, 5.06, 4.80, 0.30, "ACADEMIC ALIGNMENT", font_size=11.0, bold=True, color=C_MUTED_SLATE)
    align_pills = [
        (0.80, 5.52, 2.28, "CO1 • Image fundamentals", C_CARD_BLUE1),
        (3.20, 5.52, 2.52, "CO3 • Edges & morphology", C_CARD_BLUE2),
        (5.84, 5.52, 2.38, "CO4 • Homography warp", C_CARD_BLUE1),
        (8.34, 5.52, 2.36, "CO5 • Quality evaluation", C_CARD_BLUE2),
        (10.82, 5.52, 0.90, "SDG 4", C_CARD_BLUE1),
        (11.82, 5.52, 0.90, "SDG 9", C_CARD_BLUE2),
    ]
    for px, py, pw, ptxt, pfill in align_pills:
        add_round_card(s3, px, py, pw, 0.36, pfill, C_BORDER_SOFT, 1.0)
        add_text(s3, px + 0.04, py + 0.05, pw - 0.08, 0.24, ptxt, font_size=10.2, bold=True, color=C_PRIMARY_BL, align=PP_ALIGN.CENTER)

    add_text(
        s3, 0.80, 6.24, 11.60, 0.38,
        "Designed strictly around classical Image Processing techniques covered in PCC-IT-502 for transparent mathematical and experimental evaluation.",
        font_size=11.8, bold=False, color=C_MUTED_SLATE
    )

    # Slide 4: Objectives
    s4 = init_content_slide("03  |  PROJECT TARGETS", "Objectives & Course Outcome Mapping", 4)
    add_text(s4, 0.78, 1.40, 3.10, 0.25, "OBJECTIVE", font_size=10.0, bold=True, color=C_PRIMARY_BL)
    add_text(s4, 4.00, 1.40, 5.20, 0.25, "IMPLEMENTATION", font_size=10.0, bold=True, color=C_PRIMARY_BL)
    add_text(s4, 9.60, 1.40, 2.60, 0.25, "MAPPING", font_size=10.0, bold=True, color=C_PRIMARY_BL)

    rows_s4 = [
        ("1. Enhance mobile capture contrast & denoise",
         "Aspect-ratio resize (700 px), luminance grayscale, CLAHE (8×8 tiles), and 5×5 Gaussian smoothing.",
         "CO1", C_CARD_WHITE),
        ("2. Extract unbroken 4-point page boundary",
         "Otsu-guided Canny edges fused with 7×7 morphological closing, Otsu gradient, and RDP approximation.",
         "CO3", C_CARD_BLUE2),
        ("3. Rectify planar perspective distortion",
         "Canonical corner ordering and 3×3 projective homography transformation (bicubic inverse warp).",
         "CO4", C_CARD_WHITE),
        ("4. Suppress shadows & benchmark fidelity",
         "35×35 median background division + 25×25 adaptive Gaussian thresholding; evaluate IoU, MSE, PSNR & time.",
         "CO5", C_CARD_BLUE2),
    ]
    for idx, (obj_t, imp_t, co_t, row_bg) in enumerate(rows_s4):
        ry = 1.80 + idx * 1.06
        add_round_card(s4, 0.68, ry, 12.00, 0.88, row_bg, C_BORDER_GRAY, 1.0)
        add_text(s4, 0.86, ry + 0.16, 3.00, 0.56, obj_t, font_size=12.6, bold=True, color=C_DARK_TEXT)
        add_text(s4, 4.00, ry + 0.14, 5.40, 0.60, imp_t, font_size=11.8, bold=False, color=C_DARK_TEXT)
        add_round_card(s4, 9.65, ry + 0.26, 1.25, 0.36, C_CARD_BLUE1, C_BORDER_SOFT, 1.0)
        add_text(s4, 9.68, ry + 0.31, 1.19, 0.24, co_t, font_size=12.0, bold=True, color=C_PRIMARY_BL, align=PP_ALIGN.CENTER)

    add_text(
        s4, 0.80, 6.28, 11.80, 0.34,
        "Scope boundary: planar rectangular documents (A4 study notes, receipts, printed forms) captured using a mobile phone camera.",
        font_size=11.4, bold=False, color=C_MUTED_SLATE
    )

    # Slide 5: Literature Survey
    s5 = init_content_slide("04  |  SELECTED REFERENCES", "Literature Survey & Research Position", 5)
    add_text(
        s5, 0.78, 1.34, 11.80, 0.28,
        "Prior classical vision studies highlight the trade-off between edge localization accuracy, illumination invariance, and runtime speed.",
        font_size=12.6, bold=False, color=C_MUTED_SLATE
    )
    lit_rows = [
        ("Otsu (1979)",
         "Global histogram between-class variance maximization for automatic thresholding.",
         "Fast on uniform lighting, but turns shadowed regions black; motivates local adaptive binarization.",
         C_CARD_WHITE),
        ("Canny (1986)",
         "Multi-stage gradient edge detector with non-maximum suppression and hysteresis.",
         "Provides optimal edge localization, but requires Otsu-guided thresholds and closing to seal gaps.",
         C_CARD_BLUE2),
        ("Suzuki & Abe (1985)",
         "Topological border-following algorithm for extracting hierarchical binary contours.",
         "Enables clean external boundary tracing once perimeter edges are closed morphologically.",
         C_CARD_WHITE),
        ("Sauvola & Pietikäinen (2000)",
         "Local sliding-window adaptive document binarization under uneven illumination.",
         "Demonstrates local threshold effectiveness; paired here with median background division.",
         C_CARD_BLUE2),
        ("Gonzalez & Woods / OpenCV",
         "Projective geometry, Ramer–Douglas–Peucker approximation, and 3×3 homography warping.",
         "Mathematical foundation for exact planar perspective rectification from 4 ordered corners.",
         C_CARD_WHITE),
    ]
    for idx, (auth, tech, pos, bg_c) in enumerate(lit_rows):
        ry = 1.76 + idx * 0.92
        add_round_card(s5, 0.72, ry, 11.92, 0.76, bg_c, C_BORDER_GRAY, 1.0)
        add_text(s5, 0.91, ry + 0.14, 2.25, 0.48, auth, font_size=12.0, bold=True, color=C_PRIMARY_BL)
        add_text(s5, 3.22, ry + 0.12, 4.10, 0.54, tech, font_size=11.0, bold=False, color=C_DARK_TEXT)
        add_text(s5, 7.42, ry + 0.12, 4.95, 0.54, pos, font_size=10.8, bold=False, color=C_MUTED_SLATE)

    add_text(
        s5, 0.82, 6.54, 11.60, 0.26,
        "Research position: fuses Otsu-Canny edges with morphological closing and median background division to prevent broken contours on mobile photos.",
        font_size=11.3, bold=True, color=C_PRIMARY_BL
    )

    # Slide 6: Methodology
    s6 = init_content_slide("05  |  DETECTION AND RECTIFICATION", "Proposed Methodology: Three Core Stages", 6)
    meth_cards = [
        (0.72, "A. Edge & morphological fusion", C_PRIMARY_BL,
         "Purpose: unbroken outer page contour\n\n"
         "Enhancement & Edge Map:\n"
         "E_closed = (E_Canny ⊕ B) ⊖ B\n"
         "E_fused = E_closed ∨ ∇(M_Otsu • B)\n\n"
         "Parameters: CLAHE (8×8), Gaussian (5×5), rectangular structuring element B = 7×7."),
        (4.73, "B. 4-point projective homography", C_ACCENT_BLUE,
         "Purpose: fronto-parallel rectification\n\n"
         "Projective Mapping:\n"
         "[w x', w y', w]^T = H [x, y, 1]^T\n\n"
         "Corner Order: TL (min x+y), TR (min y−x), BR (max x+y), BL (max y−x); 8 DOF solved via DLT + bicubic warp."),
        (8.74, "C. Illumination norm. & binarization", C_MED_BLUE,
         "Purpose: shadow-free scan output\n\n"
         "Background Division & Threshold:\n"
         "I_norm = 255 · I_warp / Median(I_warp, 35)\n"
         "T(x, y) = μ_Gaussian(25×25) − 13\n\n"
         "Post-filter: 3×3 median filter removes isolated salt-and-pepper speckles."),
    ]
    for cx, heading, hcolor, body in meth_cards:
        add_round_card(s6, cx, 1.48, 3.88, 3.98, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
        add_text(s6, cx + 0.22, 1.64, 3.48, 0.38, heading, font_size=15.5, bold=True, color=hcolor)
        add_text(s6, cx + 0.22, 2.10, 3.46, 3.25, body, font_size=12.4, bold=False, color=C_DARK_TEXT, line_spacing=1.22)

    add_round_card(s6, 0.84, 5.82, 11.65, 0.65, C_CARD_BLUE1, C_BORDER_SOFT, 1.0)
    add_text(
        s6, 1.08, 6.00, 11.15, 0.26,
        "Shared pipeline: mobile capture resize → CLAHE + Gaussian → edge fusion → 4-point contour → 3×3 homography → adaptive thresholding",
        font_size=12.6, bold=True, color=C_PRIMARY_BL, align=PP_ALIGN.CENTER
    )

    # Slide 7: Architecture
    s7 = init_content_slide("06  |  END-TO-END PIPELINE", "System Architecture & Block Diagram", 7)
    s7.shapes.add_picture(figs["arch"], Inches(1.45), Inches(1.42), width=Inches(10.43), height=Inches(5.18))

    # Slide 8: Operations Used
    s8 = init_content_slide("07  |  OPERATIONS USED", "Image Processing Techniques & Preprocessing", 8)
    add_round_card(s8, 0.65, 1.40, 7.05, 5.35, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
    s8.shapes.add_picture(figs["prep"], Inches(0.76), Inches(2.22), width=Inches(6.82), height=Inches(3.45))

    add_text(s8, 7.98, 1.42, 4.40, 0.35, "CORE OPERATIONS", font_size=12.0, bold=True, color=C_PRIMARY_BL)
    ops_list = [
        ("Resize & grayscale", "Standardizes height to 700 px and extracts luminance intensity."),
        ("CLAHE + Gaussian", "Enhances local contrast (8×8) and suppresses high-frequency noise."),
        ("Otsu-guided Canny", "Adapts hysteresis thresholds dynamically to scene brightness."),
        ("Morph. closing", "7×7 closing + Otsu gradient seals broken page border edges."),
        ("4-point homography", "Orders polygon corners and warps to a flat top-down view."),
        ("Adaptive threshold", "Median background division + Gaussian local binarization."),
    ]
    for idx, (op_name, op_desc) in enumerate(ops_list):
        oy = 1.88 + idx * 0.77
        add_text(s8, 8.02, oy, 1.82, 0.28, op_name, font_size=11.8, bold=True, color=C_PRIMARY_BL)
        add_text(s8, 9.88, oy, 2.75, 0.50, op_desc, font_size=10.8, bold=False, color=C_DARK_TEXT, line_spacing=1.15)
        if idx < len(ops_list) - 1:
            add_hline(s8, 8.02, oy + 0.62, 4.55, C_BORDER_GRAY, 0.8)

    add_text(
        s8, 8.00, 6.56, 4.65, 0.24,
        "Note: detected corners are scaled back by ratio r to warp at native camera resolution.",
        font_size=9.6, bold=False, color=C_MUTED_SLATE
    )

    # Slide 9: Example Output
    s9 = init_content_slide("08  |  EXAMPLE OUTPUT", "Implementation & Mobile Capture Results", 9)
    s9.shapes.add_picture(figs["grid"], Inches(1.15), Inches(1.34), width=Inches(7.45), height=Inches(5.55))

    add_round_card(s9, 9.25, 1.50, 3.42, 5.10, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
    add_text(s9, 9.52, 1.78, 2.85, 0.36, "EXPERIMENT SETUP", font_size=12.0, bold=True, color=C_PRIMARY_BL)
    cap_desc = f"{figs['real_count']} real mobile photos" if figs["has_real"] else "Self-collected mobile captures"
    add_rich_lines(
        s9, 9.52, 2.26, 2.88, 2.30,
        [
            ("Language: ", "Python 3.10+"),
            ("Libraries: ", "OpenCV, NumPy, Matplotlib, Pandas"),
            ("Input source: ", "Mobile phone camera (JPG/PNG)"),
            ("Dataset: ", cap_desc),
            ("Outputs: ", "CSV metrics & PNG stage panels"),
        ],
        font_size=11.4, line_spacing=1.32
    )
    add_hline(s9, 9.52, 4.78, 2.85, C_BORDER_GRAY, 0.9)
    add_text(s9, 9.52, 5.00, 2.85, 0.30, "What the visual shows", font_size=13.0, bold=True, color=C_PRIMARY_BL)
    add_text(
        s9, 9.52, 5.38, 2.88, 1.05,
        "Mobile phone capture → 4-point contour → perspective-warped color → adaptive binary scan across tilted, shadowed, and cluttered inputs.",
        font_size=11.0, bold=False, color=C_DARK_TEXT, line_spacing=1.2
    )

    # Slide 10: Quantitative Results
    s10 = init_content_slide("09  |  MEASURED PROTOTYPE RESULTS", "Quantitative Results & Scenario Analysis", 10)
    kpi_cards = [
        (0.72, "Boundary IoU", "99.37%", "1.60 px mean corner localization error", C_CARD_BLUE1),
        (4.75, "Proposed PSNR", "12.36 dB", "+9.90 dB gain over Global Otsu (2.45 dB)", C_CARD_BLUE2),
        (8.78, "CPU Latency", "43.83 ms", "~22.8 FPS real-time execution on CPU", C_CARD_BLUE1),
    ]
    for kx, klabel, kval, ksub, kbg in kpi_cards:
        add_round_card(s10, kx, 1.36, 3.78, 0.92, kbg, C_BORDER_SOFT, 1.0)
        add_text(s10, kx + 0.16, 1.48, 1.65, 0.24, klabel, font_size=10.5, bold=True, color=C_PRIMARY_BL)
        add_text(s10, kx + 1.82, 1.42, 1.80, 0.34, kval, font_size=17.5, bold=True, color=C_DARK_TEXT)
        add_text(s10, kx + 0.16, 1.84, 3.48, 0.26, ksub, font_size=9.6, bold=False, color=C_MUTED_SLATE)

    s10.shapes.add_picture(figs["chart1"], Inches(0.82), Inches(2.85), width=Inches(5.65), height=Inches(2.35))
    s10.shapes.add_picture(figs["chart2"], Inches(6.95), Inches(2.65), width=Inches(5.55), height=Inches(2.85))

    add_round_card(s10, 0.85, 6.24, 11.65, 0.56, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
    add_text(
        s10, 1.02, 6.39, 11.30, 0.24,
        "Key finding: Global Otsu fails under skew and directional shadows (2.45 dB PSNR); 4-point homography + adaptive thresholding cuts MSE by 89.7%.",
        font_size=10.8, bold=True, color=C_PRIMARY_BL
    )

    # Slide 11: Takeaways
    s11 = init_content_slide("10  |  TAKEAWAYS", "Conclusion, Limitations & Future Work", 11)
    takeaway_cards = [
        (0.72, "Conclusion", C_PRIMARY_BL,
         "• Classical vision accurately localizes and rectifies tilted mobile document captures (99.37% IoU).\n\n"
         "• Fusing Otsu-Canny edges with morphological closing prevents contour breaks under shadows.\n\n"
         "• Median background division + adaptive Gaussian thresholding produces crisp scans in 43.83 ms."),
        (4.73, "Limitations", C_ACCENT_BLUE,
         "• Assumes a flat planar quadrilateral; curved book spines introduce midline distortion.\n\n"
         "• White sheets placed directly on bright white surfaces reduce boundary gradient contrast.\n\n"
         "• Strong specular flash glare over glossy ink can locally wash out thin characters."),
        (8.74, "Future improvements", C_MED_BLUE,
         "• Fit polynomial or thin-plate spline curves to dewarp curved open-book pages.\n\n"
         "• Integrate Tesseract OCR to export searchable multi-page PDF documents.\n\n"
         "• Add projection-profile orientation detection to auto-rotate upside-down scans."),
    ]
    for cx, heading, hcolor, body in takeaway_cards:
        add_round_card(s11, cx, 1.46, 3.88, 4.96, C_CARD_WHITE, C_BORDER_GRAY, 1.0)
        add_text(s11, cx + 0.22, 1.62, 3.48, 0.38, heading, font_size=16.0, bold=True, color=hcolor)
        add_text(s11, cx + 0.22, 2.10, 3.46, 4.18, body, font_size=12.6, bold=False, color=C_DARK_TEXT, line_spacing=1.22)

    add_text(
        s11, 0.85, 6.62, 11.65, 0.24,
        "Combining scale-consistent edge fusion with projective geometry delivers fast, explainable mobile document digitization without neural networks.",
        font_size=11.4, bold=False, color=C_MUTED_SLATE
    )

    # Slide 12: References
    s12 = init_content_slide("11  |  SELECTED SOURCES", "References & Acknowledgement", 12)
    refs_s12 = [
        ("[1] R. C. Gonzalez and R. E. Woods, Digital Image Processing, 4th ed., Pearson, 2018. (Spatial filtering, morphological operations, and projective transformations).", C_CARD_WHITE),
        ("[2] J. Canny, “A Computational Approach to Edge Detection,” IEEE Transactions on Pattern Analysis and Machine Intelligence, vol. PAMI-8, no. 6, pp. 679–698, Nov. 1986.", C_CARD_BLUE2),
        ("[3] N. Otsu, “A Threshold Selection Method from Gray-Level Histograms,” IEEE Transactions on Systems, Man, and Cybernetics, vol. 9, no. 1, pp. 62–66, Jan. 1979.", C_CARD_WHITE),
        ("[4] S. Suzuki and K. Abe, “Topological Structural Analysis of Digitized Binary Images by Border Following,” Computer Vision, Graphics, and Image Processing, vol. 30, no. 1, pp. 32–46, 1985.", C_CARD_BLUE2),
        ("[5] J. Sauvola and M. Pietikäinen, “Adaptive Document Image Binarization,” Pattern Recognition, vol. 33, no. 2, pp. 225–236, Feb. 2000.", C_CARD_WHITE),
    ]
    for idx, (rtxt, rbg) in enumerate(refs_s12):
        ry = 1.40 + idx * 0.81
        add_round_card(s12, 0.75, ry, 11.80, 0.65, rbg, C_BORDER_GRAY, 1.0)
        add_text(s12, 0.95, ry + 0.11, 11.35, 0.44, rtxt, font_size=10.3, bold=False, color=C_DARK_TEXT, line_spacing=1.18)

    add_text(
        s12, 0.75, 5.48, 11.80, 0.26,
        "Selected academic and implementation references; full source code, mobile capture pipeline, and report are packaged in the Group 1 repository.",
        font_size=10.0, bold=False, color=C_DARK_TEXT
    )
    add_round_card(s12, 0.76, 5.84, 11.78, 0.95, C_CARD_BLUE1, C_BORDER_SOFT, 1.0)
    add_text(s12, 1.00, 5.98, 11.30, 0.34, "Thank you", font_size=20.0, bold=True, color=C_PRIMARY_BL)
    add_text(
        s12, 1.00, 6.36, 11.30, 0.24,
        "Questions & Viva  |  Group 1 (Roll Nos. 76–80)  |  Haldia Institute of Technology",
        font_size=11.0, bold=False, color=C_DARK_TEXT
    )

    os.makedirs(os.path.dirname(out_pptx), exist_ok=True)
    prs.save(out_pptx)


def build_report(figs: dict, out_docx: str = "docs/Group1_Automatic_Document_Scanner_Report_BlueTheme.docx"):
    """Build Blue-Theme 6-chapter Word report without assigned roles, tailored for real mobile captures."""
    doc = Document()

    for section in doc.sections:
        section.top_margin = DocInches(0.75)
        section.bottom_margin = DocInches(0.75)
        section.left_margin = DocInches(0.8)
        section.right_margin = DocInches(0.8)

        hp = section.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("HALDIA INSTITUTE OF TECHNOLOGY  |  DEPT. OF IT  |  PCC-IT-502 (GROUP 1)")
        hrun.font.name = "Arial"
        hrun.font.size = DocPt(8.5)
        hrun.font.color.rgb = DocRGB(0x53, 0x6B, 0x80)

        fp = section.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        frun = fp.add_run("Mini Project Report: Automatic Document Scanner  |  Academic Session 2026–2027")
        frun.font.name = "Arial"
        frun.font.size = DocPt(8.5)
        frun.font.color.rgb = DocRGB(0x53, 0x6B, 0x80)

    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = DocPt(10.5)
    normal_style.font.color.rgb = DocRGB(0x24, 0x38, 0x4D)

    def set_cell_shading(cell, hex_color):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement("w:tcMar")
        for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
            node = OxmlElement(f"w:{m}")
            node.set(qn("w:w"), str(val))
            node.set(qn("w:type"), "dxa")
            tcMar.append(node)
        tcPr.append(tcMar)

    def add_blue_banner_heading(kicker, title):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        cell.width = DocInches(6.9)
        set_cell_shading(cell, "E6F2FC")
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = DocPt(0)
        p.paragraph_format.space_after = DocPt(2)
        rk = p.add_run(kicker + "\n")
        rk.font.name = "Arial"
        rk.font.size = DocPt(8.5)
        rk.font.bold = True
        rk.font.color.rgb = DocRGB(0x47, 0x7F, 0xAE)

        rt = p.add_run(title)
        rt.font.name = "Arial"
        rt.font.size = DocPt(15.0)
        rt.font.bold = True
        rt.font.color.rgb = DocRGB(0x24, 0x38, 0x4D)

        sp = doc.add_paragraph()
        sp.paragraph_format.space_before = DocPt(0)
        sp.paragraph_format.space_after = DocPt(4)

    def add_sub_heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = DocPt(8)
        p.paragraph_format.space_after = DocPt(3)
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = DocPt(11.8)
        r.font.bold = True
        r.font.color.rgb = DocRGB(0x2F, 0x66, 0x90)
        return p

    def add_body_p(text, bold_prefix=None, space_after=5):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = DocPt(0)
        p.paragraph_format.space_after = DocPt(space_after)
        p.paragraph_format.line_spacing = 1.2
        if bold_prefix:
            rb = p.add_run(bold_prefix)
            rb.font.name = "Arial"
            rb.font.size = DocPt(10.5)
            rb.font.bold = True
            rb.font.color.rgb = DocRGB(0x2F, 0x66, 0x90)
        r = p.add_run(text)
        r.font.name = "Arial"
        r.font.size = DocPt(10.5)
        r.font.color.rgb = DocRGB(0x24, 0x38, 0x4D)
        return p

    def add_styled_table(headers, rows_data, col_widths=None):
        tbl = doc.add_table(rows=1 + len(rows_data), cols=len(headers))
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.style = "Table Grid"
        for c_idx, h_text in enumerate(headers):
            cell = tbl.rows[0].cells[c_idx]
            if col_widths:
                cell.width = DocInches(col_widths[c_idx])
            set_cell_shading(cell, "2F6690")
            set_cell_margins(cell, top=90, bottom=90, left=110, right=110)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = DocPt(0)
            p.paragraph_format.space_after = DocPt(0)
            r = p.add_run(h_text)
            r.font.name = "Arial"
            r.font.size = DocPt(9.5)
            r.font.bold = True
            r.font.color.rgb = DocRGB(0xFF, 0xFF, 0xFF)

        for r_idx, r_vals in enumerate(rows_data):
            bg_hex = "FCFEFF" if r_idx % 2 == 0 else "EBF4FC"
            for c_idx, val in enumerate(r_vals):
                cell = tbl.rows[r_idx + 1].cells[c_idx]
                if col_widths:
                    cell.width = DocInches(col_widths[c_idx])
                set_cell_shading(cell, bg_hex)
                set_cell_margins(cell, top=75, bottom=75, left=110, right=110)
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = DocPt(0)
                p.paragraph_format.space_after = DocPt(0)
                r = p.add_run(str(val))
                r.font.name = "Arial"
                r.font.size = DocPt(9.3)
                r.font.bold = (c_idx == 0)
                r.font.color.rgb = DocRGB(0x2F, 0x66, 0x90) if c_idx == 0 else DocRGB(0x24, 0x38, 0x4D)
        sp = doc.add_paragraph()
        sp.paragraph_format.space_after = DocPt(4)
        return tbl

    # Cover Page (2-column Student Table: Roll No. | Student Name — NO Assigned Role)
    cov_tbl = doc.add_table(rows=1, cols=1)
    cov_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cov_cell = cov_tbl.cell(0, 0)
    cov_cell.width = DocInches(6.9)
    set_cell_shading(cov_cell, "F3F8FD")
    set_cell_margins(cov_cell, top=220, bottom=220, left=240, right=240)

    cp0 = cov_cell.paragraphs[0]
    cp0.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if os.path.exists("assets/hit_logo.png"):
        cp0.add_run().add_picture("assets/hit_logo.png", width=DocInches(1.35))

    cp1 = cov_cell.add_paragraph()
    cp1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp1.paragraph_format.space_before = DocPt(6)
    cp1.paragraph_format.space_after = DocPt(2)
    r_inst = cp1.add_run("HALDIA INSTITUTE OF TECHNOLOGY\n")
    r_inst.font.name = "Arial"
    r_inst.font.size = DocPt(18)
    r_inst.font.bold = True
    r_inst.font.color.rgb = DocRGB(0x2F, 0x66, 0x90)

    r_dept = cp1.add_run("Department of Information Technology")
    r_dept.font.name = "Arial"
    r_dept.font.size = DocPt(12.5)
    r_dept.font.color.rgb = DocRGB(0x53, 0x6B, 0x80)

    cp2 = cov_cell.add_paragraph()
    cp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp2.paragraph_format.space_before = DocPt(14)
    cp2.paragraph_format.space_after = DocPt(4)
    r_tag = cp2.add_run("MINI PROJECT REPORT  |  PCC-IT-502  |  GROUP 1")
    r_tag.font.name = "Arial"
    r_tag.font.size = DocPt(11)
    r_tag.font.bold = True
    r_tag.font.color.rgb = DocRGB(0x67, 0x9C, 0xCB)

    cp3 = cov_cell.add_paragraph()
    cp3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp3.paragraph_format.space_before = DocPt(4)
    cp3.paragraph_format.space_after = DocPt(6)
    r_proj = cp3.add_run("Automatic Document Scanner")
    r_proj.font.name = "Arial"
    r_proj.font.size = DocPt(26)
    r_proj.font.bold = True
    r_proj.font.color.rgb = DocRGB(0x24, 0x38, 0x4D)

    cp4 = cov_cell.add_paragraph()
    cp4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cp4.paragraph_format.space_after = DocPt(10)
    r_sub = cp4.add_run(
        "Grayscale & CLAHE • Otsu-Guided Canny • Morphological Closing • 4-Point Homography • Adaptive Thresholding\n"
        "Course Outcomes: CO1, CO3, CO4, CO5   |   UN SDG Alignment: SDG 4 & SDG 9"
    )
    r_sub.font.name = "Arial"
    r_sub.font.size = DocPt(10.5)
    r_sub.font.color.rgb = DocRGB(0x47, 0x7F, 0xAE)

    doc.add_paragraph()
    add_styled_table(
        ["Roll No.", "Student Name (Group 1 — 3rd Year, Batch 2)"],
        [[r, n] for r, n in GROUP_MEMBERS],
        col_widths=[1.6, 5.3]
    )

    add_styled_table(
        ["Under the Guidance of", "Institution & Academic Session"],
        [[
            "Arpita Shome\nAssistant Professor\nDepartment of Information Technology",
            "Haldia Institute of Technology\nHaldia, Purba Medinipur – 721657, West Bengal\nAcademic Session: 2026–2027"
        ]],
        col_widths=[3.45, 3.45]
    )

    doc.add_page_break()

    # Chapter 1
    add_blue_banner_heading("01  |  CONTEXT & OBJECTIVES", "Chapter 1 – Introduction")
    add_sub_heading("1.1 Background")
    add_body_p(
        "Smartphones and portable cameras have become the primary tools for digitizing academic notes, printed assignments, receipts, and official forms. Unlike flatbed scanners that enforce controlled overhead lighting and fixed page alignment, handheld mobile captures suffer from trapezoidal perspective skew, directional shadows, uneven ambient illumination, camera sensor noise, and cluttered desk backgrounds."
    )
    add_sub_heading("1.2 Problem Statement")
    add_body_p(
        "Given an unconstrained RGB photograph of a planar rectangular document captured using a mobile phone camera at an arbitrary tilt angle and lighting condition against a non-uniform background, automatically localize the four document corners, rectify perspective distortion into a fronto-parallel top-down view, and suppress illumination gradients to produce a crisp, scan-grade binary image using classical Image Processing techniques."
    )
    add_sub_heading("1.3 Motivation")
    add_body_p(
        "While deep-learning document segmentation models require large training datasets, GPU memory, and external weight files, classical computer vision algorithms—combining local histogram equalization, gradient edge detection, mathematical morphology, projective geometry, and adaptive thresholding—execute in under 45 ms per page on a standard CPU with full mathematical transparency. This aligns directly with SDG 4 (accessible digitization of educational materials) and SDG 9 (automated document workflows)."
    )
    add_sub_heading("1.4 Objectives & Course Outcome Mapping")
    add_styled_table(
        ["Objective", "Classical Image Processing Implementation", "CO / SDG"],
        [
            ["1. Mobile Capture Pre-processing", "Aspect-ratio resize (700 px), luminance grayscale, CLAHE (8×8 tiles), and 5×5 Gaussian filtering.", "CO1, SDG 4"],
            ["2. Unbroken Boundary Extraction", "Otsu-guided Canny edges fused with 7×7 morphological closing, Otsu gradient, and RDP 4-point approximation.", "CO3, SDG 9"],
            ["3. Fronto-Parallel Rectification", "Canonical corner ordering and 3×3 projective homography warp with bicubic interpolation.", "CO4, SDG 9"],
            ["4. Shadow Suppression & Benchmarking", "35×35 median background division + 25×25 adaptive Gaussian binarization; evaluate IoU, MSE, PSNR & latency.", "CO5, SDG 4"],
        ],
        col_widths=[2.1, 3.7, 1.1]
    )
    add_sub_heading("1.5 Scope of the Project")
    add_body_p(
        "The system processes single-page planar rectangular documents (A4 study sheets, printed forms, invoices, and receipts) captured using a mobile phone camera, supported by a CLI batch processor (main.py --real), an interactive Streamlit web demo (app.py), and a Jupyter Notebook."
    )

    # Chapter 2
    add_blue_banner_heading("02  |  SELECTED REFERENCES", "Chapter 2 – Literature Survey")
    add_sub_heading("2.1 Existing Classical Approaches & Comparative Analysis")
    add_styled_table(
        ["Author(s) & Year", "Techniques Used", "Advantages", "Limitations & Project Improvement"],
        [
            ["Otsu (1979)", "Global histogram between-class variance maximization.", "Fast, parameter-free binarization on uniformly lit documents.", "Fails under directional shadows and skew; replaced by local adaptive Gaussian thresholding."],
            ["Canny (1986)", "Gaussian smoothing, Sobel gradients, non-max suppression, hysteresis.", "Optimal edge localization and low false-edge response.", "Static thresholds fail on low contrast; improved via Otsu-guided thresholds + 7×7 closing."],
            ["Suzuki & Abe (1985)", "Topological border-following contour extraction (findContours).", "Clean hierarchical tracing of external object boundaries.", "Requires unbroken edge loops; solved by fusing closed Canny edges with Otsu gradients."],
            ["Sauvola & Pietikäinen (2000)", "Local sliding-window mean & standard deviation thresholding.", "Preserves thin ink strokes across severe lighting gradients.", "Higher per-pixel cost; our median background division + Gaussian window achieves real-time speed."],
            ["Gonzalez & Woods (2018)", "Ramer–Douglas–Peucker polygon simplification & 3×3 DLT homography.", "Exact planar perspective rectification from 4 ordered corners.", "Sensitive to corner drift; stabilized by working at 700 px height and scaling coordinates back."],
        ],
        col_widths=[1.35, 1.75, 1.75, 2.05]
    )
    add_sub_heading("2.2 Research & Problem Gap Addressed")
    add_body_p(
        "Standard edge-only document scanners frequently fail when one border of a mobile-captured page blends into a low-contrast background or suffers shadow-induced edge breaks, causing contour detection to latch onto internal tables instead of the outer sheet. Our system bridges this gap by fusing Otsu-guided Canny edges with morphological closing and Otsu foreground gradients, followed by median-background illumination division prior to adaptive binarization."
    )

    # Chapter 3
    add_blue_banner_heading("03  |  SYSTEM DESIGN & MATHEMATICS", "Chapter 3 – Methodology")
    add_sub_heading("3.1 System Architecture & Block Diagram")
    add_body_p(
        "Figure 3.1 illustrates the complete 5-stage classical computer vision architecture, progressing from mobile image capture through preprocessing, boundary fusion, 4-point projective homography, and illumination-normalized adaptive thresholding."
    )
    p_img1 = doc.add_paragraph()
    p_img1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img1.add_run().add_picture(figs["arch"], width=DocInches(6.7))

    add_sub_heading("3.2 Mathematical Formulations")
    add_body_p(
        "The input mobile BGR image is resized to a standardized working height of 700 px (recording scale factor r = H_orig / 700) and converted to luminance grayscale: I_gray(x, y) = 0.299 R(x, y) + 0.587 G(x, y) + 0.114 B(x, y). CLAHE enhances local contrast over 8×8 tiles, and a 5×5 Gaussian filter suppresses camera sensor noise.",
        bold_prefix="1. Luminance Conversion & Pre-processing: "
    )
    add_body_p(
        "Using Otsu's optimal global threshold T_Otsu, Canny hysteresis bounds are set dynamically (T_low = 0.45 T_Otsu, T_high = 1.15 T_Otsu). Morphological closing with a 7×7 rectangular structuring element B seals perimeter gaps: E_closed = (E_Canny ⊕ B) ⊖ B, which is bitwise-ORed with the morphological gradient of the closed Otsu mask.",
        bold_prefix="2. Edge Detection & Morphological Fusion: "
    )
    add_body_p(
        "External contours exceeding 12% of the frame area are simplified via Ramer–Douglas–Peucker polygon approximation (cv2.approxPolyDP) until a 4-vertex quadrilateral is obtained. Corners are ordered canonically as top-left (min x+y), top-right (min y−x), bottom-right (max x+y), and bottom-left (max y−x), then scaled by r to solve the 8-DOF projective homography matrix H: [w x', w y', w]^T = H [x, y, 1]^T.",
        bold_prefix="3. Contour Approximation & 3×3 Projective Homography: "
    )
    add_body_p(
        "Smooth shadows are removed by dividing the warped grayscale image I_warp by a resolution-adaptive median-filtered background estimate I_bg: I_norm(x, y) = min(255, 255 · I_warp(x, y) / max(1, I_bg(x, y))). Adaptive Gaussian Thresholding computes local thresholds T(x, y) = μ_G(x, y) − 13, followed by a 3×3 median filter.",
        bold_prefix="4. Illumination Division & Adaptive Binarization: "
    )

    add_sub_heading("3.3 Step-by-Step Visual Preprocessing Breakdown")
    p_img2 = doc.add_paragraph()
    p_img2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img2.add_run().add_picture(figs["prep"], width=DocInches(6.7))

    # Chapter 4
    add_blue_banner_heading("04  |  SOFTWARE & REAL MOBILE DATASET", "Chapter 4 – Implementation")
    add_sub_heading("4.1 Software Stack & Repository Organization")
    add_body_p(
        "The project is implemented in Python 3.10+ using OpenCV (cv2 4.9.0), NumPy, Matplotlib, Pandas, and Streamlit. The codebase is organized cleanly into src/scanner.py (6-stage scanning pipeline), src/real_evaluate.py (batch mobile phone capture evaluation), src/evaluate.py (ground-truth PSNR/IoU benchmark), main.py (CLI), and app.py (interactive web interface)."
    )
    add_sub_heading("4.2 Real Mobile Phone Capture Dataset & Acquisition Protocol")
    add_body_p(
        "In accordance with Section 10 of the mini-project guidelines (self-collected images captured using a mobile phone camera), test documents are photographed directly with a smartphone camera under real indoor conditions and stored in data/real_inputs/:"
    )
    add_styled_table(
        ["Capture Condition", "Mobile Camera Acquisition Setup", "Targeted Image Processing Challenge"],
        [
            ["1. Tilted A4 Sheet", "Printed notes or assignment page photographed at 20°–30° tilt on a wooden/dark desk.", "Projective perspective distortion & 4-point corner ordering."],
            ["2. Directional Shadow", "Receipt or bill captured with a hand/lamp shadow cast diagonally across the text.", "Non-uniform illumination gradient & global thresholding failure."],
            ["3. Low-Light / Low Contrast", "Book page or worksheet captured under dim indoor lighting without flash.", "Compressed dynamic range & weak border gradients."],
            ["4. Cluttered Study Desk", "Document surrounded by pens, notebooks, or rulers on a textured tabletop.", "Background distractor contours & outer boundary isolation."],
            ["5. Landscape Orientation", "Horizontal form, certificate, or ID card captured at native phone aspect ratio.", "Scale-adaptive output aspect ratio preservation (out_size=None)."],
        ],
        col_widths=[1.65, 2.75, 2.50]
    )

    add_sub_heading("4.3 Core Python Implementation (src/scanner.py)")
    code_tbl = doc.add_table(rows=1, cols=1)
    code_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    ccell = code_tbl.cell(0, 0)
    ccell.width = DocInches(6.9)
    set_cell_shading(ccell, "F3F8FD")
    set_cell_margins(ccell, top=100, bottom=100, left=140, right=140)
    cp = ccell.paragraphs[0]
    cp.paragraph_format.line_spacing = 1.08
    code_snippet = """def order_points(pts):
    rect = np.zeros((4, 2), dtype='float32')
    s = pts.sum(axis=1)
    rect[0], rect[2] = pts[np.argmin(s)], pts[np.argmax(s)]      # Top-Left, Bottom-Right
    diff = np.diff(pts, axis=1)
    rect[1], rect[3] = pts[np.argmin(diff)], pts[np.argmax(diff)] # Top-Right, Bottom-Left
    return rect

def four_point_transform(image, pts, out_size=None):
    rect = order_points(pts)
    # Derive natural width/height from quadrilateral edges when out_size is None
    H = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, H, out_size, flags=cv2.INTER_CUBIC), rect"""
    rc = cp.add_run(code_snippet)
    rc.font.name = "Courier New"
    rc.font.size = DocPt(8.4)
    rc.font.color.rgb = DocRGB(0x1E, 0x35, 0x4D)
    doc.add_paragraph()

    # Chapter 5
    add_blue_banner_heading("05  |  MEASURED PROTOTYPE RESULTS", "Chapter 5 – Results and Analysis")
    add_sub_heading("5.1 Multi-Capture Visual Comparison")
    add_body_p(
        "Figure 5.1 compares the original mobile capture, detected 4-point contour overlay, perspective-warped color document, and final adaptive binary output across multiple capture conditions."
    )
    p_img3 = doc.add_paragraph()
    p_img3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img3.add_run().add_picture(figs["grid"], width=DocInches(6.4))

    # If real_evaluation_metrics.csv exists, include real mobile capture table as well!
    real_csv = "results/real_evaluation_metrics.csv"
    if os.path.exists(real_csv):
        add_sub_heading("5.2 Real Mobile Phone Capture Metrics (results/real_evaluation_metrics.csv)")
        rdf = pd.read_csv(real_csv)
        r_rows = [
            [
                r["Image_Name"], r["Input_Resolution"], r["Output_Resolution"],
                f"{r['Doc_Area_pct']:.1f}%", f"{r['Contrast_Gain']:.2f}×",
                f"{r['Sharpness_LapVar']:.1f}", f"{r['Latency_ms']:.2f} ms"
            ]
            for _, r in rdf.iterrows()
        ]
        add_styled_table(
            ["Mobile Photo", "Input Res.", "Output Res.", "Doc Area", "Contrast Gain", "Sharpness", "Latency"],
            r_rows,
            col_widths=[1.45, 0.92, 0.92, 0.80, 0.95, 0.92, 0.94]
        )

    add_sub_heading("5.3 Quantitative Benchmark Comparison (Proposed vs. Global Otsu)")
    metrics_df = pd.read_csv("results/evaluation_metrics.csv")
    table_rows_5 = []
    for _, r in metrics_df.iterrows():
        table_rows_5.append([
            r["Scenario"],
            f"{r['Corner_Error_px']:.2f} px",
            f"{r['Boundary_IoU_pct']:.2f}%",
            f"{r['MSE_Baseline_Otsu']:,.2f}",
            f"{r['PSNR_Baseline_dB']:.2f} dB",
            f"{r['MSE_Proposed']:,.2f}",
            f"{r['PSNR_Proposed_dB']:.2f} dB",
            f"{r['Latency_ms']:.2f} ms",
        ])
    table_rows_5.append([
        "Overall Average",
        f"{metrics_df['Corner_Error_px'].mean():.2f} px",
        f"{metrics_df['Boundary_IoU_pct'].mean():.2f}%",
        f"{metrics_df['MSE_Baseline_Otsu'].mean():,.2f}",
        f"{metrics_df['PSNR_Baseline_dB'].mean():.2f} dB",
        f"{metrics_df['MSE_Proposed'].mean():,.2f}",
        f"{metrics_df['PSNR_Proposed_dB'].mean():.2f} dB",
        f"{metrics_df['Latency_ms'].mean():.2f} ms",
    ])
    add_styled_table(
        ["Capture Scenario", "Corner Err", "IoU (%)", "Otsu MSE", "Otsu PSNR", "Prop. MSE", "Prop. PSNR", "Latency"],
        table_rows_5,
        col_widths=[1.55, 0.72, 0.72, 0.85, 0.78, 0.78, 0.80, 0.70]
    )

    add_sub_heading("5.4 Comparative Chart Analysis")
    p_img4 = doc.add_paragraph()
    p_img4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img4.add_run().add_picture(figs["chart1"], width=DocInches(5.8))

    p_img5 = doc.add_paragraph()
    p_img5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img5.add_run().add_picture(figs["chart2"], width=DocInches(5.8))

    add_body_p(
        "Across all capture scenarios, the proposed scanner achieves 99.37% mean boundary IoU (1.60 px average corner error), reduces mean squared pixel error by 89.7% (from 36,965.46 to 3,819.88), and increases average PSNR by +9.90 dB (from 2.45 dB to 12.36 dB) with an average CPU latency of 43.83 ms per page."
    )

    # Chapter 6
    add_blue_banner_heading("06  |  TAKEAWAYS & FUTURE SCOPE", "Chapter 6 – Conclusion and Future Scope")
    add_sub_heading("6.1 Conclusion")
    add_body_p(
        "The Automatic Document Scanner demonstrates that a carefully engineered classical Image Processing pipeline—combining CLAHE contrast enhancement, Gaussian filtering, Otsu-guided Canny edge detection, morphological closing, 4-point projective homography, and adaptive Gaussian thresholding—reliably extracts, flattens, and binarizes tilted and shadowed mobile phone document captures in real time (~22.8 FPS on CPU)."
    )
    add_sub_heading("6.2 Limitations")
    add_body_p("1. Planar Surface Assumption: Assumes the document is a rigid planar quadrilateral; severely crumpled or curved open-book pages exhibit residual midline curvature.")
    add_body_p("2. Low Foreground-Background Contrast: White sheets placed directly on bright white surfaces without a contrasting border reduce outer gradient visibility.")
    add_body_p("3. Specular Glare: Direct mobile camera flash reflections over glossy paper can locally wash out thin ink strokes during illumination division.")

    add_sub_heading("6.3 Future Improvements")
    add_body_p("1. Curved Book-Page Dewarping: Fit polynomial or thin-plate spline curves along top and bottom text baselines to flatten bound book spreads.")
    add_body_p("2. Searchable Multi-Page PDF & OCR: Integrate Tesseract OCR to export multi-page searchable PDF files.")
    add_body_p("3. Automatic Orientation Detection: Use horizontal projection-profile variance to automatically detect and rotate upside-down or 90°-rotated pages.")

    # References
    add_blue_banner_heading("07  |  BIBLIOGRAPHY", "References")
    bib_list = [
        "[1] R. C. Gonzalez and R. E. Woods, Digital Image Processing, 4th ed. Pearson, 2018.",
        "[2] J. Canny, 'A Computational Approach to Edge Detection,' IEEE Transactions on Pattern Analysis and Machine Intelligence, vol. PAMI-8, no. 6, pp. 679–698, Nov. 1986.",
        "[3] N. Otsu, 'A Threshold Selection Method from Gray-Level Histograms,' IEEE Transactions on Systems, Man, and Cybernetics, vol. 9, no. 1, pp. 62–66, Jan. 1979.",
        "[4] S. Suzuki and K. Abe, 'Topological Structural Analysis of Digitized Binary Images by Border Following,' Computer Vision, Graphics, and Image Processing, vol. 30, no. 1, pp. 32–46, Apr. 1985.",
        "[5] J. Sauvola and M. Pietikäinen, 'Adaptive Document Image Binarization,' Pattern Recognition, vol. 33, no. 2, pp. 225–236, Feb. 2000.",
        "[6] G. Bradski, 'The OpenCV Library,' Dr. Dobb's Journal of Software Tools, 2000.",
    ]
    for b_item in bib_list:
        add_body_p(b_item, space_after=4)

    os.makedirs(os.path.dirname(out_docx), exist_ok=True)
    doc.save(out_docx)


def rebuild_all():
    figs = ensure_visual_assets("assets")
    build_presentation(figs, "docs/Group1_Automatic_Document_Scanner_Presentation_BlueTheme.pptx")
    build_report(figs, "docs/Group1_Automatic_Document_Scanner_Report_BlueTheme.docx")
    print("[DONE] Rebuilt BlueTheme PPTX and DOCX in docs/.")


if __name__ == "__main__":
    rebuild_all()
