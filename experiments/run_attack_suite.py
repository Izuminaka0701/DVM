"""
experiments/run_attack_suite.py
CHỈ dùng để tấn công server localhost trong testbed của chính bạn.

Điều phối tự động: xoá log cũ, chạy lần lượt từng loại tấn công đã build,
sau mỗi lần tự động lưu log thô ra file riêng có nhãn.

Cải tiến:
  - Tăng duration cho mỗi kịch bản (40-60s)
  - Thêm khoảng nghỉ 10s giữa các kịch bản để log rõ ràng
  - Tự động chạy generate_dataset.py sau toàn bộ suite
  - Thêm slowloris vào suite
  - In summary cuối cùng

YÊU CẦU: app/main.py (uvicorn) phải đang chạy sẵn ở localhost:8000.
Chạy: python experiments/run_attack_suite.py
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
EXP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(__file__).resolve().parent.parent

SCENARIOS = [
    {
        "name": "attack_get_flood_low",
        "cmd": [sys.executable, str(EXP_DIR / "attack_get_flood_variable.py"),
                "--concurrency", "50", "--duration", "40"],
        "desc": "GET Flood cường độ thấp (50 connections, 40s)",
    },
    {
        "name": "attack_get_flood_high",
        "cmd": [sys.executable, str(EXP_DIR / "attack_get_flood_variable.py"),
                "--concurrency", "400", "--duration", "40"],
        "desc": "GET Flood cường độ cao (400 connections, 40s)",
    },
    {
        "name": "attack_slow_post",
        "cmd": [sys.executable, str(EXP_DIR / "attack_slow_post.py")],
        "desc": "Slow POST + Fast POST flood (60s)",
    },
    {
        "name": "attack_bot_mimicry",
        "cmd": [sys.executable, str(EXP_DIR / "attack_bot_mimicry.py")],
        "desc": "Bot mimicry - giả lập traffic (60s)",
    },
    {
        "name": "attack_slowloris",
        "cmd": [sys.executable, str(EXP_DIR / "attack_slowloris.py")],
        "desc": "Slowloris - giữ connection chưa hoàn tất header (30s)",
    },
]

PAUSE_BETWEEN_S = 10  # nghỉ giữa các kịch bản


def reset_raw_log():
    raw = LOG_DIR / "raw_requests.jsonl"
    if raw.exists():
        raw.unlink()


def main():
    results = []
    total_start = time.time()

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(SCENARIOS)}] {scenario['desc']}")
        print(f"{'='*60}")

        reset_raw_log()
        time.sleep(1)

        t0 = time.time()
        subprocess.run(scenario["cmd"], check=False)
        elapsed = time.time() - t0

        time.sleep(3)  # để vòng lặp nền của app/main.py kịp ghi metrics cuối

        target = LOG_DIR / f"raw_requests_{scenario['name']}.jsonl"
        raw = LOG_DIR / "raw_requests.jsonl"
        n_lines = 0
        if raw.exists():
            shutil.copy(raw, target)
            with open(target) as f:
                n_lines = sum(1 for line in f if line.strip())
            print(f"  → Đã lưu {n_lines} request vào {target.name}")
        else:
            print(f"  ⚠️  Không thấy raw_requests.jsonl sau kịch bản {scenario['name']}")

        results.append({
            "name": scenario["name"],
            "requests": n_lines,
            "elapsed_s": round(elapsed, 1),
        })

        if i < len(SCENARIOS):
            print(f"\n  Nghỉ {PAUSE_BETWEEN_S}s trước kịch bản tiếp...")
            time.sleep(PAUSE_BETWEEN_S)

    total_elapsed = time.time() - total_start

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"TỔNG KẾT ATTACK SUITE ({total_elapsed:.0f}s)")
    print(f"{'='*60}")
    print(f"{'Kịch bản':<30} {'Requests':>10} {'Thời gian':>10}")
    print("-" * 52)
    for r in results:
        print(f"{r['name']:<30} {r['requests']:>10} {r['elapsed_s']:>8.1f}s")

    # --- Hướng dẫn chạy generate_dataset ---
    print(f"\n{'='*60}")
    print("BƯỚC TIẾP THEO — Sinh dataset huấn luyện:")
    print(f"{'='*60}")
    for scenario in SCENARIOS:
        target = LOG_DIR / f"raw_requests_{scenario['name']}.jsonl"
        if target.exists():
            print(f"  python training/generate_dataset.py {target} attack")


if __name__ == "__main__":
    main()
