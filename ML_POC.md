# OCR Token Field Classifier — PoC Notes

Lightweight proof-of-concept **before** full synthetic-data work.
Code: `snapfolio/ml/` + `snapfolio/ocr_audit.py` + CLI `audit-ocr` / `train-classifier`.
**Not wired into** `pipeline.process_document` or Streamlit (rules + Gemini unchanged).

## How to reproduce

```powershell
python -m snapfolio.cli audit-ocr testset2 -o output/ocr_audit/testset2
python -m snapfolio.cli train-classifier --input-dir testset2 --extra-dir minimaltestset --output-dir output/ml
# or, if fixtures already dumped:
python -m snapfolio.cli train-classifier --fixtures-dir output/ml_fixtures --output-dir output/ml
```

Local artifacts (gitignored under `output/`): `ml_dataset.csv`, `model.joblib`, `eval_report.md`.

## Dataset (weak supervision)

- 16 real screenshots → OCR fixtures → existing platform extractors → value-align tokens
- **842** labeled tokens; platforms: `cmb_stock`, `guosen_jty_stock`, `tencent_licaitong`, `tencent_wesee`
- Labels: noise=689, amount=38, name=35, unit_price=35, code=29, quantity=16

## Results (representative run)

| Protocol | Meaning | Numeric avg F1 (qty / price / amount) |
|---|---|---|
| Stratified 5-fold | Same platforms mixed in train/test | **~0.71** (0.67 / 0.68 / 0.79) |
| Leave-one-platform-out | Hold out entire platform | **~0.06** (cross-layout fails) |

## Decision (team)

- Same-layout learning is plausible; **cross-platform generalization is not**.
- Known platforms stay on **hand rules**; unknown platforms stay on **Gemini fallback**.
- **Pause** full `synthesize` factory and pipeline wiring until there is a clear success bar for unseen layouts.
- Keep this PoC as methodology / limitation evidence.
