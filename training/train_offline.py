"""
Offline training và đánh giá chống leakage cho sliding-window dataset.

Nguyên tắc:
  - Không chia ngẫu nhiên các window chồng lấn.
  - Với từng source/session, train luôn nằm trước test theo thời gian.
  - Bỏ một khoảng purge bằng độ dài cửa sổ giữa train và test.
  - Dùng purged walk-forward để kiểm tra khả năng dự đoán phần tương lai
    của cùng phiên thu thập.
  - Chọn và báo cáo model chính bằng unseen-scenario OOF: giữ trọn một
    normal source và một attack source ngoài tập train ở mỗi fold.

Chạy: python training/train_offline.py
"""
import json
import itertools
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.base import clone  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
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

WINDOW_SECONDS = 5.0
HOP_SECONDS = 1.0
PURGE_WINDOWS = math.ceil(WINDOW_SECONDS / HOP_SECONDS)
TEST_FRACTION = 0.30
REQUIRED_METADATA = {"source", "window_end_ts"}


def evaluate(name, y_true, y_pred, y_proba=None):
    """Đánh giá một model trên tập test chronological độc lập."""
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    print(f"\n--- {name} ---")
    print(f"Accuracy : {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall   : {rec:.4f}")
    print(f"F1-score : {f1:.4f}")

    auc = None
    if y_proba is not None and len(np.unique(y_true)) == 2:
        auc = roc_auc_score(y_true, y_proba)
        print(f"ROC-AUC  : {auc:.4f}")

    print(f"Confusion matrix:\n{cm}")
    print(f"\nClassification Report:\n{classification_report(y_true, y_pred, zero_division=0)}")

    result = {
        "name": name,
        "accuracy": round(float(acc), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(auc), 4) if auc is not None else None,
        "confusion_matrix": cm.tolist(),
    }
    if y_proba is not None and auc is not None:
        fpr, tpr, thresholds = roc_curve(y_true, y_proba)
        result["roc_fpr"] = fpr.tolist()
        result["roc_tpr"] = tpr.tolist()
        result["roc_thresholds"] = [
            float(x) if np.isfinite(x) else None for x in thresholds
        ]
    return result


def _ordered_source_indices(df):
    """Trả index theo thời gian cho từng phiên thu thập."""
    for source, group in df.groupby("source", sort=True):
        ordered = group.sort_values("window_end_ts").index.to_numpy(dtype=int)
        yield source, ordered


def purged_chronological_holdout(df, test_fraction=TEST_FRACTION,
                                 purge_windows=PURGE_WINDOWS):
    """Chia chronological trong từng source, bỏ vùng giáp ranh bị overlap."""
    train_idx, test_idx, purged_idx = [], [], []
    summary = []

    for source, ordered in _ordered_source_indices(df):
        n = len(ordered)
        split = int(math.floor(n * (1.0 - test_fraction)))
        test_start = split + purge_windows
        if split < 2 or test_start >= n:
            raise ValueError(
                f"Source {source!r} chỉ có {n} window, không đủ để chia "
                f"chronological với purge={purge_windows}."
            )
        source_train = ordered[:split]
        source_purged = ordered[split:test_start]
        source_test = ordered[test_start:]
        train_idx.extend(source_train.tolist())
        purged_idx.extend(source_purged.tolist())
        test_idx.extend(source_test.tolist())
        summary.append({
            "source": source,
            "label": int(df.loc[ordered, "label"].mode().iloc[0]),
            "total": n,
            "train": len(source_train),
            "purged": len(source_purged),
            "test": len(source_test),
            "train_last_ts": float(df.loc[source_train[-1], "window_end_ts"]),
            "test_first_ts": float(df.loc[source_test[0], "window_end_ts"]),
        })

    train_idx = np.array(sorted(train_idx), dtype=int)
    test_idx = np.array(sorted(test_idx), dtype=int)
    purged_idx = np.array(sorted(purged_idx), dtype=int)
    for name, indices in (("train", train_idx), ("test", test_idx)):
        if df.loc[indices, "label"].nunique() < 2:
            raise ValueError(f"Tập {name} không chứa đủ normal và attack.")
    return train_idx, test_idx, purged_idx, summary


