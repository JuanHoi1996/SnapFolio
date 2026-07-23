"""UI strings for SnapFolio Streamlit app (zh-CN / zh-TW / en)."""

from __future__ import annotations

from typing import Any

LANG_OPTIONS: dict[str, str] = {
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en": "English",
}

DEFAULT_LANG = "zh-CN"

_PLATFORM: dict[str, dict[str, str]] = {
    "zh-CN": {
        "cmb_stock": "招商证券",
        "tencent_wesee": "腾讯微证券",
        "guosen_jty_stock": "国信金太阳",
        "alipay_fund": "支付宝基金",
        "tencent_licaitong": "微信理财通",
        "gemini": "Gemini 云端",
    },
    "zh-TW": {
        "cmb_stock": "招商證券",
        "tencent_wesee": "騰訊微證券",
        "guosen_jty_stock": "國信金太陽",
        "alipay_fund": "支付寶基金",
        "tencent_licaitong": "微信理財通",
        "gemini": "Gemini 雲端",
    },
    "en": {
        "cmb_stock": "CMB Securities",
        "tencent_wesee": "Tencent WeSee",
        "guosen_jty_stock": "Guosen Jintaiyang",
        "alipay_fund": "Alipay Fund",
        "tencent_licaitong": "WeChat Licaitong",
        "gemini": "Gemini cloud",
    },
}

_COLUMNS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "name": "名称",
        "code": "代码",
        "quantity": "数量/份额",
        "unit_price": "单价/净值",
        "amount": "市值/资产",
        "confidence": "置信度",
        "flags": "状态",
        "source": "来源",
    },
    "zh-TW": {
        "name": "名稱",
        "code": "代碼",
        "quantity": "數量/份額",
        "unit_price": "單價/淨值",
        "amount": "市值/資產",
        "confidence": "置信度",
        "flags": "狀態",
        "source": "來源",
    },
    "en": {
        "name": "Name",
        "code": "Code",
        "quantity": "Qty / units",
        "unit_price": "Unit price / NAV",
        "amount": "Market value",
        "confidence": "Confidence",
        "flags": "Flags",
        "source": "Source",
    },
}

