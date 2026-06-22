"""RapidOCR wrapper producing raw tokens with bounding boxes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

_engine: Any | None = None


def get_engine(engine: Any | None = None) -> Any:
    """Lazy singleton RapidOCR engine; inject shared engine for batch runs."""
    global _engine
    if engine is not None:
        return engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def load_image_size(image_path: str | Path) -> tuple[int, int]:
    with Image.open(image_path) as img:
        return img.size


def run_ocr(
    image_path: str | Path,
    engine: Any | None = None,
) -> tuple[list[tuple[list[list[float]], str, float]], int, int]:
    """
    Run OCR on an image file.
    Returns (raw_tokens, width, height) where each token is (bbox, text, confidence).
    """
    image_path = Path(image_path)
    ocr = get_engine(engine)
    result, _ = ocr(str(image_path))
    width, height = load_image_size(image_path)

    tokens: list[tuple[list[list[float]], str, float]] = []
    if result:
        for item in result:
            bbox, text, conf = item[0], item[1], float(item[2])
            tokens.append((bbox, text, conf))
    return tokens, width, height


def dump_fixture(image_path: str | Path, output_path: str | Path, engine: Any | None = None) -> None:
    """Write OCR tokens to fixture format for regression tests."""
    raw, width, height = run_ocr(image_path, engine)
    lines = [f"# image: {width}x{height}"]
    for bbox, text, conf in raw:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        lines.append(f"{x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}\t{conf:.4f}\t{text}")
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
