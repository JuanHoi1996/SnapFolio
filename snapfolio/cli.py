"""Command-line interface for SnapFolio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from snapfolio.export import export_csv, export_xlsx
from snapfolio.ocr import dump_fixture
from snapfolio.pipeline import PipelineError, UnknownPlatformError, process_images


def _collect_images(input_dir: Path) -> list[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    return sorted(p for p in input_dir.iterdir() if p.suffix.lower() in exts)


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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
