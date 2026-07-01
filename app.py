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

_PLATFORM_LABELS = {
    "cmb_stock": "招商证券",
    "tencent_wesee": "腾讯微证券",
    "guosen_jty_stock": "国信金太阳",
    "alipay_fund": "支付宝基金",
    "tencent_licaitong": "微信理财通",
    "gemini": "Gemini 云端",
}

_DISPLAY_COLUMNS = [
    ("name", "名称"),
    ("code", "代码"),
    ("quantity", "数量/份额"),
    ("unit_price", "单价/净值"),
    ("amount", "市值/资产"),
    ("confidence", "置信度"),
    ("flags", "状态"),
    ("source", "来源"),
]

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


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


def _hero() -> None:
    st.markdown('<p class="sf-eyebrow">Portfolio ledger · local OCR</p>', unsafe_allow_html=True)
    st.markdown('<h1 class="sf-hero">SnapFolio</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sf-lede">上传券商与基金 App 持仓截图，本地识别后汇总为一张可导出的持仓表。'
        "默认全程离线；可选启用 Gemini 兜底识别未支持的平台。</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="sf-pipeline" aria-label="处理流程">
            <span>截图</span><span class="sf-arrow">→</span>
            <span>OCR</span><span class="sf-arrow">→</span>
            <span>平台识别</span><span class="sf-arrow">→</span>
            <span>字段抽取</span><span class="sf-arrow">→</span>
            <span>跨图合并</span><span class="sf-arrow">→</span>
            <span>导出</span>
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


def _sidebar() -> None:
    with st.sidebar:
        st.markdown("### 支持平台")
        for label in _PLATFORM_LABELS.values():
            if label != "Gemini 云端":
                st.markdown(f"- {label}")
        st.divider()
        st.checkbox(
            "启用 Gemini 兜底（本地无法识别时）",
            value=False,
            key="gemini_enabled",
        )
        st.text_input(
            "Gemini API Key",
            type="password",
            key="gemini_api_key",
            help="在 Google AI Studio 获取；仅在你点击兜底按钮时才会使用。",
        )
        st.caption(
            "隐私说明：仅在您主动点击「用 Gemini 识别」时，"
            "相应截图才会发送至 Google 服务器。API Key 仅存于当前会话，不会记录或显示。"
        )
        st.divider()
        st.markdown(
            """
            **理财通提示**  
            同一只基金请同时上传「持有中」与「资产详情」两张截图；代码仅在持有页出现。

            **截图建议**  
            尽量截全持仓卡片。标有 `needs_review` 的行请人工核对。
            """
        )


def _mime_for_filename(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return _MIME_BY_SUFFIX.get(suffix, "image/png")


def _process_uploads(
    paths: list[Path],
    upload_bytes: dict[str, bytes],
) -> tuple[list[PartialRecord], list[tuple[str, str]], list[tuple[str, bytes]]]:
    partials: list[PartialRecord] = []
    errors: list[tuple[str, str]] = []
    fallback_candidates: list[tuple[str, bytes]] = []

    progress = st.progress(0, text="准备识别…")
    for i, path in enumerate(paths):
        progress.progress((i) / len(paths), text=f"正在处理 {path.name} ({i + 1}/{len(paths)})")
        try:
            doc, source = ingest_image(path)
            partials.extend(process_document(doc, source))
        except UnknownPlatformError as exc:
            img_bytes = upload_bytes.get(path.name) or path.read_bytes()
            fallback_candidates.append((path.name, img_bytes))
            errors.append((path.name, f"未识别平台：{exc}"))
        except PipelineError as exc:
            errors.append((path.name, str(exc)))
        except Exception as exc:
            errors.append((path.name, f"处理失败：{exc}"))

    progress.progress(1.0, text="合并与校验…")
    progress.empty()

    return partials, errors, fallback_candidates


def _records_from_partials(partials: list[PartialRecord]) -> list[PositionRecord]:
    if not partials:
        return []
    merged = merge_partials(partials)
    return validate_records(merged)


def _display_dataframe(records: list[PositionRecord]) -> pd.DataFrame:
    df = records_to_dataframe(records)
    df["source"] = df["source"].map(lambda s: _PLATFORM_LABELS.get(s, s))
    df["flags"] = df["flags"].replace("", "—")
    rename = {col: label for col, label in _DISPLAY_COLUMNS}
    cols = [c for c, _ in _DISPLAY_COLUMNS if c in df.columns]
    out = df[cols].rename(columns=rename)
    if "置信度" in out.columns:
        out["置信度"] = out["置信度"].map(lambda x: f"{x:.0%}" if pd.notna(x) else "—")
    return out


def _style_review_rows(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def _row_style(row: pd.Series) -> list[str]:
        status = str(row.get("状态", ""))
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
    gemini_enabled: bool,
    api_key: str,
) -> None:
    n = len(fallback_candidates)
    if n == 0:
        return

    st.markdown(
        f"""
        <div class="sf-card">
            <h3>⚠️ 有 {n} 张截图本地无法识别</h3>
            <p>可能是暂不支持的平台。您可以选择用 <strong>Google Gemini</strong> 识别这些截图。</p>
            <p><strong>注意：点击识别按钮后，这些截图会被上传到 Google 服务器进行处理，不再是纯本地流程。</strong>
            请确认截图中不含您不愿外传的信息后再继续。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not gemini_enabled:
        st.info("请在左侧边栏勾选「启用 Gemini 兜底」并填写 API Key 后，再使用云端识别。")
        return

    if not api_key:
        st.info("请在左侧边栏填写 Gemini API Key（也可在 `.env` 或 Streamlit Secrets 中配置 `GEMINI_API_KEY`）。")
        return

    if st.button(f"用 Gemini 识别这 {n} 张图", type="secondary"):
        partials: list[PartialRecord] = list(st.session_state.get("local_partials", []))
        gemini_errors: list[str] = []

        with st.spinner(f"正在通过 Gemini 识别 {n} 张截图…"):
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
                (name, "Gemini 未能识别此截图") for name in gemini_errors
            )
        st.rerun()


def _render_results(
    records: list[PositionRecord],
    errors: list[tuple[str, str]],
    fallback_candidates: list[tuple[str, bytes]],
) -> None:
    if errors:
        with st.expander(f"有 {len(errors)} 张图片未能本地识别", expanded=not records):
            for name, msg in errors:
                st.warning(f"**{name}** — {msg}")

    if not records and not fallback_candidates:
        st.error("没有生成任何持仓记录。请检查截图是否为支持的平台，或换一张更完整的截图重试。")
        return

    if records:
        review_count = sum(1 for r in records if r.flags)
        st.success(f"识别完成，共 {len(records)} 条持仓。")

        c1, c2, c3 = st.columns(3)
        c1.metric("持仓条数", len(records))
        c2.metric("待核对", review_count)
        c3.metric("跳过图片", len(errors))

        display_df = _display_dataframe(records)
        st.dataframe(_style_review_rows(display_df), use_container_width=True, hide_index=True)

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "下载 Excel",
                data=_xlsx_bytes(records),
                file_name="portfolio.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with dl2:
            st.download_button(
                "下载 CSV",
                data=_csv_bytes(records),
                file_name="portfolio.csv",
                mime="text/csv",
                use_container_width=True,
            )

    gemini_enabled = st.session_state.get("gemini_enabled", False)
    api_key = _resolve_gemini_api_key()
    _render_fallback_consent(
        fallback_candidates,
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
    _inject_styles()
    _sidebar()
    _hero()

    uploads = st.file_uploader(
        "选择持仓截图",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
        help="可同时选择多张截图；理财通同一只基金请上传持有页与详情页各一张。",
    )

    if not uploads:
        st.markdown(
            """
            <div class="sf-card">
                <h3>上传截图开始</h3>
                <p>将招商、微证券、国信、支付宝基金或理财通的持仓截图拖入上方区域，点击「开始识别」。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.caption(f"已选择 {len(uploads)} 张图片")
    run = st.button("开始识别", type="primary", use_container_width=False)

    if run:
        upload_bytes = {u.name: u.getvalue() for u in uploads}
        with tempfile.TemporaryDirectory() as tmp:
            paths: list[Path] = []
            for upload in uploads:
                dest = Path(tmp) / upload.name
                dest.write_bytes(upload_bytes[upload.name])
                paths.append(dest)

            with st.spinner("本地 OCR 运行中，首次加载模型可能需数十秒…"):
                partials, errors, fallback_candidates = _process_uploads(paths, upload_bytes)

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
    _render_results(records, errors, fallback_candidates)


if __name__ == "__main__":
    main()
