"""
experiments/run_full_experiment.py
SCRIPT TỔNG — Chạy toàn bộ quy trình thí nghiệm từ đầu đến cuối.

Quy trình:
  Giai đoạn 1: Thu dữ liệu (normal → burst → attack suite)
  Giai đoạn 2: Sinh dataset + Train offline
  Giai đoạn 3: Đo hiệu năng real-time (với model mới)
  Giai đoạn 4: Sinh biểu đồ + báo cáo

YÊU CẦU:
  - Python venv đã activate với tất cả dependencies
  - Không có process nào dùng port 8000

Chạy: python experiments/run_full_experiment.py
"""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_DIR / "logs"
DATA_DIR = PROJECT_DIR / "data"
EXP_DIR = PROJECT_DIR / "experiments"
PYTHON = sys.executable


def run(cmd, cwd=None, timeout=None, desc=""):
    """Chạy lệnh và in output."""
    print(f"\n  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd, cwd=cwd or str(PROJECT_DIR),
            timeout=timeout, capture_output=False
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {desc}")
        return False
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def start_server():
    """Khởi động uvicorn server nền."""
    print("\n  Khởi động uvicorn server...")
    # QUAN TRỌNG: KHÔNG dùng stdout=PIPE/stderr=PIPE vì trên Windows,
    # khi pipe buffer (~64KB) đầy mà parent không đọc, child process bị block
    # hoàn toàn → response time tăng từ <10ms lên 2200ms.
    # Redirect ra file log hoặc DEVNULL để server chạy bình thường.
    server_log = LOG_DIR / "server_output.log"
    server_log_fh = open(server_log, "w")
    proc = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=str(PROJECT_DIR),
        stdout=server_log_fh,
        stderr=subprocess.STDOUT,
    )
    # Lưu file handle để đóng sau
    proc._log_fh = server_log_fh  # type: ignore[attr-defined]
    time.sleep(4)  # đợi server khởi động
    if proc.poll() is not None:
        print("  [ERROR] Server không khởi động được!")
        server_log_fh.close()
        print(f"  Log: {server_log.read_text()[-500:]}")
        return None
    print(f"  Server đang chạy (PID={proc.pid})")
    return proc


def stop_server(proc):
    """Dừng server."""
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("  Server đã dừng.")
    # Đóng file handle log nếu có
    if proc and hasattr(proc, '_log_fh'):
        try:
            proc._log_fh.close()
        except Exception:
            pass


def clean_logs():
    """Xóa log cũ để bắt đầu sạch."""
    for f in LOG_DIR.glob("*"):
        if f.is_file():
            f.unlink()
    print("  Đã xóa log cũ.")


def clean_data():
    """Xóa dữ liệu training cũ."""
    csv_path = DATA_DIR / "training_data.csv"
    if csv_path.exists():
        csv_path.unlink()
    print("  Đã xóa training_data.csv cũ.")


def rename_raw_log(new_name):
    """Đổi tên raw_requests.jsonl → tên mới.
    
    QUAN TRỌNG: Server phải đã DỪNG trước khi gọi hàm này,
    vì app/main.py giữ file handle persistent trên raw_requests.jsonl.
    """
    raw = LOG_DIR / "raw_requests.jsonl"
    target = LOG_DIR / new_name
    if raw.exists():
        shutil.move(str(raw), str(target))  # move thay vì copy+unlink
        count = sum(1 for line in open(target) if line.strip())
        print(f"  → {target.name}: {count} requests")
        return count
    else:
        print(f"  ⚠️  Không tìm thấy raw_requests.jsonl")
        return 0


