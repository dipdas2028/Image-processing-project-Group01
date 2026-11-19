"""Command-Line Interface for Group 1 Automatic Document Scanner (PCC-IT-502)."""

import argparse
import os
import cv2

from src.evaluate import run_evaluation
from src.real_evaluate import run_real_evaluation
from src.scanner import scan_document
from build_docs import rebuild_all


def parse_args():
    parser = argparse.ArgumentParser(
        description="Automatic Document Scanner using Classical Image Processing (Group 1)"
    )
    parser.add_argument(
        "--real",
        action="store_true",
        help="Scan all real mobile phone photos in data/real_inputs/ and auto-update DOCX report & PPTX.",
    )
    parser.add_argument(
        "--real-dir",
        type=str,
        default="data/real_inputs",
        help="Folder containing your real mobile phone document photos (default: data/real_inputs).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run baseline PSNR/IoU benchmark evaluation and update DOCX report & PPTX.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Path to a single mobile document photo (JPG/PNG) to scan.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/scanned_output.png",
        help="Output path for the binarized scanned document when using --input.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.real:
        print(f"[INFO] Scanning all real mobile captures in '{args.real_dir}'...")
        df = run_real_evaluation(input_dir=args.real_dir)
        print("\n=== Real Mobile Capture Evaluation Summary ===")
        print(df.to_string(index=False))
        rebuild_all()
        print("\n[DONE] Saved real scans to results/real_outputs/, metrics to results/real_evaluation_metrics.csv, comparison grid to assets/real_results_grid.png, and updated docs/.")
    elif args.input is not None:
        if not os.path.exists(args.input):
            raise FileNotFoundError(f"Input image not found: {args.input}")
        img = cv2.imread(args.input)
        res = scan_document(img, out_size=None)
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        cv2.imwrite(args.output, res["scanned_binary"])
        color_out = os.path.splitext(args.output)[0] + "_color.png"
        cv2.imwrite(color_out, res["warped_color"])
        print(f"[DONE] Scanned '{args.input}' in {res['processing_time_ms']:.2f} ms")
        print(f"       Binary output: {args.output}")
        print(f"       Color warped : {color_out}")
    else:
        print("[INFO] Running benchmark evaluation and building BlueTheme documents...")
        df = run_evaluation()
        print("\n=== Benchmark Evaluation Summary ===")
        print(df.to_string(index=False))
        rebuild_all()
        print("\n[DONE] Outputs saved to results/, assets/, and docs/.")


if __name__ == "__main__":
    main()
