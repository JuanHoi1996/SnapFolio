"""Command-line interface for SnapFolio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from snapfolio.export import export_csv, export_xlsx
from snapfolio.ocr import dump_fixture, get_engine
from snapfolio.ocr_audit import (
    audit_image,
    collect_images,
    write_audit_files,
    write_batch_summary,
)
from snapfolio.ml.dataset import build_weak_dataset, save_dataset
from snapfolio.ml.train import train_and_evaluate
from snapfolio.pipeline import PipelineError, UnknownPlatformError, process_images


def _collect_images(input_dir: Path) -> list[Path]:
    return collect_images(input_dir)


def cmd_process(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"Error: not a directory: {input_dir}", file=sys.stderr)
        return 1

    images = _collect_images(input_dir)
    if not images:
        print(f"Error: no images found in {input_dir}", file=sys.stderr)
        return 1

    try:
        records = process_images(images)
    except UnknownPlatformError as e:
        print(f"Rejected: {e}", file=sys.stderr)
        return 2
    except PipelineError as e:
        print(f"Pipeline error: {e}", file=sys.stderr)
        return 1

    output = Path(args.output)
    if output.suffix.lower() == ".csv":
        export_csv(records, output)
    else:
        if output.suffix.lower() not in (".xlsx", ".xls"):
            output = output.with_suffix(".xlsx")
        export_xlsx(records, output)

    print(f"Wrote {len(records)} holdings to {output}")
    for r in records:
        flag_str = f" [{','.join(r.flags)}]" if r.flags else ""
        print(f"  {r.name} ({r.code or 'no code'}) conf={r.confidence:.2f}{flag_str}")
    return 0


def _fixture_path_for_image(image: Path, output_dir: Path) -> Path:
    return output_dir / f"{image.stem}.fixture.txt"


def cmd_dump_ocr(args: argparse.Namespace) -> int:
    input_path = Path(args.input)

    if input_path.is_file():
        out = Path(args.output) if args.output else input_path.with_suffix(".fixture.txt")
        dump_fixture(input_path, out)
        print(f"Wrote fixture: {out}")
        return 0

    if not input_path.is_dir():
        print(f"Error: path not found: {input_path}", file=sys.stderr)
        return 1

    images = _collect_images(input_path)
    if not images:
        print(f"Error: no images found in {input_path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output) if args.output else input_path / "fixtures"
    output_dir.mkdir(parents=True, exist_ok=True)

    for image in images:
        out = _fixture_path_for_image(image, output_dir)
        dump_fixture(image, out)
        print(f"Wrote fixture: {out}")

    print(f"Dumped {len(images)} fixture(s) to {output_dir}")
    return 0


def _ensure_fixtures(
    images: list[Path],
    fixtures_dir: Path,
    *,
    skip_if_exists: bool = True,
) -> list[Path]:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for image in images:
        out = _fixture_path_for_image(image, fixtures_dir)
        if skip_if_exists and out.exists():
            paths.append(out)
            continue
        dump_fixture(image, out)
        print(f"Wrote fixture: {out}")
        paths.append(out)
    return paths


def cmd_train_classifier(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    fixtures_dir = Path(args.fixtures_dir) if args.fixtures_dir else output_dir.parent / "ml_fixtures"

    images: list[Path] = []
    for dir_arg in (args.input_dir, args.extra_dir):
        if not dir_arg:
            continue
        input_dir = Path(dir_arg)
        if not input_dir.is_dir():
            print(f"Error: not a directory: {input_dir}", file=sys.stderr)
            return 1
        images.extend(_collect_images(input_dir))

    if not images and not fixtures_dir.is_dir():
        print("Error: no images found and no fixtures directory", file=sys.stderr)
        return 1

    if fixtures_dir.is_dir() and list(fixtures_dir.glob("*.fixture.txt")):
        fixture_paths = sorted(fixtures_dir.glob("*.fixture.txt"))
        print(f"Using {len(fixture_paths)} existing fixture(s) from {fixtures_dir}")
    elif images:
        print(f"Dumping OCR fixtures to {fixtures_dir} ...")
        fixture_paths = _ensure_fixtures(images, fixtures_dir, skip_if_exists=True)
    else:
        print(f"Error: no fixtures in {fixtures_dir}", file=sys.stderr)
        return 1

    print("Building weak-supervised dataset ...")
    df = build_weak_dataset(fixture_paths)
    if df.empty:
        print("Error: empty dataset (all documents rejected or no alignments)", file=sys.stderr)
        return 1

    dataset_path = save_dataset(df, output_dir.parent / "ml_dataset.csv")
    print(f"Dataset: {len(df)} rows -> {dataset_path}")
    print(f"  labels: {df['label'].value_counts().to_dict()}")
    print(f"  platforms: {sorted(df['platform'].unique())}")

    print("Training RandomForest ...")
    report_path = train_and_evaluate(df, output_dir)
    print(f"Evaluation report: {report_path}")
    print(f"Model: {output_dir / 'model.joblib'}")

    report_text = report_path.read_text(encoding="utf-8")
    for line in report_text.splitlines():
        if "Numeric avg F1" in line or "LOPO mean F1" in line or "5-fold reference F1" in line:
            print(line.strip())

    return 0


def cmd_audit_ocr(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    images = collect_images(input_path)
    if not images:
        print(f"Error: no images found at {input_path}", file=sys.stderr)
        return 1

    if args.output:
        output_dir = Path(args.output)
    elif input_path.is_dir():
        output_dir = input_path / "ocr_audit"
    else:
        output_dir = Path("ocr_audit")

    engine = get_engine()
    audits = []
    for image in images:
        audit = audit_image(image, engine)
        audits.append(audit)
        txt_path, _ = write_audit_files(audit, output_dir)
        print(f"Wrote audit: {txt_path}")

    summary = write_batch_summary(audits, output_dir)
    print(f"Wrote summary: {summary} ({len(audits)} image(s))")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="snapfolio", description="SnapFolio holdings extractor")
    sub = parser.add_subparsers(dest="command", required=True)

    p_process = sub.add_parser("process", help="Process screenshots in a directory")
    p_process.add_argument("--input-dir", required=True, help="Directory containing screenshots")
    p_process.add_argument("--output", required=True, help="Output .xlsx or .csv path")
    p_process.set_defaults(func=cmd_process)

    p_dump = sub.add_parser("dump-ocr", help="Dump OCR tokens to fixture file(s)")
    p_dump.add_argument(
        "input",
        help="Screenshot image path, or directory of images (batch mode)",
    )
    p_dump.add_argument(
        "-o",
        "--output",
        help="Output fixture path (single image), or output directory (batch; default: <input>/fixtures)",
    )
    p_dump.set_defaults(func=cmd_dump_ocr)

    p_audit = sub.add_parser(
        "audit-ocr",
        help="Write human/agent-readable OCR token audits (+ SUMMARY.md)",
    )
    p_audit.add_argument(
        "input",
        help="Screenshot image path, or directory of images",
    )
    p_audit.add_argument(
        "-o",
        "--output",
        help="Output directory (default: <input>/ocr_audit or ./ocr_audit)",
    )
    p_audit.set_defaults(func=cmd_audit_ocr)

    p_train = sub.add_parser(
        "train-classifier",
        help="Build weak-supervised token dataset and train RandomForest classifier",
    )
    p_train.add_argument(
        "--input-dir",
        default="testset2",
        help="Primary image directory (default: testset2)",
    )
    p_train.add_argument(
        "--extra-dir",
        default="minimaltestset",
        help="Additional image directory (default: minimaltestset)",
    )
    p_train.add_argument(
        "--output-dir",
        default="output/ml",
        help="Directory for model, meta, and eval report (default: output/ml)",
    )
    p_train.add_argument(
        "--fixtures-dir",
        help="Use existing OCR fixtures (skip OCR); default: output/ml_fixtures",
    )
    p_train.set_defaults(func=cmd_train_classifier)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
