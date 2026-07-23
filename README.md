# SnapFolio

Extract structured investment holdings from **screenshots** of Chinese brokerage and fund apps, then export a unified Excel or CSV table.

- **Local-first OCR** (RapidOCR) — no API key required for supported platforms
- **Optional Gemini fallback** for unrecognized layouts (explicit user consent)
- **UI languages:** Simplified Chinese · Traditional Chinese · English

**Live demo:** [https://snapfolio.streamlit.app/](https://snapfolio.streamlit.app/)  
**Design notes:** see [DESIGN.md](DESIGN.md)

> 中文说明见 [README_zh.md](README_zh.md)

---

## Features

| Feature | Description |
|--------|-------------|
| Closed-world platform detection | Matches known app signatures; rejects unknown layouts instead of guessing |
| Five supported apps | CMB Securities, Tencent WeSee, Guosen Jintaiyang, Alipay Fund, WeChat Licaitong |
| List + detail extractors | Row/column layouts and key–value detail cards |
| Cross-image reconciliation | Merges Licaitong “holding” + “detail” pages into one row |
| Arithmetic validation | Flags rows where `amount ≉ quantity × unit_price` |
| Review flags | `needs_review`, `incomplete_fields`, `amount_mismatch`, `llm_extracted`, … |
| Streamlit web UI | Upload → recognize → preview → download Excel/CSV |
| CLI | Batch-process a folder of screenshots |
| Privacy controls | Local by default; Gemini only after an explicit click |
| i18n | Switch UI language in the sidebar |

---

## Supported platforms

| Platform | Typical screen |
|----------|----------------|
| CMB Securities (招商证券) | My stocks |
| Tencent WeSee (腾讯微证券) | Holdings list |
| Guosen Jintaiyang (国信金太阳) | Holdings list |
| Alipay Fund (支付宝基金) | Asset detail |
| WeChat Licaitong (微信理财通) | Holding + asset detail (two screenshots) |

Unsupported screenshots are rejected with a clear error (or offered Gemini fallback if enabled).

---

## Requirements

- **Python 3.10–3.12** (RapidOCR does not support 3.13+ yet)
- Dependencies: see [`requirements.txt`](requirements.txt) and [`pyproject.toml`](pyproject.toml)
- Streamlit Cloud also uses [`packages.txt`](packages.txt) for system libraries (`libgl1`, `libglib2.0-0t64`)

---

## Installation

```bash
cd SnapFolio
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

---

## Usage

### Web UI (recommended)

```bash
streamlit run app.py
```

Open `http://localhost:8501`, upload screenshots, click **Start recognition**, preview the table, then download Excel/CSV.

**Worked example (Licaitong):**

1. Upload both screenshots for the same fund: **持有中 (holding)** and **资产详情 (detail)**.
2. Run recognition.
3. Confirm one merged row: name + **6-digit code** (from holding) + quantity / NAV / amount (from detail).
4. Rows needing a human check are highlighted and carry flags such as `needs_review`.

**Live example:** use the [Streamlit Cloud app](https://snapfolio.streamlit.app/) with your own screenshots (do not commit personal portfolio images to Git).

After deploying to [Streamlit Cloud](https://streamlit.io/cloud), push to `main`, then **Reboot app** (not only Rerun) so `packages.txt` / dependency changes rebuild.

### Command line

```bash
# Excel
python -m snapfolio.cli process --input-dir ./screenshots --output portfolio.xlsx

# CSV
python -m snapfolio.cli process --input-dir ./screenshots --output portfolio.csv
```

Put all related screenshots in the same folder. For Licaitong, include both page types so codes and amounts can merge.

**Screenshot tip:** capture the full holding card. Heavily cropped images may leave fields empty or flagged for review.

---

## API keys (optional Gemini fallback)

Supported platforms run **fully offline**. Gemini is only for screenshots that fail local classification.

1. Copy [`.env.example`](.env.example) to `.env` (never commit `.env`):

   ```bash
   cp .env.example .env
   ```

2. Set:

   ```env
   GEMINI_API_KEY=your_key_here
   ```

3. Or enter the key in the web UI sidebar / Streamlit Cloud **Secrets** as `GEMINI_API_KEY`.

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey).

**Privacy:** images are uploaded to Google **only** after you click the Gemini recognize button. Keys stay in the session / secrets store and are not hardcoded in the repository.

---

## Project layout

```
app.py                 # Streamlit UI
snapfolio/             # OCR → classify → extract → reconcile → validate → export
  i18n.py              # UI strings (zh-CN / zh-TW / en)
  ml/                  # Random Forest token-classifier PoC (not in production path)
tests/                 # Unit / regression tests
requirements.txt
packages.txt           # Streamlit Cloud apt packages
DESIGN.md              # Architecture notes
```

---

## Known issues

- **Licaitong codes require two screenshots.** The detail page alone has no fund code; upload the holding page as well, or the code column stays empty.
- **Wrapped security names (WeSee).** Long names split across OCR lines are joined in the current extractor; residual OCR truncations (missing last character) can still occur.
- **OCR / layout drift.** App UI updates or unusual fonts can break signatures or field anchors for a platform until configs are updated.
- **Confidence is not calibrated probability.** It reflects resolution strategy + OCR score; use flags and arithmetic checks for review.
- **Gemini can hallucinate plausible rows.** Cloud results are marked `llm_extracted` and still go through reconcile/validate; always spot-check.

## Planned enhancements

- Broader, independently annotated evaluation sets across all five platforms
- Clearer in-app guidance when a Licaitong pair is incomplete
- More declarative column/layout config to lower the cost of adding a new app
- Optional schema-driven vision path while keeping local-first controls

---

## License / course context

Built for **UNSW FINS5557 Applied AI in Finance** (Track A — Tech Team). See the written report for evaluation metrics, ethics, AI-tool disclosure, and contribution statements.