def phase_1_collect_data():
    """Giai đoạn 1: Thu dữ liệu."""
    print("\n" + "=" * 70)
    print("GIAI ĐOẠN 1: THU DỮ LIỆU")
    print("=" * 70)

    # --- 1A: Normal traffic (120s) ---
    print("\n--- 1A: Traffic bình thường (120s, 20 users) ---")
    server = start_server()
    if not server:
        return False
    time.sleep(5)  # đợi vòng lặp nền chạy

    run([PYTHON, "-m", "locust",
         "-f", str(EXP_DIR / "locustfile_normal.py"),
         "--host=http://localhost:8000",
         "-u", "20", "-r", "5",
         "--run-time", "120s", "--headless"],
        timeout=150, desc="Locust normal")

    time.sleep(3)
    # QUAN TRỌNG: Dừng server TRƯỚC khi rename để giải phóng file handle
    stop_server(server)
    time.sleep(2)
    rename_raw_log("raw_requests_normal.jsonl")

    # --- 1B: Burst traffic (90s) ---
    print("\n--- 1B: Traffic burst hợp lệ (90s, 150 users) ---")
    server = start_server()
    if not server:
        return False
    time.sleep(5)

    run([PYTHON, "-m", "locust",
         "-f", str(EXP_DIR / "locustfile_burst.py"),
         "--host=http://localhost:8000",
         "-u", "150", "-r", "30",
         "--run-time", "90s", "--headless"],
        timeout=150, desc="Locust burst")

    time.sleep(3)
    # QUAN TRỌNG: Dừng server TRƯỚC khi rename
    stop_server(server)
    time.sleep(2)
    rename_raw_log("raw_requests_burst.jsonl")

    # --- 1C: Attack suite ---
    print("\n--- 1C: Attack suite (5 kịch bản) ---")
    server = start_server()
    if not server:
        return False
    time.sleep(5)

    run([PYTHON, str(EXP_DIR / "run_attack_suite.py")],
        timeout=900, desc="Attack suite")

    time.sleep(3)
    stop_server(server)
    time.sleep(2)

    return True


def phase_2_train():
    """Giai đoạn 2: Sinh dataset + Train."""
    print("\n" + "=" * 70)
    print("GIAI ĐOẠN 2: SINH DATASET + HUẤN LUYỆN")
    print("=" * 70)

    # Xóa training data cũ
    clean_data()

    # Generate dataset cho normal + burst
    for name, label in [("normal", "normal"), ("burst", "normal")]:
        path = LOG_DIR / f"raw_requests_{name}.jsonl"
        if path.exists():
            run([PYTHON, "training/generate_dataset.py", str(path), label],
                desc=f"Generate {name}")

    # Generate dataset cho attack
    for f in LOG_DIR.glob("raw_requests_attack_*.jsonl"):
        run([PYTHON, "training/generate_dataset.py", str(f), "attack"],
            desc=f"Generate {f.stem}")

    # Train offline
    print("\n--- Huấn luyện mô hình ---")
    run([PYTHON, "training/train_offline.py"], desc="Train offline")
    return True


