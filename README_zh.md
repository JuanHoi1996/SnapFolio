# SnapFolio

从券商 / 基金 App **截图**中自动识别持仓，导出统一的 Excel 或 CSV 表格。

- **本地优先 OCR**（RapidOCR）— 支持的平台无需 API Key
- **可选 Gemini 兜底** — 仅用于本地无法识别的版面（需用户明确同意）
- **界面语言：** 简体中文 · 繁體中文 · English

**在线演示：** [https://snapfolio.streamlit.app/](https://snapfolio.streamlit.app/)  
**设计说明：** 见 [DESIGN.md](DESIGN.md)

> English README: [README.md](README.md)

---

## 功能一览

| 功能 | 说明 |
|------|------|
| 闭世界平台识别 | 只匹配已知 App 签名；未知版面拒绝，不乱猜 |
| 五个支持平台 | 招商证券、腾讯微证券、国信金太阳、支付宝基金、微信理财通 |
| 列表 / 详情抽取 | 行列持仓与键值详情卡 |
| 跨图合并 | 理财通「持有中」+「资产详情」合并为一行 |
| 算术校验 | `市值 ≉ 数量 × 单价` 时打标 |
| 复核标记 | `needs_review`、`incomplete_fields`、`amount_mismatch`、`llm_extracted` 等 |
| Streamlit Web | 上传 → 识别 → 预览 → 下载 Excel/CSV |
| 命令行 | 批量处理截图文件夹 |
| 隐私控制 | 默认本地；仅在点击后才走 Gemini |
| 国际化 | 侧边栏切换界面语言 |

---

## 支持的平台

| 平台 | 典型页面 |
|------|----------|
| 招商证券 | 我的股票 |
| 腾讯微证券 | 持仓列表 |
| 国信金太阳 | 持仓列表 |
| 支付宝基金 | 资产详情页 |
| 微信理财通 | 持有中 + 资产详情（两张截图） |

不支持的截图会被明确拒绝（若开启 Gemini，可再选择云端识别）。

---

## 环境要求

- **Python 3.10–3.12**（RapidOCR 暂不支持 3.13+）
- 依赖见 [`requirements.txt`](requirements.txt)、[`pyproject.toml`](pyproject.toml)
- Streamlit Cloud 另用 [`packages.txt`](packages.txt) 安装系统库（`libgl1`、`libglib2.0-0t64`）

---

## 安装

```bash
cd SnapFolio
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
pip install -e .
```

---

## 使用

### Web 界面（推荐）

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`，上传截图 →「开始识别」→ 预览表格 → 下载 Excel/CSV。

**理财通示例：**

1. 同一只基金同时上传 **「持有中」** 与 **「资产详情」**。
2. 点击识别。
3. 应得到一行：名称 + **六位代码**（来自持有页）+ 份额/净值/金额（来自详情页）。
4. 需人工核对的行会高亮，并带 `needs_review` 等标记。

**在线试用：** [Streamlit Cloud](https://snapfolio.streamlit.app/)（请勿把含真实隐私的持仓图提交进 Git）。

部署到 Cloud 后若改了依赖，请在控制台 **Reboot app**（不是仅 Rerun），等待重建完成。

### 命令行

```bash
python -m snapfolio.cli process --input-dir ./screenshots --output portfolio.xlsx
python -m snapfolio.cli process --input-dir ./screenshots --output portfolio.csv
```

**截图建议：** 尽量截全持仓卡片；裁切过狠可能导致字段缺失或进入待核对。

---

## API Key（可选 Gemini）

支持的平台可**全程离线**。仅当本地分类失败时才可能用到 Gemini。

1. 复制 [`.env.example`](.env.example) 为 `.env`（**不要**把 `.env` 提交进仓库）：

   ```bash
   cp .env.example .env
   ```

2. 填写：

   ```env
   GEMINI_API_KEY=your_key_here
   ```

3. 或在 Web 侧边栏 / Streamlit Secrets 中配置同名变量。

免费 Key：[Google AI Studio](https://aistudio.google.com/apikey)。

**隐私：** 只有主动点击「用 Gemini 识别」后，对应截图才会上传到 Google。Key 不写死在代码里。

---

## 已知问题

- **理财通代码依赖双图。** 仅上传详情页时代码列为空（版面上本身无代码）。
- **微证券长名称折行。** 当前会拼接多行名字；OCR 漏字仍可能发生。
- **版面/字体变更** 可能导致某平台签名或锚点失效，需更新配置。
- **置信度不是校准概率**；请结合 flags 与算术校验人工复核。
- **Gemini 可能产出看似合理的错误行**；结果标 `llm_extracted`，务必抽查。

## 后续计划

- 覆盖五平台的独立标注评估集
- 理财通缺页时更明确的界面提示
- 更声明式的列/版面配置，降低加新 App 成本
- 在保持本地优先的前提下探索 schema 驱动视觉路径

---

## 课程说明

本项目用于 **UNSW FINS5557 Applied AI in Finance**（Track A）。评估指标、伦理、AI 工具披露与贡献声明见书面报告。
