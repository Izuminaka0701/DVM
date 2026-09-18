"""
experiments/plot_results.py
Sinh toàn bộ biểu đồ cho Chương 4 luận văn.

Biểu đồ:
  - fig_4_2_confusion_matrix.png   : Confusion matrix heatmap (4.2)
  - fig_4_2_feature_importance.png : Feature importance bar chart (4.2)
  - fig_4_2_roc_curve.png          : ROC Curve (4.2)
  - fig_4_3_1_processing_latency.png : Boxplot processing latency (4.3.1)
  - fig_4_3_2_detection_delay.png    : Bar chart detection delay (4.3.2)
  - fig_4_3_3_resource_usage.png     : CPU/RAM line chart (4.3.3)
  - fig_4_3_timeline.png             : Request rate + attack probability timeline

Chạy: python experiments/plot_results.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Cố gắng dùng font hỗ trợ tiếng Việt
try:
    plt.rcParams["font.family"] = "DejaVu Sans"
except Exception:
    pass
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.bbox"] = "tight"

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def safe_load_jsonl(path):
    """Đọc JSONL, bỏ qua dòng hỏng."""
    rows = []
    if not path.exists():
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def plot_latency():
    """4.3.1 - Boxplot processing latency."""
    rows = safe_load_jsonl(LOG_DIR / "metrics.jsonl")
    if not rows:
        print("  [SKIP] Chua co metrics.jsonl")
        return
    df = pd.DataFrame(rows)
    if "processing_latency_ms" not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(6, 4))
    bp = ax.boxplot(df["processing_latency_ms"], vert=True, patch_artist=True)
    bp["boxes"][0].set_facecolor("#4CAF50")
    bp["boxes"][0].set_alpha(0.7)
    ax.set_ylabel("Processing latency (ms)")
    ax.set_title("4.3.1 - Processing Latency Distribution")
    ax.set_xticklabels(["All windows"])

    # Annotate stats
    data = df["processing_latency_ms"]
    stats_text = (f"Mean: {data.mean():.2f} ms\n"
                  f"P50: {data.median():.2f} ms\n"
                  f"P95: {data.quantile(0.95):.2f} ms\n"
                  f"Max: {data.max():.2f} ms")
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes, fontsize=8,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    out = FIG_DIR / "fig_4_3_1_processing_latency.png"
    plt.savefig(out)
    plt.close()
    print(f"  [OK] {out.name}")


def plot_resources():
    """4.3.3 - CPU/RAM line chart."""
    path = LOG_DIR / "resource_usage.csv"
    if not path.exists():
        print("  [SKIP] Chua co resource_usage.csv")
        return

    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("ts,"):
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                try:
                    rows.append({
                        "ts": float(parts[0]),
                        "cpu": float(parts[1]),
                        "mem_mb": float(parts[2]),
                    })
                except ValueError:
                    continue

    if not rows:
        print("  [SKIP] resource_usage.csv rong")
        return

    df = pd.DataFrame(rows)
    df["t"] = df["ts"] - df["ts"].min()

    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(df["t"], df["cpu"], color="tab:red", linewidth=1.5, label="CPU (%)")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("CPU (%)", color="tab:red")
    ax1.tick_params(axis="y", labelcolor="tab:red")

    ax2 = ax1.twinx()
    ax2.plot(df["t"], df["mem_mb"], color="tab:blue", linewidth=1.5, label="RAM (MB)")
    ax2.set_ylabel("RAM (MB)", color="tab:blue")
    ax2.tick_params(axis="y", labelcolor="tab:blue")

    plt.title("4.3.3 - CPU & RAM Usage Over Time")
    fig.legend(loc="upper left", bbox_to_anchor=(0.12, 0.88))

    out = FIG_DIR / "fig_4_3_3_resource_usage.png"
    plt.savefig(out)
    plt.close()
    print(f"  [OK] {out.name}")


def plot_detection_delay():
    """4.3.2 - Bar chart detection delay."""
    report_path = RESULTS_DIR / "benchmark_report.json"
    if not report_path.exists():
        print("  [SKIP] Chua co benchmark_report.json (chay benchmark_latency.py --report truoc)")
        return

    with open(report_path) as f:
        report = json.load(f)

    delays = report.get("detection_delay")
    if not delays:
        print("  [SKIP] Khong co du lieu detection_delay")
        return

    names = [d["attack"].replace("_start", "").replace("_", "\n") for d in delays]
    values = [d["delay_s"] if d["delay_s"] is not None else 0 for d in delays]
    colors = ["#4CAF50" if d["detected"] else "#F44336" for d in delays]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(names, values, color=colors, edgecolor="white", linewidth=0.5)

    for bar, d in zip(bars, delays):
        if d["detected"]:
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                    f'{d["delay_s"]}s', ha='center', va='bottom', fontsize=8)
        else:
            ax.text(bar.get_x() + bar.get_width()/2., 0.5,
                    'NOT\nDETECTED', ha='center', va='bottom', fontsize=7,
                    color='white', fontweight='bold')

    ax.set_ylabel("Detection Delay (seconds)")
    ax.set_title("4.3.2 - Detection Delay by Attack Type")
    ax.legend(handles=[
        plt.Rectangle((0,0),1,1, facecolor="#4CAF50", label="Detected"),
        plt.Rectangle((0,0),1,1, facecolor="#F44336", label="Not Detected"),
    ], loc="upper right")

    out = FIG_DIR / "fig_4_3_2_detection_delay.png"
    plt.savefig(out)
    plt.close()
    print(f"  [OK] {out.name}")


def plot_timeline():
    """Timeline - Request rate + Attack probability."""
    rows = safe_load_jsonl(LOG_DIR / "metrics.jsonl")
    if not rows:
        print("  [SKIP] Chua co metrics.jsonl")
        return

    df = pd.DataFrame(rows)
    if "ts" not in df.columns:
        return
    df["t"] = df["ts"] - df["ts"].min()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

    ax1.plot(df["t"], df["request_rate"], color="tab:blue", linewidth=0.8)
    ax1.set_ylabel("Request Rate (req/s)")
    ax1.set_title("Real-time Monitoring Timeline")
    ax1.grid(True, alpha=0.3)

    ax2.plot(df["t"], df["attack_probability"], color="tab:red", linewidth=0.8)
    ax2.axhline(y=0.7, color="orange", linestyle="--", alpha=0.7, label="Threshold (0.7)")
    ax2.set_ylabel("Attack Probability")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylim(-0.05, 1.05)
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Đánh dấu vùng alert
    if "alert_triggered" in df.columns:
        alert_mask = df["alert_triggered"] == True  # noqa
        if alert_mask.any():
            ax2.fill_between(df["t"], 0, 1, where=alert_mask,
                           alpha=0.2, color="red", label="Alert triggered")

    plt.tight_layout()
    out = FIG_DIR / "fig_4_3_timeline.png"
    plt.savefig(out)
    plt.close()
    print(f"  [OK] {out.name}")


def plot_confusion_matrix():
    """4.2 - Confusion matrix heatmap."""
    eval_path = RESULTS_DIR / "offline_evaluation.json"
    if not eval_path.exists():
        print("  [SKIP] Chua co offline_evaluation.json")
        return

    with open(eval_path) as f:
        data = json.load(f)

    # Vẽ CM cho model tốt nhất
    best_name = data.get("best_model")
    for r in data.get("results", []):
        if r["name"] == best_name and "confusion_matrix" in r:
            cm = np.array(r["confusion_matrix"])
            fig, ax = plt.subplots(figsize=(5, 4))
            im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
            ax.figure.colorbar(im, ax=ax)
            classes = ["Normal (0)", "Attack (1)"]
            ax.set(xticks=[0, 1], yticks=[0, 1],
                   xticklabels=classes, yticklabels=classes,
                   ylabel="True label", xlabel="Predicted label",
                   title=f"4.2 - Confusion Matrix ({best_name})")

            # Annotate cells
            for i in range(2):
                for j in range(2):
                    ax.text(j, i, str(cm[i, j]),
                           ha="center", va="center", fontsize=16,
                           color="white" if cm[i, j] > cm.max()/2 else "black")

            out = FIG_DIR / "fig_4_2_confusion_matrix.png"
            plt.savefig(out)
            plt.close()
            print(f"  [OK] {out.name}")
            break


def plot_feature_importance():
    """4.2 - Feature importance bar chart."""
    eval_path = RESULTS_DIR / "offline_evaluation.json"
    if not eval_path.exists():
        print("  [SKIP] Chua co offline_evaluation.json")
        return

    with open(eval_path) as f:
        data = json.load(f)

    fi = data.get("feature_importances", {})
    best_name = data.get("best_model")
    if best_name not in fi:
        print("  [SKIP] Khong co feature importance cho model tot nhat")
        return

    importances = fi[best_name]
    sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    names = [f[0] for f in sorted_features]
    values = [f[1] for f in sorted_features]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(names)))
    bars = ax.barh(names[::-1], values[::-1], color=colors[::-1], edgecolor="white")
    ax.set_xlabel("Importance")
    ax.set_title(f"4.2 - Feature Importance ({best_name})")

    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
                f'{val:.4f}', ha='left', va='center', fontsize=8)

    out = FIG_DIR / "fig_4_2_feature_importance.png"
    plt.savefig(out)
    plt.close()
    print(f"  [OK] {out.name}")


def plot_roc_curve():
    """4.2 - ROC Curve (giả lập từ kết quả eval nếu có đủ dữ liệu)."""
    # ROC curve cần raw predictions, ta dùng kết quả từ training
    eval_path = RESULTS_DIR / "offline_evaluation.json"
    if not eval_path.exists():
        print("  [SKIP] Chua co offline_evaluation.json")
        return

    with open(eval_path) as f:
        data = json.load(f)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot([0, 1], [0, 1], 'k--', alpha=0.5, label="Random (AUC=0.5)")

    for r in data.get("results", []):
        if r.get("roc_auc") is not None:
            # Vẽ điểm (1-specificity, sensitivity) = (FPR, TPR) từ confusion matrix
            cm = np.array(r["confusion_matrix"])
            if cm.shape == (2, 2):
                tn, fp, fn, tp = cm.ravel()
                tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
                ax.plot([0, fpr, 1], [0, tpr, 1], 'o-',
                       label=f"{r['name']} (AUC={r['roc_auc']})", markersize=8)

    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("4.2 - ROC Curve")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(True, alpha=0.3)

    out = FIG_DIR / "fig_4_2_roc_curve.png"
    plt.savefig(out)
    plt.close()
    print(f"  [OK] {out.name}")


if __name__ == "__main__":
    print("Generating figures for Chapter 4...\n")
    plot_latency()
    plot_resources()
    plot_detection_delay()
    plot_timeline()
    plot_confusion_matrix()
    plot_feature_importance()
    plot_roc_curve()
    print(f"\nAll figures saved to {FIG_DIR}/")
