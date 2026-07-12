"""Train and evaluate RandomForest token-field classifier."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from snapfolio.ml.dataset import LABELS
from snapfolio.ml.features import FEATURE_NAMES

NUMERIC_CLASSES = ("quantity", "unit_price", "amount")


def _make_classifier() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )


def _report_block(y_true, y_pred, labels: list[str]) -> str:
    return classification_report(
        y_true,
        y_pred,
        labels=labels,
        target_names=labels,
        zero_division=0,
    )


def _numeric_f1_summary(y_true, y_pred) -> dict[str, float]:
    out: dict[str, float] = {}
    for cls in NUMERIC_CLASSES:
        mask_true = [y == cls for y in y_true]
        mask_pred = [y == cls for y in y_pred]
        if not any(mask_true):
            out[cls] = 0.0
            continue
        tp = sum(t and p for t, p in zip(mask_true, mask_pred))
        fp = sum(not t and p for t, p in zip(mask_true, mask_pred))
        fn = sum(t and not p for t, p in zip(mask_true, mask_pred))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        out[cls] = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return out


def _avg_numeric_f1(y_true, y_pred) -> float:
    scores = _numeric_f1_summary(y_true, y_pred)
    return sum(scores.values()) / len(scores)


def train_and_evaluate(dataset_csv_or_df: str | Path | pd.DataFrame, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(dataset_csv_or_df, pd.DataFrame):
        df = dataset_csv_or_df.copy()
    else:
        df = pd.read_csv(dataset_csv_or_df)

    df = df[df["origin"] == "real"].reset_index(drop=True)
    label_list = sorted(df["label"].unique())
    X = df[FEATURE_NAMES].values
    y = df["label"].values

    lines: list[str] = [
        "# Token Field Classifier — Evaluation Report",
        "",
        f"- Training samples: **{len(df)}**",
        f"- Platforms: {', '.join(sorted(df['platform'].unique()))}",
        f"- Label distribution: {df['label'].value_counts().to_dict()}",
        "",
        "> Note: Some platforms have only 1–2 images; LOPO folds may lack certain classes.",
        "",
    ]

    # Leave-one-platform-out
    lines.append("## Leave-One-Platform-Out (LOPO)")
    platforms = sorted(df["platform"].unique())
    lopo_macro: list[float] = []
    lopo_numeric: list[float] = []

    for held_out in platforms:
        test_mask = df["platform"] == held_out
        train_mask = ~test_mask
        if train_mask.sum() == 0 or test_mask.sum() == 0:
            continue

        clf = _make_classifier()
        clf.fit(df.loc[train_mask, FEATURE_NAMES], df.loc[train_mask, "label"])
        y_pred = clf.predict(df.loc[test_mask, FEATURE_NAMES])
        y_test = df.loc[test_mask, "label"].tolist()

        macro_f1 = f1_score(y_test, y_pred, average="macro", labels=label_list, zero_division=0)
        num_f1 = _avg_numeric_f1(y_test, y_pred)
        lopo_macro.append(macro_f1)
        lopo_numeric.append(num_f1)

        lines.append(f"### Held out: `{held_out}` (n={test_mask.sum()})")
        lines.append(f"- Macro F1: **{macro_f1:.3f}**")
        num_scores = _numeric_f1_summary(y_test, y_pred)
        lines.append(
            "- Numeric avg F1: **{:.3f}** (quantity={:.3f}, unit_price={:.3f}, amount={:.3f})".format(
                num_f1,
                num_scores["quantity"],
                num_scores["unit_price"],
                num_scores["amount"],
            )
        )
        lines.append("")
        lines.append("```")
        lines.append(_report_block(y_test, y_pred, label_list))
        lines.append("```")
        lines.append("")

    if lopo_macro:
        lines.append("### LOPO Summary")
        lines.append(f"- Mean macro F1: **{sum(lopo_macro)/len(lopo_macro):.3f}**")
        lines.append(f"- Mean numeric avg F1: **{sum(lopo_numeric)/len(lopo_numeric):.3f}**")
        lines.append("")

    # Stratified 5-fold (reference)
    if len(df) >= 10 and len(set(y)) >= 2:
        lines.append("## Stratified 5-Fold CV (reference)")
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        clf = _make_classifier()
        y_pred_cv = cross_val_predict(clf, X, y, cv=skf)
        macro_f1 = f1_score(y, y_pred_cv, average="macro", labels=label_list, zero_division=0)
        num_f1 = _avg_numeric_f1(y.tolist(), y_pred_cv.tolist())
        lines.append(f"- Macro F1: **{macro_f1:.3f}**")
        num_scores = _numeric_f1_summary(y.tolist(), y_pred_cv.tolist())
        lines.append(
            "- Numeric avg F1: **{:.3f}** (quantity={:.3f}, unit_price={:.3f}, amount={:.3f})".format(
                num_f1,
                num_scores["quantity"],
                num_scores["unit_price"],
                num_scores["amount"],
            )
        )
        lines.append("")
        lines.append("```")
        lines.append(_report_block(y.tolist(), y_pred_cv.tolist(), label_list))
        lines.append("```")
        lines.append("")

    # Prominent numeric section
    lines.append("## Numeric Classes (quantity / unit_price / amount)")
    if lopo_numeric:
        lines.append(
            f"- **LOPO mean F1**: quantity/unit_price/amount average = **{sum(lopo_numeric)/len(lopo_numeric):.3f}**"
        )
    if len(df) >= 10:
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        clf = _make_classifier()
        y_pred_cv = cross_val_predict(clf, X, y, cv=skf)
        num_scores = _numeric_f1_summary(y.tolist(), y_pred_cv.tolist())
        lines.append(
            "- **5-fold reference F1**: "
            f"quantity={num_scores['quantity']:.3f}, "
            f"unit_price={num_scores['unit_price']:.3f}, "
            f"amount={num_scores['amount']:.3f}"
        )
    lines.append("")

    # Full retrain
    final_clf = _make_classifier()
    final_clf.fit(X, y)

    model_path = output_dir / "model.joblib"
    joblib.dump(final_clf, model_path)

    meta = {
        "feature_names": FEATURE_NAMES,
        "labels": label_list,
        "n_samples": len(df),
        "platforms": sorted(df["platform"].unique().tolist()),
        "label_counts": df["label"].value_counts().to_dict(),
    }
    meta_path = output_dir / "model_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    report_path = output_dir / "eval_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