def phase_3_realtime_test():
    """Giai đoạn 3: Đo hiệu năng real-time."""
    print("\n" + "=" * 70)
    print("GIAI ĐOẠN 3: ĐO HIỆU NĂNG REAL-TIME")
    print("=" * 70)

    # Xóa metrics/alerts cũ để đo sạch
    for f in ["metrics.jsonl", "alerts.jsonl", "attack_start.log", "resource_usage.csv"]:
        p = LOG_DIR / f
        if p.exists():
            p.unlink()

    server = start_server()
    if not server:
        return False

    time.sleep(5)

    # Đo resource nền (60s)
    print("\n--- Đo CPU/RAM nền (60s) ---")
    monitor_proc = subprocess.Popen(
        [PYTHON, str(EXP_DIR / "benchmark_latency.py"), "--monitor", "120"],
        cwd=str(PROJECT_DIR),
    )

    # Chờ 10s (idle metrics)
    time.sleep(10)

    # Normal traffic 30s
    print("\n--- Normal traffic 30s (đo baseline) ---")
    run([PYTHON, "-m", "locust",
         "-f", str(EXP_DIR / "locustfile_normal.py"),
         "--host=http://localhost:8000",
         "-u", "10", "-r", "5",
         "--run-time", "30s", "--headless"],
        timeout=45, desc="Normal traffic for measurement")
    time.sleep(5)

    # Flood attack 30s
    print("\n--- HTTP Flood attack 30s ---")
    run([PYTHON, str(EXP_DIR / "attack_get_flood_variable.py"),
         "--concurrency", "200", "--duration", "30"],
        timeout=45, desc="Flood attack for measurement")
    time.sleep(5)

    # Bot mimicry 30s
    print("\n--- Bot mimicry 30s ---")
    # Override duration tạm cho lần test này
    run([PYTHON, str(EXP_DIR / "attack_bot_mimicry.py")],
        timeout=75, desc="Bot mimicry for measurement")
    time.sleep(10)

    # Đợi monitor kết thúc
    try:
        monitor_proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        monitor_proc.terminate()

    stop_server(server)
    time.sleep(2)

    # Generate report
    print("\n--- Tổng hợp báo cáo ---")
    run([PYTHON, str(EXP_DIR / "benchmark_latency.py"), "--report"],
        desc="Generate benchmark report")

    return True


def phase_4_plots():
    """Giai đoạn 4: Sinh biểu đồ."""
    print("\n" + "=" * 70)
    print("GIAI ĐOẠN 4: SINH BIỂU ĐỒ")
    print("=" * 70)
    run([PYTHON, str(EXP_DIR / "plot_results.py")], desc="Plot results")
    return True


def print_summary():
    """In tổng kết."""
    print("\n" + "=" * 70)
    print("HOÀN TẤT — TỔNG KẾT KẾT QUẢ")
    print("=" * 70)

    results_dir = PROJECT_DIR / "results"
    figures_dir = PROJECT_DIR / "figures"

    print("\n📊 Kết quả đánh giá:")
    for f in sorted(results_dir.glob("*")) if results_dir.exists() else []:
        print(f"  → {f.name}")

    print("\n📈 Biểu đồ:")
    for f in sorted(figures_dir.glob("*.png")) if figures_dir.exists() else []:
        print(f"  → {f.name}")

    print("\n📁 Thư mục quan trọng:")
    print(f"  results/  → Bảng markdown + JSON cho Chương 4")
    print(f"  figures/  → Hình ảnh cho Chương 4")
    print(f"  models/   → Model đã train (model.pkl + scaler.pkl)")
    print(f"  data/     → Dataset huấn luyện (training_data.csv)")

    print("\n🔧 Chạy dashboard:")
    print(f"  1. uvicorn app.main:app --port 8000")
    print(f"  2. streamlit run dashboard/dashboard.py")


def main():
    start = time.time()

    print("=" * 70)
    print("THỰC NGHIỆM PHÁT HIỆN DDoS THỜI GIAN THỰC")
    print("=" * 70)
    print(f"Python: {sys.version}")
    print(f"Project: {PROJECT_DIR}")
    print(f"Bắt đầu: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Đảm bảo thư mục
    LOG_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    ok = True

    # Giai đoạn 1
    if ok:
        ok = phase_1_collect_data()
        if not ok:
            print("\n[ERROR] Giai đoạn 1 thất bại!")

    # Giai đoạn 2
    if ok:
        ok = phase_2_train()
        if not ok:
            print("\n[ERROR] Giai đoạn 2 thất bại!")

    # Giai đoạn 3
    if ok:
        ok = phase_3_realtime_test()
        if not ok:
            print("\n[ERROR] Giai đoạn 3 thất bại!")

    # Giai đoạn 4
    if ok:
        ok = phase_4_plots()

    elapsed = time.time() - start
    print(f"\nTổng thời gian: {elapsed/60:.1f} phút")

    print_summary()


if __name__ == "__main__":
    main()