_STRINGS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "lang_label": "界面语言",
        "eyebrow": "Portfolio ledger · local OCR",
        "lede": "上传券商与基金 App 持仓截图，本地识别后汇总为一张可导出的持仓表。默认全程离线；可选启用 Gemini 兜底识别未支持的平台。",
        "pipeline_aria": "处理流程",
        "pipe_shot": "截图",
        "pipe_ocr": "OCR",
        "pipe_classify": "平台识别",
        "pipe_extract": "字段抽取",
        "pipe_merge": "跨图合并",
        "pipe_export": "导出",
        "sidebar_platforms": "支持平台",
        "gemini_checkbox": "启用 Gemini 兜底（本地无法识别时）",
        "gemini_key_label": "Gemini API Key",
        "gemini_key_help": "在 Google AI Studio 获取；仅在你点击兜底按钮时才会使用。",
        "privacy_caption": "隐私说明：仅在您主动点击「用 Gemini 识别」时，相应截图才会发送至 Google 服务器。API Key 仅存于当前会话，不会记录或显示。",
        "tips_md": (
            "**理财通提示**  \n"
            "同一只基金请同时上传「持有中」与「资产详情」两张截图；代码仅在持有页出现。\n\n"
            "**截图建议**  \n"
            "尽量截全持仓卡片。标有 `needs_review` 的行请人工核对。"
        ),
        "uploader_label": "选择持仓截图",
        "uploader_help": "可同时选择多张截图；理财通同一只基金请上传持有页与详情页各一张。",
        "empty_card_title": "上传截图开始",
        "empty_card_body": "将招商、微证券、国信、支付宝基金或理财通的持仓截图拖入上方区域，点击「开始识别」。",
        "selected_n": "已选择 {n} 张图片",
        "run_button": "开始识别",
        "prep_progress": "准备识别…",
        "processing_file": "正在处理 {name} ({i}/{total})",
        "merge_progress": "合并与校验…",
        "unknown_platform": "未识别平台：{exc}",
        "process_failed": "处理失败：{exc}",
        "spinner_ocr": "本地 OCR 运行中，首次加载模型可能需数十秒…",
        "errors_expander": "有 {n} 张图片未能本地识别",
        "no_records": "没有生成任何持仓记录。请检查截图是否为支持的平台，或换一张更完整的截图重试。",
        "success": "识别完成，共 {n} 条持仓。",
        "metric_holdings": "持仓条数",
        "metric_review": "待核对",
        "metric_skipped": "跳过图片",
        "dl_excel": "下载 Excel",
        "dl_csv": "下载 CSV",
        "fallback_title": "⚠️ 有 {n} 张截图本地无法识别",
        "fallback_body": "可能是暂不支持的平台。您可以选择用 <strong>Google Gemini</strong> 识别这些截图。",
        "fallback_warn": (
            "<strong>注意：点击识别按钮后，这些截图会被上传到 Google 服务器进行处理，不再是纯本地流程。</strong>"
            "请确认截图中不含您不愿外传的信息后再继续。"
        ),
        "fallback_enable_hint": "请在左侧边栏勾选「启用 Gemini 兜底」并填写 API Key 后，再使用云端识别。",
        "fallback_key_hint": "请在左侧边栏填写 Gemini API Key（也可在 `.env` 或 Streamlit Secrets 中配置 `GEMINI_API_KEY`）。",
        "fallback_button": "用 Gemini 识别这 {n} 张图",
        "fallback_spinner": "正在通过 Gemini 识别 {n} 张截图…",
        "gemini_failed": "Gemini 未能识别此截图",
    },
    "zh-TW": {
        "lang_label": "介面語言",
        "eyebrow": "Portfolio ledger · local OCR",
        "lede": "上傳券商與基金 App 持倉截圖，本地識別後彙總為一張可匯出的持倉表。預設全程離線；可選啟用 Gemini 兜底識別未支援的平台。",
        "pipeline_aria": "處理流程",
        "pipe_shot": "截圖",
        "pipe_ocr": "OCR",
        "pipe_classify": "平台識別",
        "pipe_extract": "欄位抽取",
        "pipe_merge": "跨圖合併",
        "pipe_export": "匯出",
        "sidebar_platforms": "支援平台",
        "gemini_checkbox": "啟用 Gemini 兜底（本地無法識別時）",
        "gemini_key_label": "Gemini API Key",
        "gemini_key_help": "可於 Google AI Studio 取得；僅在你點擊兜底按鈕時才會使用。",
        "privacy_caption": "隱私說明：僅在您主動點擊「用 Gemini 識別」時，相應截圖才會傳送至 Google 伺服器。API Key 僅存於目前工作階段，不會記錄或顯示。",
        "tips_md": (
            "**理財通提示**  \n"
            "同一檔基金請同時上傳「持有中」與「資產詳情」兩張截圖；代碼僅在持有頁出現。\n\n"
            "**截圖建議**  \n"
            "盡量截全持倉卡片。標有 `needs_review` 的列請人工核對。"
        ),
        "uploader_label": "選擇持倉截圖",
        "uploader_help": "可同時選擇多張截圖；理財通同一檔基金請上傳持有頁與詳情頁各一張。",
        "empty_card_title": "上傳截圖開始",
        "empty_card_body": "將招商、微證券、國信、支付寶基金或理財通的持倉截圖拖入上方區域，點擊「開始識別」。",
        "selected_n": "已選擇 {n} 張圖片",
        "run_button": "開始識別",
        "prep_progress": "準備識別…",
        "processing_file": "正在處理 {name} ({i}/{total})",
        "merge_progress": "合併與校驗…",
        "unknown_platform": "未識別平台：{exc}",
        "process_failed": "處理失敗：{exc}",
        "spinner_ocr": "本地 OCR 執行中，首次載入模型可能需數十秒…",
        "errors_expander": "有 {n} 張圖片未能本地識別",
        "no_records": "沒有產生任何持倉記錄。請檢查截圖是否為支援的平台，或換一張更完整的截圖重試。",
        "success": "識別完成，共 {n} 筆持倉。",
        "metric_holdings": "持倉筆數",
        "metric_review": "待核對",
        "metric_skipped": "略過圖片",
        "dl_excel": "下載 Excel",
        "dl_csv": "下載 CSV",
        "fallback_title": "⚠️ 有 {n} 張截圖本地無法識別",
        "fallback_body": "可能是暫不支援的平台。您可以選擇用 <strong>Google Gemini</strong> 識別這些截圖。",
        "fallback_warn": (
            "<strong>注意：點擊識別按鈕後，這些截圖會被上傳到 Google 伺服器進行處理，不再是純本地流程。</strong>"
            "請確認截圖中不含您不願外傳的資訊後再繼續。"
        ),
        "fallback_enable_hint": "請在左側邊欄勾選「啟用 Gemini 兜底」並填寫 API Key 後，再使用雲端識別。",
        "fallback_key_hint": "請在左側邊欄填寫 Gemini API Key（也可在 `.env` 或 Streamlit Secrets 中設定 `GEMINI_API_KEY`）。",
        "fallback_button": "用 Gemini 識別這 {n} 張圖",
        "fallback_spinner": "正在透過 Gemini 識別 {n} 張截圖…",
        "gemini_failed": "Gemini 未能識別此截圖",
    },
    "en": {
        "lang_label": "Language",
        "eyebrow": "Portfolio ledger · local OCR",
        "lede": "Upload brokerage and fund-app holding screenshots. SnapFolio extracts them locally into one exportable table. Offline by default; optional Gemini fallback for unsupported layouts.",
        "pipeline_aria": "Processing pipeline",
        "pipe_shot": "Screenshot",
        "pipe_ocr": "OCR",
        "pipe_classify": "Classify",
        "pipe_extract": "Extract",
        "pipe_merge": "Reconcile",
        "pipe_export": "Export",
        "sidebar_platforms": "Supported platforms",
        "gemini_checkbox": "Enable Gemini fallback (when local recognition fails)",
        "gemini_key_label": "Gemini API Key",
        "gemini_key_help": "Get a key from Google AI Studio; used only when you click the fallback button.",
        "privacy_caption": "Privacy: screenshots are sent to Google only after you click “Recognize with Gemini”. The API key stays in this session and is never logged or displayed.",
        "tips_md": (
            "**Licaitong tip**  \n"
            "For each fund, upload both the holding (“持有中”) and asset-detail screenshots; the code appears only on the holding page.\n\n"
            "**Screenshot tip**  \n"
            "Capture the full holding card. Rows flagged `needs_review` need a manual check."
        ),
        "uploader_label": "Choose holding screenshots",
        "uploader_help": "You can select multiple images; for Licaitong, upload one holding page and one detail page per fund.",
        "empty_card_title": "Start by uploading screenshots",
        "empty_card_body": "Drop CMB, WeSee, Guosen, Alipay Fund, or Licaitong holding screenshots above, then click “Start recognition”.",
        "selected_n": "{n} image(s) selected",
        "run_button": "Start recognition",
        "prep_progress": "Preparing…",
        "processing_file": "Processing {name} ({i}/{total})",
        "merge_progress": "Merging and validating…",
        "unknown_platform": "Unknown platform: {exc}",
        "process_failed": "Processing failed: {exc}",
        "spinner_ocr": "Running local OCR — first model load may take tens of seconds…",
        "errors_expander": "{n} image(s) could not be recognized locally",
        "no_records": "No holdings were produced. Check that the screenshots are from a supported platform, or try a fuller capture.",
        "success": "Done — {n} holding(s) extracted.",
        "metric_holdings": "Holdings",
        "metric_review": "Needs review",
        "metric_skipped": "Skipped images",
        "dl_excel": "Download Excel",
        "dl_csv": "Download CSV",
        "fallback_title": "⚠️ {n} screenshot(s) could not be recognized locally",
        "fallback_body": "They may be from an unsupported platform. You can try <strong>Google Gemini</strong> on these images.",
        "fallback_warn": (
            "<strong>Note: clicking recognize will upload these screenshots to Google — this is no longer a fully local run.</strong> "
            "Confirm the images do not contain information you prefer not to share."
        ),
        "fallback_enable_hint": "Enable “Gemini fallback” in the sidebar and provide an API key before using cloud recognition.",
        "fallback_key_hint": "Enter a Gemini API Key in the sidebar (or set `GEMINI_API_KEY` in `.env` / Streamlit Secrets).",
        "fallback_button": "Recognize these {n} image(s) with Gemini",
        "fallback_spinner": "Recognizing {n} screenshot(s) with Gemini…",
        "gemini_failed": "Gemini could not recognize this screenshot",
    },
}


def normalize_lang(code: str | None) -> str:
    if code in _STRINGS:
        return code  # type: ignore[return-value]
    return DEFAULT_LANG


def t(lang: str, key: str, **kwargs: Any) -> str:
    lang = normalize_lang(lang)
    template = _STRINGS[lang].get(key) or _STRINGS[DEFAULT_LANG].get(key) or key
    return template.format(**kwargs) if kwargs else template


def platform_labels(lang: str) -> dict[str, str]:
    return _PLATFORM[normalize_lang(lang)]


def display_columns(lang: str) -> list[tuple[str, str]]:
    cols = _COLUMNS[normalize_lang(lang)]
    order = ("name", "code", "quantity", "unit_price", "amount", "confidence", "flags", "source")
    return [(k, cols[k]) for k in order]