def purged_walk_forward_splits(df, n_splits=3, purge_windows=PURGE_WINDOWS):
    """Expanding-window CV; mọi validation window nằm sau training window."""
    train_fractions = np.linspace(0.40, 0.70, n_splits)
    validation_span = 0.25

    for fold, train_fraction in enumerate(train_fractions, 1):
        fold_train, fold_val = [], []
        for source, ordered in _ordered_source_indices(df):
            n = len(ordered)
            train_end = int(math.floor(n * train_fraction))
            val_start = train_end + purge_windows
            val_end = min(n, int(math.floor(n * (train_fraction + validation_span))))
            if train_end < 2 or val_start >= val_end:
                raise ValueError(
                    f"Source {source!r} không đủ window cho walk-forward fold {fold}."
                )
            fold_train.extend(ordered[:train_end].tolist())
            fold_val.extend(ordered[val_start:val_end].tolist())

        train_idx = np.array(sorted(fold_train), dtype=int)
        val_idx = np.array(sorted(fold_val), dtype=int)
        if (df.loc[train_idx, "label"].nunique() < 2
                or df.loc[val_idx, "label"].nunique() < 2):
            raise ValueError(f"Walk-forward fold {fold} không có đủ hai class.")
        yield train_idx, val_idx


def positive_probability(model, X):
    if not hasattr(model, "predict_proba"):
        return None
    matrix = model.predict_proba(X)
    classes = list(model.classes_)
    if 1 not in classes:
        return None
    return matrix[:, classes.index(1)]


def walk_forward_scores(model, X, y, df):
    f1_scores, auc_scores = [], []
    for fold, (train_idx, val_idx) in enumerate(purged_walk_forward_splits(df), 1):
        scaler = StandardScaler().fit(X[train_idx])
        fold_model = clone(model)
        fold_model.fit(scaler.transform(X[train_idx]), y[train_idx])
        X_val = scaler.transform(X[val_idx])
        pred = fold_model.predict(X_val)
        proba = positive_probability(fold_model, X_val)
        fold_f1 = f1_score(y[val_idx], pred, zero_division=0)
        fold_auc = roc_auc_score(y[val_idx], proba) if proba is not None else None
        f1_scores.append(float(fold_f1))
        if fold_auc is not None:
            auc_scores.append(float(fold_auc))
        print(f"    Fold {fold}: train={len(train_idx)}, validation={len(val_idx)}, "
              f"F1={fold_f1:.4f}, AUC={fold_auc:.4f}")
    return f1_scores, auc_scores


