# SnapFolio

从券商 / 基金 App **截图**中自动识别持仓，导出统一的 Excel 或 CSV 表格。默认可全程本地 OCR，无需 API Key；可选 Gemini 云端兜底（见下文）。

## 支持的平台

| 平台 | App |
|------|-----|
| 招商证券 | 我的股票 |
| 腾讯微证券 | 持仓列表 |
| 国信金太阳 | 持仓列表 |
| 支付宝基金 | 资产详情页 |
| 微信理财通 | 持有中 + 资产详情（可多张截图） |

不支持的 App 截图会被明确拒绝，不会乱猜。

## 安装

需要 Python 3.10–3.12（RapidOCR 暂不支持 3.13+）。

```bash
cd SnapFolio
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
pip install -e .
```

## 使用

### Web 界面（推荐）

```bash
pip install streamlit
streamlit run app.py
```

浏览器打开 `http://localhost:8501`，上传截图后点击「开始识别」，可预览表格并下载 Excel/CSV。本地调通后再部署到 [Streamlit Cloud](https://streamlit.io/cloud)。

仓库根目录的 `packages.txt` 会在云端安装 `libgl1`、`libglib2.0-0`（RapidOCR / OpenCV 在 Linux 上需要）；`requirements.txt` 使用 `opencv-python-headless` 避免 GUI 依赖。推送后请在 Streamlit Cloud 控制台 **Reboot app**（不是 Rerun），等依赖重新构建完成再试识别。

### 命令行

把截图放进一个文件夹，例如 `screenshots/`，然后：

```bash
python -m snapfolio.cli process --input-dir ./screenshots --output portfolio.xlsx
```

导出 CSV：

```bash
python -m snapfolio.cli process --input-dir ./screenshots --output portfolio.csv
```

**理财通**：同一只基金需要「持有中」和「资产详情」各一张截图，放在同一文件夹里一起处理，会自动合并成一行。基金代码只在「持有中」页出现；若只放资产详情页，代码列会为空，需手动补上。

**截图建议**：尽量截全整张持仓卡片；裁切严重的图可能识别不全，导出结果里会标 `needs_review`，需人工核对。

## 可选：Gemini 云端兜底

默认情况下，所有识别均在本地完成，截图不会离开本机。若某张截图无法匹配已知平台（`UnknownPlatformError`），可在 Web 界面侧边栏：

1. 勾选 **「启用 Gemini 兜底（本地无法识别时）」**
2. 填写 **Gemini API Key**（可在 [Google AI Studio](https://aistudio.google.com/apikey) 免费获取）

也可在项目根目录创建 `.env` 并设置 `GEMINI_API_KEY=`（参见 `.env.example`），或在 Streamlit Cloud 的 Secrets 中配置同名变量。

**隐私说明**：只有在你主动点击「用 Gemini 识别这 N 张图」时，对应截图才会上传到 Google 服务器。API Key 仅存于当前浏览器会话，不会被记录或显示。Gemini 识别结果会标记 `llm_extracted`，并经过与本地相同的合并与校验流程。
