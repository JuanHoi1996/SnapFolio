"""Human/agent-readable OCR token audits for ML feasibility checks."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from snapfolio.document import Document, build_document, cluster_rows
from snapfolio.ocr import run_ocr

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_SIX_DIGIT = re.compile(r"(?<!\d)\d{6}(?!\d)")
_DIGIT = re.compile(r"\d")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_LABEL_GLUE = re.compile(
    r"(持仓|市值|份额|净值|现价|成本|可用|数量|金额|资产).{0,2}[\d,，\.。]+"
    r"|[\d,，\.。]+.{0,2}(持仓|市值|份额|净值|现价|成本)"
)


@dataclass
class TokenAuditRow:
    index: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float
    flags: list[str]


@dataclass
class ImageAudit:
    source: str
    width: int
    height: int
    token_count: int
    mean_confidence: float
    low_conf_count: int
    row_count: int
    flag_counts: dict[str, int]
    tokens: list[TokenAuditRow]


def collect_images(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() in _IMAGE_EXTS:
        return [path]
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.suffix.lower() in _IMAGE_EXTS)


def _token_flags(text: str, confidence: float) -> list[str]:
    flags: list[str] = []
    if confidence < 0.7:
        flags.append("low_conf")
    if _SIX_DIGIT.search(text.replace(" ", "")):
        flags.append("has_6digit")
    digit_n = len(_DIGIT.findall(text))
    cjk_n = len(_CJK.findall(text))
    if digit_n and digit_n / max(len(text), 1) >= 0.5:
        flags.append("digit_heavy")
    if cjk_n and cjk_n / max(len(text), 1) >= 0.4:
        flags.append("cjk_heavy")
    if _LABEL_GLUE.search(text):
        flags.append("label_value_glue")
    if "%" in text or "＋" in text or ("+" in text and digit_n):
        flags.append("pct_or_signed")
    if "，" in text or "。" in text:
        flags.append("fullwidth_punct")
    return flags


def audit_document(doc: Document, *, source_name: str | None = None) -> ImageAudit:
    name = source_name or Path(doc.source_path).name or "unknown"
    rows: list[TokenAuditRow] = []
    flag_counts: dict[str, int] = {}
    confs: list[float] = []

    ordered = sorted(enumerate(doc.tokens), key=lambda it: (it[1].y0, it[1].x0))
    for display_i, (orig_i, tok) in enumerate(ordered):
        flags = _token_flags(tok.text, tok.confidence)
        for f in flags:
            flag_counts[f] = flag_counts.get(f, 0) + 1
        confs.append(tok.confidence)
        rows.append(
            TokenAuditRow(
                index=display_i,
                text=tok.text,
                x0=tok.x0,
                y0=tok.y0,
                x1=tok.x1,
                y1=tok.y1,
                confidence=tok.confidence,
                flags=flags,
            )
        )

    clustered = cluster_rows(doc.tokens, doc.median_token_height() * 0.55)
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return ImageAudit(
        source=name,
        width=doc.image_width,
        height=doc.image_height,
        token_count=len(rows),
        mean_confidence=mean_conf,
        low_conf_count=flag_counts.get("low_conf", 0),
        row_count=len(clustered),
        flag_counts=flag_counts,
        tokens=rows,
    )


def audit_image(image_path: Path, engine: Any | None = None) -> ImageAudit:
    raw, width, height = run_ocr(image_path, engine)
    doc = build_document(raw, width, height, str(image_path))
    return audit_document(doc, source_name=image_path.name)


def format_audit_text(audit: ImageAudit) -> str:
    lines = [
        f"# source: {audit.source}",
        f"# size: {audit.width}x{audit.height}",
        f"# tokens: {audit.token_count}",
        f"# rows_clustered: {audit.row_count}",
        f"# mean_conf: {audit.mean_confidence:.4f}",
        f"# low_conf: {audit.low_conf_count}",
        f"# flags: {json.dumps(audit.flag_counts, ensure_ascii=False)}",
        "#",
        "# idx  y0     x0-x1          conf   flags                 text",
        "# ---  -----  -------------  -----  --------------------  ----",
    ]
    for t in audit.tokens:
        flag_s = ",".join(t.flags) if t.flags else "-"
        lines.append(
            f"{t.index:03d}  {t.y0:.3f}  {t.x0:.3f}-{t.x1:.3f}  "
            f"{t.confidence:.3f}  {flag_s:<20}  {t.text}"
        )
    return "\n".join(lines) + "\n"


def write_audit_files(audit: ImageAudit, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(audit.source).stem
    txt_path = output_dir / f"{stem}.audit.txt"
    json_path = output_dir / f"{stem}.audit.json"
    txt_path.write_text(format_audit_text(audit), encoding="utf-8")
    json_path.write_text(
        json.dumps(asdict(audit), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return txt_path, json_path


def write_batch_summary(audits: list[ImageAudit], output_dir: Path) -> Path:
    """Write SUMMARY.md for human / subagent review of token stability."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "SUMMARY.md"
    total_tokens = sum(a.token_count for a in audits)
    total_low = sum(a.low_conf_count for a in audits)
    all_flags: dict[str, int] = {}
    for a in audits:
        for k, v in a.flag_counts.items():
            all_flags[k] = all_flags.get(k, 0) + v

    lines = [
        "# OCR Token Audit Summary",
        "",
        f"- images: {len(audits)}",
        f"- total_tokens: {total_tokens}",
        f"- mean_tokens_per_image: {total_tokens / len(audits):.1f}" if audits else "- mean_tokens_per_image: 0",
        f"- low_conf_tokens: {total_low} ({100 * total_low / max(total_tokens, 1):.1f}%)",
        f"- aggregate_flags: `{json.dumps(all_flags, ensure_ascii=False)}`",
        "",
        "## Per image",
        "",
        "| source | tokens | rows | mean_conf | low_conf | glue | 6digit |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for a in audits:
        lines.append(
            f"| `{a.source}` | {a.token_count} | {a.row_count} | "
            f"{a.mean_confidence:.3f} | {a.low_conf_count} | "
            f"{a.flag_counts.get('label_value_glue', 0)} | "
            f"{a.flag_counts.get('has_6digit', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Stability checklist for token-field RF",
            "",
            "Review each `*.audit.txt` and answer:",
            "1. Are holdings rows visually separable by y-clustering?",
            "2. Are name / code / quantity / price / amount usually **distinct tokens**?",
            "3. How often is label glued to value (`label_value_glue`)?",
            "4. How noisy is chrome (tabs, ads, timestamps) vs business tokens?",
            "5. Would handcrafted features (x/y norms, digit_ratio, has_6digit, row position) "
            "likely separate `name/code/quantity/unit_price/amount/noise`?",
            "",
            "## Files",
            "",
            "Per image: `<stem>.audit.txt` (readable) + `<stem>.audit.json` (structured).",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
