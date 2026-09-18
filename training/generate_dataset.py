"""
training/generate_dataset.py
Đọc log thô (logs/raw_requests_*.jsonl) thu được từ MỘT phiên chạy đã biết nhãn
(normal / burst / attack), tái tạo lại các cửa sổ trượt CHÍNH XÁC như lúc online
(dùng chung common/features.py để tránh lệch train/serve), xuất ra CSV huấn luyện.

Quy trình gợi ý:
  1. Chạy app/main.py, đổi tên logs/raw_requests.jsonl -> raw_requests_normal.jsonl
     sau khi chạy xong locustfile_normal.py (xoá/khởi động lại app giữa các lần).
  2. Lặp lại với locustfile_burst.py -> raw_requests_burst.jsonl (label vẫn "normal"
     vì đây là traffic hợp lệ, chỉ tăng đột biến).
  3. Lặp lại với attack_http_flood.py / attack_slowloris.py -> raw_requests_attack.jsonl
     (label "attack").
  4. Chạy script này cho từng file:
       python training/generate_dataset.py logs/raw_requests_normal.jsonl normal
       python training/generate_dataset.py logs/raw_requests_burst.jsonl normal
       python training/generate_dataset.py logs/raw_requests_attack.jsonl attack
     Dữ liệu sẽ được NỐI TIẾP vào cùng 1 file data/training_data.csv.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.features import extract_features, FEATURE_ORDER  # noqa: E402

WINDOW_SECONDS = 5.0
HOP_SECONDS = 1.0

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "training_data.csv"
OUT_PATH.parent.mkdir(exist_ok=True)


def load_requests(path):
    reqs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                reqs.append(json.loads(line))
    reqs.sort(key=lambda r: r["ts"])
    return reqs


def generate_windows(requests):
    if not requests:
        return
    start, end = requests[0]["ts"], requests[-1]["ts"]
    t = start + WINDOW_SECONDS
    while t <= end:
        window = [r for r in requests if t - WINDOW_SECONDS <= r["ts"] < t]
        yield extract_features(window, WINDOW_SECONDS)
        t += HOP_SECONDS


def main():
    if len(sys.argv) != 3:
        print("Cách dùng: python training/generate_dataset.py <raw_log.jsonl> <normal|attack>")
        sys.exit(1)

    raw_path, label_str = sys.argv[1], sys.argv[2]
    if label_str not in ("normal", "attack"):
        print("Nhãn phải là 'normal' hoặc 'attack'")
        sys.exit(1)
    label = 1 if label_str == "attack" else 0

    requests = load_requests(raw_path)
    rows = list(generate_windows(requests))

    write_header = not OUT_PATH.exists()
    with open(OUT_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(FEATURE_ORDER + ["label"])
        for feat in rows:
            writer.writerow([feat[k] for k in FEATURE_ORDER] + [label])

    print(f"Đã ghi {len(rows)} cửa sổ (label={label}) từ {raw_path} vào {OUT_PATH}")


if __name__ == "__main__":
    main()
