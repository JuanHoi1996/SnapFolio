"""
SnapFolio Web UI — upload broker screenshots, extract holdings, export ledger.
Run: streamlit run app.py
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from snapfolio.export import records_to_dataframe
from snapfolio.i18n import (
    DEFAULT_LANG,
    LANG_OPTIONS,
    display_columns,
    normalize_lang,
    platform_labels,
    t,
)
from snapfolio.llm_fallback import extract_with_gemini
from snapfolio.models import PartialRecord, PositionRecord
from snapfolio.pipeline import (
    PipelineError,
    UnknownPlatformError,
    ingest_image,
    process_document,
)
from snapfolio.reconcile import merge_partials
from snapfolio.validate import validate_records

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _lang() -> str:
    return normalize_lang(st.session_state.get("ui_lang", DEFAULT_LANG))


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;700&family=JetBrains+Mono:wght@400;500&family=Source+Sans+3:wght@400;500;600&display=swap');

        .stApp {
            background: linear-gradient(165deg, #F7F4ED 0%, #EDE8DC 45%, #F7F4ED 100%);
        }

        .sf-hero {
            font-family: 'Fraunces', Georgia, serif;
            font-size: 2.35rem;
            font-weight: 700;
            color: #0B1426;
            letter-spacing: -0.02em;
            line-height: 1.15;
            margin: 0 0 0.35rem 0;
        }

        .sf-eyebrow {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: #C9A227;
            margin-bottom: 0.5rem;
        }

        .sf-lede {
            font-family: 'Source Sans 3', sans-serif;
            font-size: 1.05rem;
            color: #3D4F5F;
            max-width: 42rem;
            line-height: 1.55;
            margin-bottom: 1.5rem;
        }

        .sf-pipeline {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem 0.5rem;
            margin: 1.25rem 0 2rem 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
        }

        .sf-pipeline span {
            background: #0B1426;
            color: #F7F4ED;
            padding: 0.35rem 0.65rem;
            border-radius: 2px;
        }

        .sf-pipeline .sf-arrow {
            background: transparent;
            color: #C9A227;
            padding: 0.35rem 0.15rem;
        }

        .sf-card {
            background: #FFFCF7;
            border: 1px solid #D8D0C0;
            border-left: 3px solid #C9A227;
            padding: 1rem 1.15rem;
            margin-bottom: 1rem;
            border-radius: 2px;
        }

        .sf-card h3 {
            font-family: 'Source Sans 3', sans-serif;
            font-size: 0.95rem;
            font-weight: 600;
            color: #0B1426;
            margin: 0 0 0.35rem 0;
        }

        .sf-card p {
            font-family: 'Source Sans 3', sans-serif;
            font-size: 0.88rem;
            color: #5A6B7A;
            margin: 0;
            line-height: 1.45;
        }

        div[data-testid="stMetric"] {
            background: #FFFCF7;
            border: 1px solid #D8D0C0;
            padding: 0.75rem 1rem;
            border-radius: 2px;
        }

        div[data-testid="stMetric"] label {
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 0.7rem !important;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .stDownloadButton button {
            font-family: 'Source Sans 3', sans-serif;
            font-weight: 600;
            border-radius: 2px;
        }

        [data-testid="stFileUploader"] {
            background: #FFFCF7;
            border: 1px dashed #C9A227;
            border-radius: 2px;
            padding: 0.5rem;
        }

        @media (prefers-reduced-motion: reduce) {
            * { animation: none !important; transition: none !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hero(lang: str) -> None:
    st.markdown(f'<p class="sf-eyebrow">{t(lang, "eyebrow")}</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="sf-hero">SnapFolio</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="sf-lede">{t(lang, "lede")}</p>', unsafe_allow_html=True)
    aria = t(lang, "pipeline_aria")
    st.markdown(
        f"""
        <div class="sf-pipeline" aria-label="{aria}">
            <span>{t(lang, "pipe_shot")}</span><span class="sf-arrow">→</span>
            <span>{t(lang, "pipe_ocr")}</span><span class="sf-arrow">→</span>
            <span>{t(lang, "pipe_classify")}</span><span class="sf-arrow">→</span>
            <span>{t(lang, "pipe_extract")}</span><span class="sf-arrow">→</span>
            <span>{t(lang, "pipe_merge")}</span><span class="sf-arrow">→</span>
            <span>{t(lang, "pipe_export")}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _resolve_gemini_api_key() -> str:
    ui_key = st.session_state.get("gemini_api_key", "").strip()
    if ui_key:
        return ui_key
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        return st.secrets.get("GEMINI_API_KEY", "").strip()
    except Exception:
        return ""


