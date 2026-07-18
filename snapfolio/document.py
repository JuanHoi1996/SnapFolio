"""Token, Document, and spatial primitives for relative-geometry extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from snapfolio.ocr_normalize import normalize_ocr_text


@dataclass
class Token:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def contains_text(self, needle: str, case_sensitive: bool = False) -> bool:
        hay = self.text if case_sensitive else self.text.lower()
        n = needle if case_sensitive else needle.lower()
        return n in hay


@dataclass
class Document:
    tokens: list[Token]
    image_width: int
    image_height: int
    source_path: str = ""

    def find_tokens_containing(self, needle: str) -> list[Token]:
        return [t for t in self.tokens if t.contains_text(needle)]

    def has_all(self, *needles: str) -> bool:
        """True iff every needle appears in at least one token (AND semantics)."""
        return all(any(t.contains_text(n) for t in self.tokens) for n in needles)

    def has_any(self, *needles: str) -> bool:
        """Deprecated alias for has_all — name historically mismatched AND semantics."""
        return self.has_all(*needles)

    def has_any_of(self, *needles: str) -> bool:
        """True iff at least one needle appears in some token (OR semantics)."""
        return any(any(t.contains_text(n) for t in self.tokens) for n in needles)

    def median_token_height(self) -> float:
        if not self.tokens:
            return 0.02
        heights = sorted(t.height for t in self.tokens)
        return heights[len(heights) // 2]


def normalize_bbox(
    bbox: list[list[float]], width: int, height: int
) -> tuple[float, float, float, float]:
    xs = [p[0] for p in bbox]
    ys = [p[1] for p in bbox]
    return (
        min(xs) / width,
        min(ys) / height,
        max(xs) / width,
        max(ys) / height,
    )


def build_document(
    raw_tokens: list[tuple[list[list[float]], str, float]],
    width: int,
    height: int,
    source_path: str = "",
) -> Document:
    tokens: list[Token] = []
    for bbox, text, conf in raw_tokens:
        if not text or not text.strip():
            continue
        x0, y0, x1, y1 = normalize_bbox(bbox, width, height)
        tokens.append(Token(normalize_ocr_text(text.strip()), x0, y0, x1, y1, float(conf)))
    return Document(tokens, width, height, source_path)


def cluster_rows(tokens: list[Token], y_tolerance: float | None = None) -> list[list[Token]]:
    """Cluster tokens into horizontal rows by y-center proximity."""
    if not tokens:
        return []
    if y_tolerance is None:
        heights = [t.height for t in tokens]
        y_tolerance = (sorted(heights)[len(heights) // 2]) * 0.6

    sorted_tokens = sorted(tokens, key=lambda t: t.cy)
    rows: list[list[Token]] = []
    current_row: list[Token] = [sorted_tokens[0]]
    current_y = sorted_tokens[0].cy

    for tok in sorted_tokens[1:]:
        if abs(tok.cy - current_y) <= y_tolerance:
            current_row.append(tok)
            current_y = sum(t.cy for t in current_row) / len(current_row)
        else:
            rows.append(sorted(current_row, key=lambda t: t.x0))
            current_row = [tok]
            current_y = tok.cy
    rows.append(sorted(current_row, key=lambda t: t.x0))
    return rows


def detect_column_anchors(header_tokens: list[Token]) -> list[float]:
    """Return x-centers of header column anchors, sorted left-to-right."""
    return sorted(t.cx for t in header_tokens)


def assign_token_to_column(token: Token, column_xs: list[float]) -> int:
    """Assign token to nearest column by x-center."""
    if not column_xs:
        return 0
    return min(range(len(column_xs)), key=lambda i: abs(token.cx - column_xs[i]))


def value_near_label(
    doc: Document,
    label: str,
    direction: str = "right",
    max_distance: float = 0.4,
) -> Token | None:
    """
    Find value token relative to a label anchor.
    direction: 'right' | 'below' | 'either'
    """
    label_tokens = doc.find_tokens_containing(label)
    if not label_tokens:
        return None

    label_tok = min(label_tokens, key=lambda t: len(t.text))
    candidates: list[tuple[float, Token]] = []

    for tok in doc.tokens:
        if tok is label_tok or label in tok.text:
            continue

        if direction in ("right", "either"):
            if tok.x0 >= label_tok.x1 - 0.01 and abs(tok.cy - label_tok.cy) < 0.03:
                dist = tok.x0 - label_tok.x1
                if 0 <= dist <= max_distance:
                    candidates.append((dist, tok))

        if direction in ("below", "either"):
            if tok.y0 >= label_tok.y1 - 0.01:
                x_overlap = not (tok.x1 < label_tok.x0 or tok.x0 > label_tok.x1)
                dist = tok.y0 - label_tok.y1
                if dist <= max_distance and (x_overlap or abs(tok.cx - label_tok.cx) < 0.15):
                    candidates.append((dist + 0.5, tok))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def tokens_in_y_band(tokens: list[Token], y0: float, y1: float) -> list[Token]:
    return [t for t in tokens if t.cy >= y0 and t.cy <= y1]


def same_row(a: Token, b: Token, tolerance: float | None = None) -> bool:
    tol = tolerance if tolerance is not None else max(a.height, b.height) * 0.8
    return abs(a.cy - b.cy) <= tol


def numeric_token_right_of(label_tok: Token, pool: list[Token], max_dx: float = 0.45) -> Token | None:
    """Find the nearest numeric token on the same row, to the right of label_tok."""
    from snapfolio.numbers import parse_decimal, parse_nav_with_date

    best: tuple[float, Token] | None = None
    for tok in pool:
        if tok is label_tok:
            continue
        if tok.x0 < label_tok.x1 - 0.01:
            continue
        if tok.x0 - label_tok.x1 > max_dx:
            continue
        if not same_row(label_tok, tok):
            continue
        if parse_decimal(tok.text) is None and parse_nav_with_date(tok.text) is None:
            continue
        dist = tok.x0 - label_tok.x1
        if best is None or dist < best[0]:
            best = (dist, tok)
    return best[1] if best else None


def tokens_right_of(tokens: list[Token], x: float, max_x: float | None = None) -> list[Token]:
    result = [t for t in tokens if t.x0 >= x]
    if max_x is not None:
        result = [t for t in result if t.x0 <= max_x]
    return sorted(result, key=lambda t: (t.cy, t.x0))


_TOP_CHROME_Y = 0.05
_FOOTER_CHROME_Y = 0.92

_CHROME_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
_CHROME_STATUS_RE = re.compile(r"^(G\.?l|4G|5G|N@?|38大促|腾讯腾安)$", re.I)
_CHROME_BATTERY_RE = re.compile(r"^\d{1,3}%?$")

_FOOTER_TAB_KEYWORDS = (
    "讨论区",
    "已加自选",
    "对比",
    "PK",
    "定投",
    "买入",
    "取出",
    "卖出",
    "赎回",
    "转换",
    "更多",
)


def _is_top_status_chrome(token: Token) -> bool:
    if token.y0 >= _TOP_CHROME_Y:
        return False
    text = token.text.strip()
    if _CHROME_TIME_RE.match(text):
        return True
    if _CHROME_STATUS_RE.match(text):
        return True
    if _CHROME_BATTERY_RE.match(text):
        return True
    return False


def _is_footer_tab_chrome(token: Token) -> bool:
    if token.y0 <= _FOOTER_CHROME_Y:
        return False
    text = token.text.strip()
    return any(k in text for k in _FOOTER_TAB_KEYWORDS)


def strip_chrome(doc: Document) -> Document:
    """Remove global status-bar and footer-tab tokens; keep business content intact."""
    kept = [
        t
        for t in doc.tokens
        if not _is_top_status_chrome(t) and not _is_footer_tab_chrome(t)
    ]
    return Document(kept, doc.image_width, doc.image_height, doc.source_path)


def parse_fixture(path: str | Path) -> Document:
    """
    Load a fixture file: header '# image: WxH' then 'x0,y0,x1,y1\\tconf\\ttext' lines.
    Absolute pixel coords are normalized to [0,1].
    """
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    width, height = 1080, 1920
    raw: list[tuple[list[list[float]], str, float]] = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            m = re.match(r"#\s*image:\s*(\d+)x(\d+)", line)
            if m:
                width, height = int(m.group(1)), int(m.group(2))
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue
        coords = [float(c) for c in parts[0].split(",")]
        conf = float(parts[1])
        text = parts[2]
        x0, y0, x1, y1 = coords
        bbox = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        raw.append((bbox, text, conf))

    return build_document(raw, width, height, str(path))
