"""Signature-based platform/page classification (closed-world)."""

from __future__ import annotations

from dataclasses import dataclass

from snapfolio.document import Document
from snapfolio.extractors.configs import PLATFORM_CONFIGS, PlatformConfig


@dataclass
class ClassificationResult:
    platform: PlatformConfig | None
    page_id: str | None
    rejected: bool
    reason: str = ""


def _match_signature(doc: Document, sig: tuple[str, ...], any_of: tuple[str, ...] | None = None) -> bool:
    if any_of:
        if not doc.has_any_of(*any_of):
            return False
    return doc.has_all(*sig)


def classify(doc: Document) -> ClassificationResult:
    """
    Match document against known platform signatures.
    Returns rejected=True if no match (closed-world).
    """
    for config in PLATFORM_CONFIGS:
        for page in config.pages:
            if _match_signature(doc, page.signature, page.signature_any_of):
                return ClassificationResult(
                    platform=config,
                    page_id=page.page_id,
                    rejected=False,
                )

    return ClassificationResult(
        platform=None,
        page_id=None,
        rejected=True,
        reason="Screenshot does not match any known platform signature",
    )