def _sidebar(lang: str) -> str:
    with st.sidebar:
        selected = st.selectbox(
            t(lang, "lang_label"),
            options=list(LANG_OPTIONS.keys()),
            format_func=lambda c: LANG_OPTIONS[c],
            key="ui_lang",
        )
        lang = normalize_lang(selected)
        st.divider()
        st.markdown(f"### {t(lang, 'sidebar_platforms')}")
        labels = platform_labels(lang)
        for pid, label in labels.items():
            if pid != "gemini":
                st.markdown(f"- {label}")
        st.divider()
        st.checkbox(
            t(lang, "gemini_checkbox"),
            value=False,
            key="gemini_enabled",
        )
        st.text_input(
            t(lang, "gemini_key_label"),
            type="password",
            key="gemini_api_key",
            help=t(lang, "gemini_key_help"),
        )
        st.caption(t(lang, "privacy_caption"))
        st.divider()
        st.markdown(t(lang, "tips_md"))
    return lang


def _mime_for_filename(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return _MIME_BY_SUFFIX.get(suffix, "image/png")


def _process_uploads(
    paths: list[Path],
    upload_bytes: dict[str, bytes],
    lang: str,
) -> tuple[list[PartialRecord], list[tuple[str, str]], list[tuple[str, bytes]]]:
    partials: list[PartialRecord] = []
    errors: list[tuple[str, str]] = []
    fallback_candidates: list[tuple[str, bytes]] = []

    progress = st.progress(0, text=t(lang, "prep_progress"))
    for i, path in enumerate(paths):
        progress.progress(
            i / len(paths),
            text=t(lang, "processing_file", name=path.name, i=i + 1, total=len(paths)),
        )
        try:
            doc, source = ingest_image(path)
            partials.extend(process_document(doc, source))
        except UnknownPlatformError as exc:
            img_bytes = upload_bytes.get(path.name) or path.read_bytes()
            fallback_candidates.append((path.name, img_bytes))
            errors.append((path.name, t(lang, "unknown_platform", exc=exc)))
        except PipelineError as exc:
            errors.append((path.name, str(exc)))
        except Exception as exc:
            errors.append((path.name, t(lang, "process_failed", exc=exc)))

    progress.progress(1.0, text=t(lang, "merge_progress"))
    progress.empty()

    return partials, errors, fallback_candidates


def _records_from_partials(partials: list[PartialRecord]) -> list[PositionRecord]:
    if not partials:
        return []
    merged = merge_partials(partials)
    return validate_records(merged)


def _display_dataframe(records: list[PositionRecord], lang: str) -> pd.DataFrame:
    df = records_to_dataframe(records)
    labels = platform_labels(lang)
    df["source"] = df["source"].map(lambda s: labels.get(s, s))
    df["flags"] = df["flags"].replace("", "—")
    columns = display_columns(lang)
    rename = {col: label for col, label in columns}
    cols = [c for c, _ in columns if c in df.columns]
    out = df[cols].rename(columns=rename)
    conf_label = rename.get("confidence", "置信度")
    if conf_label in out.columns:
        out[conf_label] = out[conf_label].map(lambda x: f"{x:.0%}" if pd.notna(x) else "—")
    return out


def _style_review_rows(df: pd.DataFrame, lang: str) -> pd.io.formats.style.Styler:
    flags_label = dict(display_columns(lang)).get("flags", "状态")

    def _row_style(row: pd.Series) -> list[str]:
        status = str(row.get(flags_label, ""))
        if "llm_extracted" in status:
            return ["background-color: #E8F4FC; color: #0B1426"] * len(row)
        if "needs_review" in status or "amount_mismatch" in status:
            return ["background-color: #FFF0E6; color: #0B1426"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


def _xlsx_bytes(records: list[PositionRecord]) -> bytes:
    buf = io.BytesIO()
    df = records_to_dataframe(records)
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="holdings")
        ws = writer.sheets["holdings"]
        if "code" in df.columns:
            code_col = df.columns.get_loc("code") + 1
            for row in range(2, len(df) + 2):
                ws.cell(row=row, column=code_col).number_format = "@"
    buf.seek(0)
    return buf.getvalue()


def _csv_bytes(records: list[PositionRecord]) -> bytes:
    return records_to_dataframe(records).to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def _render_fallback_consent(
    fallback_candidates: list[tuple[str, bytes]],
    *,
    lang: str,
    gemini_enabled: bool,
    api_key: str,
) -> None:
    n = len(fallback_candidates)
    if n == 0:
        return

    st.markdown(
        f"""
        <div class="sf-card">
            <h3>{t(lang, "fallback_title", n=n)}</h3>
            <p>{t(lang, "fallback_body")}</p>
            <p>{t(lang, "fallback_warn")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not gemini_enabled:
        st.info(t(lang, "fallback_enable_hint"))
        return

    if not api_key:
        st.info(t(lang, "fallback_key_hint"))
        return

    if st.button(t(lang, "fallback_button", n=n), type="secondary"):
        partials: list[PartialRecord] = list(st.session_state.get("local_partials", []))
        gemini_errors: list[str] = []

        with st.spinner(t(lang, "fallback_spinner", n=n)):
            for name, img_bytes in fallback_candidates:
                new_partials = extract_with_gemini(
                    img_bytes,
                    api_key=api_key,
                    source_image=name,
                    mime_type=_mime_for_filename(name),
                )
                if new_partials:
                    partials.extend(new_partials)
                else:
                    gemini_errors.append(name)

        st.session_state["local_partials"] = partials
        st.session_state["fallback_candidates"] = []
        if gemini_errors:
            st.session_state.setdefault("errors", []).extend(
                (name, t(lang, "gemini_failed")) for name in gemini_errors
            )
        st.rerun()


def _render_results(
    records: list[PositionRecord],
    errors: list[tuple[str, str]],
    fallback_candidates: list[tuple[str, bytes]],
    lang: str,
) -> None:
    if errors:
        with st.expander(t(lang, "errors_expander", n=len(errors)), expanded=not records):
            for name, msg in errors:
                st.warning(f"**{name}** — {msg}")

    if not records and not fallback_candidates:
        st.error(t(lang, "no_records"))
        return

    if records:
        review_count = sum(1 for r in records if r.flags)
        st.success(t(lang, "success", n=len(records)))

        c1, c2, c3 = st.columns(3)
        c1.metric(t(lang, "metric_holdings"), len(records))
        c2.metric(t(lang, "metric_review"), review_count)
        c3.metric(t(lang, "metric_skipped"), len(errors))

        display_df = _display_dataframe(records, lang)
        st.dataframe(_style_review_rows(display_df, lang), use_container_width=True, hide_index=True)

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                t(lang, "dl_excel"),
                data=_xlsx_bytes(records),
                file_name="portfolio.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                t(lang, "dl_csv"),
                data=_csv_bytes(records),
                file_name="portfolio.csv",
                mime="text/csv",
                use_container_width=True,
            )

    gemini_enabled = st.session_state.get("gemini_enabled", False)
    api_key = _resolve_gemini_api_key()
    _render_fallback_consent(
        fallback_candidates,
        lang=lang,
        gemini_enabled=gemini_enabled,
        api_key=api_key,
    )


def main() -> None:
    st.set_page_config(
        page_title="SnapFolio",
        page_icon="📒",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    if "ui_lang" not in st.session_state:
        st.session_state["ui_lang"] = DEFAULT_LANG

    _inject_styles()
    lang = _sidebar(_lang())
    _hero(lang)

    uploads = st.file_uploader(
        t(lang, "uploader_label"),
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
        help=t(lang, "uploader_help"),
    )

    if not uploads:
        st.markdown(
            f"""
            <div class="sf-card">
                <h3>{t(lang, "empty_card_title")}</h3>
                <p>{t(lang, "empty_card_body")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.caption(t(lang, "selected_n", n=len(uploads)))
    run = st.button(t(lang, "run_button"), type="primary", use_container_width=False)

    if run:
        upload_bytes = {u.name: u.getvalue() for u in uploads}
        with tempfile.TemporaryDirectory() as tmp:
            paths: list[Path] = []
            for upload in uploads:
                dest = Path(tmp) / upload.name
                dest.write_bytes(upload_bytes[upload.name])
                paths.append(dest)

            with st.spinner(t(lang, "spinner_ocr")):
                partials, errors, fallback_candidates = _process_uploads(paths, upload_bytes, lang)

        st.session_state["local_partials"] = partials
        st.session_state["fallback_candidates"] = fallback_candidates
        st.session_state["upload_bytes"] = upload_bytes
        st.session_state["errors"] = errors
        st.session_state["processed"] = True

    if not st.session_state.get("processed"):
        return

    partials = st.session_state.get("local_partials", [])
    errors = st.session_state.get("errors", [])
    fallback_candidates = st.session_state.get("fallback_candidates", [])

    records = _records_from_partials(partials)
    _render_results(records, errors, fallback_candidates, lang)


if __name__ == "__main__":
    main()
