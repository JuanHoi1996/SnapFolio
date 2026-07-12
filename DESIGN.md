# SnapFolio Design

## Overview

SnapFolio extracts structured investment holdings from screenshots of Chinese broker / fund mobile apps using **local offline OCR** (RapidOCR). The design prioritizes **robustness** and **graceful failure** — unknown platforms are rejected, and suspicious values are flagged rather than silently emitted.

## Pipeline Stages

```
Image(s) → OCR Ingest → Normalize → Classify → Extract → Reconcile → Validate → Export
```

| Stage | Module | Responsibility |
|-------|--------|----------------|
| 1. OCR Ingest | `ocr.py` | RapidOCR → raw tokens `[bbox, text, confidence]` |
| 2. Normalize | `document.py` | Relative coords `[0,1]`, `Token` / `Document` model |
| 3. Classify | `classify.py` | Signature match → `PlatformConfig`, or reject |
| 4. Extract | `extractors/` | Generic engines driven by declarative config |
| 5. Reconcile | `reconcile.py` | Merge partial records across images by normalized name |
| 6. Validate | `validate.py` | `amount ≈ quantity × unit_price`, confidence flags |
| 7. Export | `export.py` | xlsx (code as text) / csv (utf-8-sig) |

## Core Principles

### Closed-world classification
Only five platforms are supported. If OCR text matches no known signature, the pipeline **rejects** the image with an explicit error — it never guesses a platform.

### Relative geometry only
All spatial logic uses coordinates normalized to `[0, 1]` by image width/height at ingest. **No absolute pixel thresholds** appear in extraction logic. Row clustering tolerance is derived from median token height; column positions come from header token x-centers.

### Multi-strategy field resolution
For each field, extraction tries strategies in order:

1. **inline** — label and value merged in one OCR token (`持仓数24500`)
2. **spatial** — value near label anchor (right / below) within relative max distance
3. **regex** — page-level pattern fallback
4. **None** — field left empty (partial record)

### Validation is first-class
Every final `PositionRecord` carries `confidence` and `flags`. Cross-check: `amount ≈ quantity × unit_price` within 1.5% tolerance. Mismatches and incomplete fields get `needs_review`.

## Two Layout Archetypes

### LIST (repeating rows)
Platforms: 招商证券, 腾讯微证券, 国信金太阳

- Detect column anchors from **header token x-positions** (dynamic)
- Cluster body tokens into rows by y (tolerance = fraction of median token height)
- Cross value = row × column intersection

### DETAIL (key-value card)
Platforms: 支付宝基金, 微信理财通

- Anchor on label tokens
- Find value by relative direction (right / below) within `max_distance` (e.g. 0.4 of image width)

## Platform Configuration

A platform is a declarative `PlatformConfig` in `extractors/configs.py`:

- `signature` keywords for classification
- `archetype`: `list` or `detail`
- `fields`: label/column mapping per field
- No per-platform parser classes — only config + generic engines

Adding a platform = adding a config entry.

## Multi-page Reconciliation (理财通)

微信理财通 uses two page types:

- **Page A** (`持有中`): name + code only → partial record (expected)
- **Page B** (`持有资产` detail): name + amount + quantity + unit_price (may lack code)

`reconcile.py` merges partials by **normalized name** across images. This is the generic multi-image path — not a special-case parser.

## Data Model

- `FieldObservation` — single field with value, confidence, winning strategy
- `PartialRecord` — per-image, may be incomplete
- `PositionRecord` — final reconciled holding with provenance and flags

## Fixture Workflow

`dump-ocr` writes OCR tokens to a text fixture (absolute pixel coords + header dimensions). Tests load fixtures without re-running OCR, enabling a hand-curated golden set.
