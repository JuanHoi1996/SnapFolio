"""
SnapFolio Web UI — upload broker screenshots, extract holdings, export ledger.
Run: streamlit run app.py
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from snapfolio.export import records_to_dataframe
from snapfolio.models import PositionRecord
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
        "全程离线，不上传云端。</p>",
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


def _sidebar() -> None:
    with st.sidebar:
        st.markdown("### 支持平台")
        for label in _PLATFORM_LABELS.values():
            st.markdown(f"- {label}")
        st.divider()
        st.markdown(
            """
            **理财通提示**  
            同一只基金请同时上传「持有中」与「资产详情」两张截图；代码仅在持有页出现。

            **截图建议**  
            尽量截全持仓卡片。标有 `needs_review` 的行请人工核对。
            """
        )


def _process_uploads(
    paths: list[Path],
) -> tuple[list[PositionRecord], list[tuple[str, str]]]:
    partials = []
    errors: list[tuple[str, str]] = []

    progress = st.progress(0, text="准备识别…")
    for i, path in enumerate(paths):
        progress.progress((i) / len(paths), text=f"正在处理 {path.name} ({i + 1}/{len(paths)})")
        try:
            doc, source = ingest_image(path)
            partials.extend(process_document(doc, source))
        except UnknownPlatformError as exc:
            errors.append((path.name, f"未识别平台：{exc}"))
        except PipelineError as exc:
            errors.append((path.name, str(exc)))
        except Exception as exc:
            errors.append((path.name, f"处理失败：{exc}"))

    progress.progress(1.0, text="合并与校验…")
    progress.empty()

    if not partials:
        return [], errors

    merged = merge_partials(partials)
    records = validate_records(merged)
    return records, errors


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

    if not run:
        return

    with tempfile.TemporaryDirectory() as tmp:
        paths: list[Path] = []
        for upload in uploads:
            suffix = Path(upload.name).suffix or ".png"
            dest = Path(tmp) / f"{upload.name}"
            dest.write_bytes(upload.getvalue())
            paths.append(dest)

        with st.spinner("本地 OCR 运行中，首次加载模型可能需数十秒…"):
            records, errors = _process_uploads(paths)

    if errors:
        with st.expander(f"有 {len(errors)} 张图片未能识别", expanded=not records):
            for name, msg in errors:
                st.warning(f"**{name}** — {msg}")

    if not records:
        st.error("没有生成任何持仓记录。请检查截图是否为支持的平台，或换一张更完整的截图重试。")
        return

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


if __name__ == "__main__":
    main()