def unseen_scenario_evaluation(model, X, y, df):
    """Giữ trọn một normal source và một attack source ngoài tập train.

    Mỗi sample có thể được dự đoán ở nhiều cặp holdout. Xác suất OOF cuối cùng
    là trung bình các dự đoán từ những model chưa từng thấy source của sample.
    """
    normal_sources = sorted(df.loc[df["label"] == 0, "source"].unique())
    attack_sources = sorted(df.loc[df["label"] == 1, "source"].unique())
    if len(normal_sources) < 2 or len(attack_sources) < 2:
        raise ValueError("Cần ít nhất 2 normal source và 2 attack source để đánh giá unseen scenario.")

    probability_lists = [[] for _ in range(len(df))]
    folds = []
    for normal_source, attack_source in itertools.product(normal_sources, attack_sources):
        test_mask = df["source"].isin([normal_source, attack_source]).to_numpy()
        train_mask = ~test_mask
        scaler = StandardScaler().fit(X[train_mask])
        fold_model = clone(model)
        fold_model.fit(scaler.transform(X[train_mask]), y[train_mask])
        X_test = scaler.transform(X[test_mask])
        pred = fold_model.predict(X_test)
        proba = positive_probability(fold_model, X_test)
        test_indices = np.flatnonzero(test_mask)
        for index, probability in zip(test_indices, proba):
            probability_lists[index].append(float(probability))

        fold_auc = roc_auc_score(y[test_mask], proba)
        fold_f1 = f1_score(y[test_mask], pred, zero_division=0)
        fold_balanced = balanced_accuracy_score(y[test_mask], pred)
        folds.append({
            "normal_source": normal_source,
            "attack_source": attack_source,
            "test_size": int(test_mask.sum()),
            "auc": round(float(fold_auc), 4),
            "f1": round(float(fold_f1), 4),
            "balanced_accuracy": round(float(fold_balanced), 4),
        })

    if any(not values for values in probability_lists):
        raise ValueError("Có sample không nhận được dự đoán unseen-scenario OOF.")
    averaged_proba = np.array([np.mean(values) for values in probability_lists])
    oof_pred = (averaged_proba >= 0.5).astype(int)
    oof_auc = roc_auc_score(y, averaged_proba)
    oof_f1 = f1_score(y, oof_pred, zero_division=0)
    oof_balanced = balanced_accuracy_score(y, oof_pred)
    oof_accuracy = accuracy_score(y, oof_pred)
    oof_cm = confusion_matrix(y, oof_pred, labels=[0, 1])
    fpr, tpr, _ = roc_curve(y, averaged_proba)

    return {
        "strategy": "leave-one-normal-and-one-attack-source-out",
        "n_folds": len(folds),
        "folds": folds,
        "fold_auc_mean": round(float(np.mean([fold["auc"] for fold in folds])), 4),
        "fold_auc_std": round(float(np.std([fold["auc"] for fold in folds])), 4),
        "fold_f1_mean": round(float(np.mean([fold["f1"] for fold in folds])), 4),
        "fold_f1_std": round(float(np.std([fold["f1"] for fold in folds])), 4),
        "oof_accuracy": round(float(oof_accuracy), 4),
        "oof_balanced_accuracy": round(float(oof_balanced), 4),
        "oof_f1": round(float(oof_f1), 4),
        "oof_auc": round(float(oof_auc), 4),
        "oof_confusion_matrix": oof_cm.tolist(),
        "oof_roc_fpr": fpr.tolist(),
        "oof_roc_tpr": tpr.tolist(),
    }


