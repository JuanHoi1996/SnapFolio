# SnapFolio

从券商 / 基金 App **截图**中自动识别持仓，导出统一的 Excel 或 CSV 表格。全程本地 OCR，无需联网、无需 API Key。

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
