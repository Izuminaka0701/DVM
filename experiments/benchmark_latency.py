"""
experiments/benchmark_latency.py
4.3 Đánh giá Định lượng Hiệu năng Hệ thống Thời gian thực.

Cải tiến:
  - Tự động tìm PID uvicorn nếu không chỉ định
  - Lưu kết quả chi tiết vào results/ (JSON)
  - Detection delay chi tiết cho từng kịch bản

Cách dùng:
  Cách 1 - đo CPU/RAM tự động (tìm PID uvicorn):
    python experiments/benchmark_latency.py --monitor 60

  Cách 2 - đo CPU/RAM cho PID cụ thể:
    python experiments/benchmark_latency.py --monitor 60 --pid 12345

  Cách 3 - tổng hợp báo cáo latency + detection delay:
    python experiments/benchmark_latency.py --report
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import psutil

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

METRICS_LOG = LOG_DIR / "metrics.jsonl"
ATTACK_LOG = LOG_DIR / "attack_start.log"
RESOURCE_LOG = LOG_DIR / "resource_usage.csv"


def find_uvicorn_pid():
    """Tự động tìm PID của process uvicorn đang chạy."""
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "uvicorn" in cmdline and "app.main" in cmdline:
                print(f"Tìm thấy uvicorn PID: {proc.info['pid']}")
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def monitor_resources(pid: int, duration_s: int):
    """Đo CPU/RAM theo thời gian và lưu vào CSV.
    
    Đo TOÀN BỘ process tree (parent + children) vì trên Windows, uvicorn
    parent process chỉ là supervisor (CPU ~0%), work thật xảy ra ở worker child.
    """
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"Không tìm thấy process với PID {pid}")
        return

    print(f"Đang đo CPU/RAM của PID {pid} (+ children) trong {duration_s}s...")
    header_needed = not RESOURCE_LOG.exists() or RESOURCE_LOG.stat().st_size == 0
    with open(RESOURCE_LOG, "a") as f:
        if header_needed:
            f.write("ts,cpu_percent,mem_mb\n")
        for i in range(duration_s):
            try:
                # Đo tổng hợp parent + tất cả child processes
                children = parent.children(recursive=True)
                all_procs = [parent] + children

                total_cpu = 0.0
                total_mem = 0.0
                for p in all_procs:
                    try:
                        total_cpu += p.cpu_percent(interval=0)
                        total_mem += p.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # cpu_percent(interval=0) lần đầu luôn trả 0, cần sleep rồi đo lại
                time.sleep(1.0)

                total_cpu = 0.0
                for p in all_procs:
                    try:
                        total_cpu += p.cpu_percent(interval=0)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                mem_mb = total_mem / (1024 * 1024)
                f.write(f"{time.time()},{total_cpu},{mem_mb:.2f}\n")
                if (i + 1) % 10 == 0:
                    n_children = len(children)
                    print(f"  [{i+1}/{duration_s}] CPU={total_cpu:.1f}%, "
                          f"RAM={mem_mb:.1f}MB ({n_children} children)")
            except psutil.NoSuchProcess:
                print(f"Process {pid} đã kết thúc.")
                break
    print(f"Đã ghi {duration_s} mẫu CPU/RAM vào {RESOURCE_LOG}")


def load_metrics_safe():
    """Đọc metrics.jsonl, bỏ qua dòng hỏng."""
    rows = []
    if not METRICS_LOG.exists():
        return rows
    with open(METRICS_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def summarize_latency():
    """4.3.1 Processing Latency (ms/window)."""
    rows = load_metrics_safe()
    if not rows:
        print("Chưa có metrics.jsonl - hãy chạy app/main.py trước.")
        return None

    latencies = [r["processing_latency_ms"] for r in rows if "processing_latency_ms" in r]
    if not latencies:
        return None

    latencies.sort()
    n = len(latencies)
    result = {
        "n_windows": n,
        "mean_ms": round(statistics.mean(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(latencies[int(n * 0.95)], 3),
        "p99_ms": round(latencies[min(int(n * 0.99), n - 1)], 3),
        "max_ms": round(max(latencies), 3),
        "min_ms": round(min(latencies), 3),
        "std_ms": round(statistics.stdev(latencies), 3) if n > 1 else 0,
    }

    print("\n--- 4.3.1 Processing latency (ms/window) ---")
    print(f"  N windows: {result['n_windows']}")
    print(f"  Mean : {result['mean_ms']} ms")
    print(f"  P50  : {result['median_ms']} ms")
    print(f"  P95  : {result['p95_ms']} ms")
    print(f"  P99  : {result['p99_ms']} ms")
    print(f"  Max  : {result['max_ms']} ms")
    print(f"  Std  : {result['std_ms']} ms")
    return result


def summarize_detection_delay():
    """4.3.2 Detection Delay (seconds) — thời gian từ lúc tấn công bắt đầu đến alert đầu tiên."""
    if not ATTACK_LOG.exists():
        print("Chưa có attack_start.log - hãy chạy 1 attack script trước.")
        return None

    alerts_path = LOG_DIR / "alerts.jsonl"
    alerts = []
    if alerts_path.exists():
        with open(alerts_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        alerts.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    results = []
    print("\n--- 4.3.2 Detection delay (giây) ---")
    with open(ATTACK_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            name, ts_str = parts
            attack_ts = float(ts_str)
            following = [a["ts"] for a in alerts if a["ts"] >= attack_ts]
            if following:
                delay = round(following[0] - attack_ts, 2)
                print(f"  {name}: {delay}s")
                results.append({"attack": name, "delay_s": delay, "detected": True})
            else:
                print(f"  {name}: KHÔNG phát hiện")
                results.append({"attack": name, "delay_s": None, "detected": False})

    return results


def summarize_resources():
    """4.3.3 Resource usage summary."""
    if not RESOURCE_LOG.exists():
        print("Chưa có resource_usage.csv - hãy chạy --monitor trước.")
        return None

    rows = []
    with open(RESOURCE_LOG) as f:
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
        return None

    cpus = [r["cpu"] for r in rows]
    mems = [r["mem_mb"] for r in rows]

    result = {
        "n_samples": len(rows),
        "cpu_mean": round(statistics.mean(cpus), 2),
        "cpu_max": round(max(cpus), 2),
        "cpu_p95": round(sorted(cpus)[int(len(cpus) * 0.95)], 2),
        "mem_mean_mb": round(statistics.mean(mems), 2),
        "mem_max_mb": round(max(mems), 2),
    }

    print("\n--- 4.3.3 Resource usage ---")
    print(f"  N samples : {result['n_samples']}")
    print(f"  CPU mean  : {result['cpu_mean']}%")
    print(f"  CPU max   : {result['cpu_max']}%")
    print(f"  CPU P95   : {result['cpu_p95']}%")
    print(f"  RAM mean  : {result['mem_mean_mb']} MB")
    print(f"  RAM max   : {result['mem_max_mb']} MB")
    return result


def generate_report():
    """Tổng hợp tất cả metrics vào 1 file JSON."""
    latency = summarize_latency()
    delays = summarize_detection_delay()
    resources = summarize_resources()

    report = {
        "processing_latency": latency,
        "detection_delay": delays,
        "resource_usage": resources,
    }

    report_path = RESULTS_DIR / "benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nĐã lưu báo cáo tổng hợp vào {report_path}")

    # Markdown table
    md_lines = [
        "# Bảng 4.3 — Hiệu năng Hệ thống Thời gian thực\n",
        "## 4.3.1 Processing Latency\n",
    ]
    if latency:
        md_lines.extend([
            "| Metric | Value |",
            "|--------|-------|",
            f"| Mean | {latency['mean_ms']} ms |",
            f"| P50 (Median) | {latency['median_ms']} ms |",
            f"| P95 | {latency['p95_ms']} ms |",
            f"| P99 | {latency['p99_ms']} ms |",
            f"| Max | {latency['max_ms']} ms |",
            "",
        ])

    md_lines.append("## 4.3.2 Detection Delay\n")
    if delays:
        md_lines.extend([
            "| Kịch bản tấn công | Delay (s) | Phát hiện? |",
            "|-------------------|-----------|------------|",
        ])
        for d in delays:
            detected = "✅ Có" if d["detected"] else "❌ Không"
            delay_str = f"{d['delay_s']}" if d["delay_s"] is not None else "—"
            md_lines.append(f"| {d['attack']} | {delay_str} | {detected} |")
        md_lines.append("")

    md_lines.append("## 4.3.3 Resource Usage\n")
    if resources:
        md_lines.extend([
            "| Metric | Value |",
            "|--------|-------|",
            f"| CPU mean | {resources['cpu_mean']}% |",
            f"| CPU max | {resources['cpu_max']}% |",
            f"| CPU P95 | {resources['cpu_p95']}% |",
            f"| RAM mean | {resources['mem_mean_mb']} MB |",
            f"| RAM max | {resources['mem_max_mb']} MB |",
        ])

    table_path = RESULTS_DIR / "table_4_3.md"
    with open(table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Đã lưu bảng markdown vào {table_path}")


def main():
    parser = argparse.ArgumentParser(description="Benchmark DDoS detection system")
    parser.add_argument("--monitor", type=int, metavar="SECONDS",
                        help="Đo CPU/RAM trong N giây")
    parser.add_argument("--pid", type=int, default=None,
                        help="PID của uvicorn (tự tìm nếu không chỉ định)")
    parser.add_argument("--report", action="store_true",
                        help="Tổng hợp báo cáo từ log đã có")
    args = parser.parse_args()

    if args.monitor:
        pid = args.pid
        if pid is None:
            pid = find_uvicorn_pid()
        if pid is None:
            print("Không tìm thấy uvicorn đang chạy. Hãy chỉ định --pid hoặc khởi động server.")
            sys.exit(1)
        monitor_resources(pid, args.monitor)
    elif args.report:
        generate_report()
    else:
        # Mặc định: generate report
        generate_report()


if __name__ == "__main__":
    main()