def build_candidates():
    candidates = {
        "LogisticRegression": LogisticRegression(
            max_iter=2000, random_state=42
        ),
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
        print("\n(Bỏ qua XGBoost - cài xgboost nếu muốn thêm vào so sánh)")
    return candidates


def main():
    if not DATA_PATH.exists():
        print(f"Chưa có {DATA_PATH}. Hãy chạy generate_dataset.py trước.")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH).reset_index(drop=True)
    missing = REQUIRED_METADATA - set(df.columns)
    if missing:
        print(f"[ERROR] Dataset thiếu metadata: {sorted(missing)}")
        print("Hãy xóa data/training_data.csv và chạy lại Phase 2 để tạo schema mới.")
        sys.exit(1)
    df["window_end_ts"] = pd.to_numeric(df["window_end_ts"], errors="raise")

    n_attack = int(df["label"].sum())
    n_normal = int(len(df) - n_attack)
    print(f"Dataset: {len(df)} cửa sổ, {n_attack} attack, {n_normal} normal")
    print(f"Nguồn dữ liệu: {df['source'].nunique()} session/file")

    if df["label"].nunique() < 2:
        print("[ERROR] Cần cả dữ liệu normal và attack.")
        sys.exit(1)

    X = df[FEATURE_ORDER].to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=int)
    try:
        train_idx, test_idx, purged_idx, split_summary = purged_chronological_holdout(df)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    print(f"\nPurged chronological holdout: train={len(train_idx)}, "
          f"purged={len(purged_idx)}, test={len(test_idx)}")
    for item in split_summary:
        kind = "attack" if item["label"] else "normal"
        print(f"  {item['source']:<42} {kind:<6} "
              f"train={item['train']:>3} purge={item['purged']:>2} test={item['test']:>3}")

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    scaler = StandardScaler().fit(X_train)
    X_train_s = scaler.transform(X_train)
    X_test_s = scaler.transform(X_test)

    all_results = []
    baseline_pred = [fixed_threshold_predict(row) for row in X_test]
    all_results.append(evaluate(
        "Baseline - Fixed threshold (request_rate)", y_test, baseline_pred
    ))

    candidates = build_candidates()
    best_name, best_selection_score = None, -1.0
    feature_importances = {}

    for name, template in candidates.items():
        model = clone(template)
        model.fit(X_train_s, y_train)
        pred = model.predict(X_test_s)
        proba = positive_probability(model, X_test_s)
        result = evaluate(name, y_test, pred, proba)

        print(f"\n  3-fold purged walk-forward CV for {name}:")
        cv_f1, cv_auc = walk_forward_scores(template, X, y, df)
        result["cv_strategy"] = "3-fold purged walk-forward"
        result["cv_f1_mean"] = round(float(np.mean(cv_f1)), 4)
        result["cv_f1_std"] = round(float(np.std(cv_f1)), 4)
        result["cv_f1_scores"] = [round(x, 4) for x in cv_f1]
        result["cv_auc_mean"] = round(float(np.mean(cv_auc)), 4) if cv_auc else None
        result["cv_auc_std"] = round(float(np.std(cv_auc)), 4) if cv_auc else None
        result["cv_auc_scores"] = [round(x, 4) for x in cv_auc]
        print(f"  CV F1 : {result['cv_f1_mean']:.4f} ± {result['cv_f1_std']:.4f}")
        print(f"  CV AUC: {result['cv_auc_mean']:.4f} ± {result['cv_auc_std']:.4f}")

        scenario = unseen_scenario_evaluation(template, X, y, df)
        result["unseen_scenario"] = scenario
        print("  Unseen-scenario OOF: "
              f"AUC={scenario['oof_auc']:.4f}, "
              f"Balanced Accuracy={scenario['oof_balanced_accuracy']:.4f}, "
              f"F1={scenario['oof_f1']:.4f}")
        all_results.append(result)

        selection_score = scenario["oof_balanced_accuracy"]
        if selection_score > best_selection_score:
            best_name, best_selection_score = name, selection_score

        if hasattr(model, "feature_importances_"):
            feature_importances[name] = dict(
                zip(FEATURE_ORDER, model.feature_importances_.tolist())
            )

    best_result = next(r for r in all_results if r["name"] == best_name)
    print(f"\n{'=' * 70}")
    print(f"Mô hình tốt nhất theo unseen-scenario balanced accuracy: {best_name}")
    print(f"Scenario balanced accuracy={best_selection_score:.4f} | "
          f"Scenario AUC={best_result['unseen_scenario']['oof_auc']:.4f} | "
          f"Held-out AUC={best_result['roc_auc']}")
    print(f"{'=' * 70}")

    # Sau khi đánh giá xong, fit model triển khai trên toàn bộ dữ liệu.
    final_scaler = StandardScaler().fit(X)
    final_model = clone(candidates[best_name])
    final_model.fit(final_scaler.transform(X), y)
    joblib.dump(final_model, MODEL_DIR / "model.pkl")
    joblib.dump(final_scaler, MODEL_DIR / "scaler.pkl")

    evaluation = {
        "strategy": "purged chronological holdout per source",
        "test_fraction": TEST_FRACTION,
        "purge_windows": PURGE_WINDOWS,
        "purge_seconds": WINDOW_SECONDS,
        "selection": "best unseen-scenario OOF balanced accuracy",
        "limitation": "Các source hiện vẫn là một phiên cho mỗi kịch bản; cần phiên độc lập để đo khả năng tổng quát hóa hoàn toàn.",
        "sources": split_summary,
    }
    eval_output = {
        "dataset_size": len(df),
        "n_attack": n_attack,
        "n_normal": n_normal,
        "features": FEATURE_ORDER,
        "train_size": len(train_idx),
        "purged_size": len(purged_idx),
        "test_size": len(test_idx),
        "best_model": best_name,
        "primary_evaluation": "unseen-scenario out-of-fold",
        "best_auc": best_result["unseen_scenario"]["oof_auc"],
        "best_f1": best_result["unseen_scenario"]["oof_f1"],
        "best_balanced_accuracy": best_result["unseen_scenario"]["oof_balanced_accuracy"],
        "same_session_chronological_auc": best_result["roc_auc"],
        "same_session_walk_forward_auc": best_result["cv_auc_mean"],
        "best_selection_score": best_selection_score,
        "evaluation": evaluation,
        "results": all_results,
        "feature_importances": feature_importances,
    }
    eval_path = RESULTS_DIR / "offline_evaluation.json"
    with open(eval_path, "w", encoding="utf-8") as f:
        json.dump(eval_output, f, indent=2, ensure_ascii=False)

    md_lines = [
        "# Bảng 4.2 — So sánh mô hình học máy (Offline Evaluation)\n",
        f"Dataset: {len(df)} cửa sổ ({n_attack} attack, {n_normal} normal)\n",
        "**Chỉ số chính:** unseen-scenario out-of-fold; mỗi fold giữ trọn một "
        "normal source và một attack source ngoài tập train.\n",
        "**Kiểm tra phụ:** purged chronological holdout theo từng source; "
        f"purge {PURGE_WINDOWS} window ({WINDOW_SECONDS:.0f} giây).\n",
        f"Train: {len(train_idx)} | Purged: {len(purged_idx)} | Test: {len(test_idx)}\n",
        "",
        "| Mô hình | **Unseen-scenario AUC** | Balanced Acc. | F1 | Same-session F1 | Chronological AUC | Walk-forward AUC |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in all_results:
        cv_auc = (f"{result['cv_auc_mean']} ± {result['cv_auc_std']}"
                  if result.get("cv_auc_mean") is not None else "—")
        auc = result["roc_auc"] if result.get("roc_auc") is not None else "—"
        scenario = result.get("unseen_scenario")
        md_lines.append(
            f"| {result['name']} | {scenario['oof_auc'] if scenario else '—'} | "
            f"{scenario['oof_balanced_accuracy'] if scenario else '—'} | "
            f"{scenario['oof_f1'] if scenario else '—'} | "
            f"{result['f1']} | {auc} | {cv_auc} |"
        )

    best_fi = feature_importances.get(best_name, {})
    if best_fi:
        md_lines.extend(["", "## Feature Importance\n", "| Đặc trưng | Importance |", "|---|---:|"])
        for feature, importance in sorted(best_fi.items(), key=lambda x: -x[1]):
            md_lines.append(f"| {feature} | {importance:.4f} |")

    md_lines.extend([
        "",
        "## Giới hạn đánh giá\n",
        f"Model được chọn là **{best_name}**, AUC chính = "
        f"**{best_result['unseen_scenario']['oof_auc']:.4f}**. AUC same-session cao "
        "không được dùng làm kết luận chính vì các window trong một phiên vẫn có "
        "phân phối rất giống nhau.\n\n"
        "Các window chồng lấn đã được tách bằng purge gap. Tuy nhiên mỗi kịch bản "
        "hiện chỉ có một phiên thu thập; cần chạy thêm phiên độc lập và dùng toàn "
        "bộ phiên mới làm external test trước khi kết luận khả năng tổng quát hóa.",
    ])
    table_path = RESULTS_DIR / "table_4_2.md"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"Đã lưu model triển khai vào {MODEL_DIR}")
    print(f"Đã lưu đánh giá vào {eval_path}")
    print(f"Đã lưu bảng vào {table_path}")


if __name__ == "__main__":
    main()
