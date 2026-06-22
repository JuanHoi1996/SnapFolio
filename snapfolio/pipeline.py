"""Orchestrate the full extraction pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from snapfolio.classify import classify
from snapfolio.document import build_document, parse_fixture
from snapfolio.extractors.base import extract_document
from snapfolio.models import PartialRecord, PositionRecord
from snapfolio.ocr import run_ocr
from snapfolio.reconcile import merge_partials
from snapfolio.validate import validate_records


class PipelineError(Exception):
    pass


class UnknownPlatformError(PipelineError):
    pass


def ingest_image(
    image_path: str | Path,
    engine: Any | None = None,
) -> tuple[Any, str]:
    """OCR ingest -> Document."""
    raw, width, height = run_ocr(image_path, engine)
    doc = build_document(raw, width, height, str(image_path))
    return doc, str(image_path)


def ingest_fixture(fixture_path: str | Path) -> Any:
    return parse_fixture(fixture_path)


def process_document(doc: Any, source_image: str) -> list[PartialRecord]:
    result = classify(doc)
    if result.rejected or result.platform is None:
        raise UnknownPlatformError(result.reason)

    return extract_document(
        doc,
        result.platform,
        source_image,
        page_id=result.page_id,
    )


def process_images(
    image_paths: list[str | Path],
    engine: Any | None = None,
) -> list[PositionRecord]:
    """Full pipeline: OCR -> classify -> extract -> reconcile -> validate."""
    all_partials: list[PartialRecord] = []

    for path in image_paths:
        doc, source = ingest_image(path, engine)
        partials = process_document(doc, source)
        all_partials.extend(partials)

    merged = merge_partials(all_partials)
    return validate_records(merged)


def process_fixtures(fixture_paths: list[str | Path]) -> list[PositionRecord]:
    """Pipeline using pre-dumped OCR fixtures (no OCR engine needed)."""
    all_partials: list[PartialRecord] = []

    for path in fixture_paths:
        doc = ingest_fixture(path)
        partials = process_document(doc, str(path))
        all_partials.extend(partials)

    merged = merge_partials(all_partials)
    return validate_records(merged)
