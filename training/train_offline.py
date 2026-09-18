"""
training/train_offline.py
3.4.1 Offline Training Pipeline + 4.2 Đánh giá và lựa chọn mô hình học máy.

Cải tiến:
  - 5-fold Stratified Cross-Validation (thay vì chỉ 1 lần train/test split)
  - In mean ± std F1 từ 5 fold
  - Classification report chi tiết (precision/recall per class)
  - ROC-AUC score
  - Feature importance (RandomForest)
  - Lưu kết quả vào results/offline_evaluation.json
  - Tự động sinh bảng markdown results/table_4_2.md

Chạy: python training/train_offline.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (  # noqa: E402
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.neural_network import MLPClassifier  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from common.features import FEATURE_ORDER  # noqa: E402
from training.baseline_fixed_threshold import fixed_threshold_predict  # noqa: E402

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "training_data.csv"
MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def evaluate(name, y_true, y_pred, y_proba=None):
    """Đánh giá 1 model, in kết quả, trả về dict metrics."""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred)

    print(f"\n--- {name} ---")
    print(f"Accuracy : {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall   : {rec:.4f}")
    print(f"F1-score : {f1:.4f}")

    auc = None
    if y_proba is not None:
        try:
            auc = roc_auc_score(y_true, y_proba)
            print(f"ROC-AUC  : {auc:.4f}")
        except ValueError:
            pass

    print(f"Confusion matrix:\n{cm}")
    print(f"\nClassification Report:\n{classification_report(y_true, y_pred, zero_division=0)}")

    return {
        "name": name,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "roc_auc": round(auc, 4) if auc is not None else None,
        "confusion_matrix": cm.tolist(),
    }


def main():
    if not DATA_PATH.exists():
        print(f"Chưa có {DATA_PATH}. Hãy chạy training/generate_dataset.py trước "
              f"(cần cả dữ liệu normal, burst và attack).")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    print(f"Dataset: {len(df)} cửa sổ, {df['label'].sum()} attack, "
          f"{len(df) - df['label'].sum()} normal")
    print(f"Đặc trưng: {FEATURE_ORDER}")

    X = df[FEATURE_ORDER].values
    y = df["label"].values

    # ---- Train/Test Split ----
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    print(f"\nTrain: {len(X_train)} | Test: {len(X_test)}")
    print(f"Train attack: {y_train.sum()} | Test attack: {y_test.sum()}")

    scaler = StandardScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    all_results = []

    # ---- Baseline (4.4): rule ngưỡng cố định, dữ liệu thô chưa scale ----
    baseline_pred = [fixed_threshold_predict(row) for row in X_test]
    baseline_result = evaluate("Baseline - Fixed threshold (request_rate)", y_test, baseline_pred)
    all_results.append(baseline_result)

    # ---- ML Models ----
    candidates = {
        "RandomForest": RandomForestClassifier(
            n_estimators=200, max_depth=10, random_state=42
        ),
        "MLP": MLPClassifier(
            hidden_layer_sizes=(64, 32), max_iter=1000, random_state=42
        ),
    }
    try:
        from xgboost import XGBClassifier
        candidates["XGBoost"] = XGBClassifier(
            n_estimators=200, max_depth=5, eval_metric="logloss", random_state=42
        )
    except ImportError:
        print("\n(Bỏ qua XGBoost - chạy 'pip install xgboost' nếu muốn thêm vào so sánh)")

    best_name, best_model, best_f1 = None, None, -1.0
    feature_importances = {}

    for name, model in candidates.items():
        model.fit(X_train_s, y_train)
        pred = model.predict(X_test_s)

        # Lấy xác suất cho ROC-AUC
        proba = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_test_s)[:, 1]

        result = evaluate(name, y_test, pred, proba)

        # ---- 5-fold Stratified Cross-Validation ----
        print(f"\n  5-fold Stratified CV for {name}:")
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        # Cần scaler riêng cho mỗi fold, dùng pipeline đơn giản
        cv_scores = []
        for fold_i, (train_idx, val_idx) in enumerate(cv.split(X, y)):
            fold_scaler = StandardScaler().fit(X[train_idx])
            fold_X_train = fold_scaler.transform(X[train_idx])
            fold_X_val = fold_scaler.transform(X[val_idx])
            fold_model = type(model)(**model.get_params())
            fold_model.fit(fold_X_train, y[train_idx])
            fold_pred = fold_model.predict(fold_X_val)
            fold_f1 = f1_score(y[val_idx], fold_pred, zero_division=0)
            cv_scores.append(fold_f1)

        cv_mean = np.mean(cv_scores)
        cv_std = np.std(cv_scores)
        print(f"  CV F1 scores: {[round(s, 4) for s in cv_scores]}")
        print(f"  CV F1: {cv_mean:.4f} ± {cv_std:.4f}")
        result["cv_f1_mean"] = round(cv_mean, 4)
        result["cv_f1_std"] = round(cv_std, 4)
        result["cv_f1_scores"] = [round(s, 4) for s in cv_scores]

        all_results.append(result)

        if result["f1"] > best_f1:
            best_name, best_model, best_f1 = name, model, result["f1"]

        # Feature importance (RandomForest)
        if hasattr(model, "feature_importances_"):
            importances = dict(zip(FEATURE_ORDER, model.feature_importances_.tolist()))
            feature_importances[name] = importances
            print(f"\n  Feature importance ({name}):")
            for feat, imp in sorted(importances.items(), key=lambda x: -x[1]):
                print(f"    {feat:<25} {imp:.4f}")

    # ---- Summary ----
    print(f"\n{'='*60}")
    print(f"Mô hình tốt nhất: {best_name} (F1={best_f1:.4f})")
    print(f"{'='*60}")

    # ---- Save model + scaler ----
    joblib.dump(best_model, MODEL_DIR / "model.pkl")
    joblib.dump(scaler, MODEL_DIR / "scaler.pkl")
    print(f"Đã lưu model + scaler vào {MODEL_DIR}/ (app/main.py sẽ tự nạp lại khi khởi động)")

    # ---- Save evaluation results ----
    eval_output = {
        "dataset_size": len(df),
        "n_attack": int(df["label"].sum()),
        "n_normal": int(len(df) - df["label"].sum()),
        "features": FEATURE_ORDER,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "best_model": best_name,
        "best_f1": best_f1,
        "results": all_results,
        "feature_importances": feature_importances,
    }
    eval_path = RESULTS_DIR / "offline_evaluation.json"
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_output, f, indent=2, ensure_ascii=False)
    print(f"Đã lưu kết quả đánh giá vào {eval_path}")

    # ---- Generate markdown table for 4.2 ----
    md_lines = [
        "# Bảng 4.2 — So sánh mô hình học máy (Offline Evaluation)\n",
        f"Dataset: {len(df)} cửa sổ ({int(df['label'].sum())} attack, "
        f"{int(len(df) - df['label'].sum())} normal)\n",
        f"Đặc trưng: {len(FEATURE_ORDER)} ({', '.join(FEATURE_ORDER)})\n",
        "",
        "| Mô hình | Accuracy | Precision | Recall | F1-score | ROC-AUC | CV F1 (5-fold) |",
        "|---------|----------|-----------|--------|----------|---------|----------------|",
    ]
    for r in all_results:
        cv_str = f"{r.get('cv_f1_mean', '-')} ± {r.get('cv_f1_std', '-')}" if r.get('cv_f1_mean') else "—"
        auc_str = f"{r['roc_auc']}" if r.get('roc_auc') else "—"
        md_lines.append(
            f"| {r['name']} | {r['accuracy']} | {r['precision']} | "
            f"{r['recall']} | {r['f1']} | {auc_str} | {cv_str} |"
        )
    md_lines.append("")

    if feature_importances:
        md_lines.append("## Feature Importance\n")
        md_lines.append("| Đặc trưng | Importance |")
        md_lines.append("|-----------|------------|")
        # Lấy feature importance của model tốt nhất
        best_fi = feature_importances.get(best_name, {})
        for feat, imp in sorted(best_fi.items(), key=lambda x: -x[1]):
            md_lines.append(f"| {feat} | {imp:.4f} |")

    table_path = RESULTS_DIR / "table_4_2.md"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Đã lưu bảng markdown vào {table_path}")


if __name__ == "__main__":
    main()
