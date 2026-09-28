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
import argparse
import json
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.features import extract_features, FEATURE_ORDER  # noqa: E402

WINDOW_SECONDS = 5.0
HOP_SECONDS = 1.0

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "training_data.csv"
OUT_PATH.parent.mkdir(exist_ok=True)


def load_requests(path, ip_prefix=None):
    reqs = []
    excluded = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                request = json.loads(line)
                if ip_prefix and not request["ip"].startswith(ip_prefix):
                    excluded += 1
                    continue
                reqs.append(request)
    reqs.sort(key=lambda r: r["ts"])
    return reqs, excluded


def generate_windows(requests):
    if not requests:
        return
    start, end = requests[0]["ts"], requests[-1]["ts"]
    pending = deque()
    index = 0
    t = start + WINDOW_SECONDS
    while t <= end:
        while index < len(requests) and requests[index]["ts"] < t:
            pending.append(requests[index])
            index += 1
        while pending and pending[0]["ts"] < t - WINDOW_SECONDS:
            pending.popleft()
        # Khoảng ngắt trong log không phải traffic normal: không tạo mẫu rỗng.
        if pending:
            record = extract_features(list(pending), WINDOW_SECONDS)
            # Metadata chỉ dùng để chia train/test đúng theo thời gian; không
            # được đưa vào vector đặc trưng của model.
            record["window_end_ts"] = t
            yield record
        t += HOP_SECONDS


def main():
    parser = argparse.ArgumentParser(description="Tạo window từ log request thực tế")
    parser.add_argument("raw_path", type=Path)
    parser.add_argument("label", choices=("normal", "attack"))
    parser.add_argument("--ip-prefix", help="IP giả lập của kịch bản, ví dụ 203.0. hoặc 198.51.; các request khác bị loại khỏi dataset, log gốc giữ nguyên")
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    parser.add_argument("--source", help="Tên phiên thu thập; mặc định là tên file raw")
    args = parser.parse_args()
    label = 1 if args.label == "attack" else 0

    requests, excluded = load_requests(args.raw_path, args.ip_prefix)
    if not requests:
        parser.error(f"Không có request hợp lệ trong {args.raw_path}; không ghi dataset")
    rows = list(generate_windows(requests))
    if not rows:
        parser.error(f"Không có cửa sổ 5 giây chứa request trong {args.raw_path}; không ghi dataset")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_header = not args.output.exists() or args.output.stat().st_size == 0
    expected_header = FEATURE_ORDER + ["label", "source", "window_end_ts"]
    if not write_header:
        with open(args.output, newline="", encoding="utf-8") as existing:
            current_header = next(csv.reader(existing), [])
        if current_header != expected_header:
            parser.error(
                f"Schema cũ trong {args.output}. Hãy xóa/tạo lại dataset để có "
                "source và window_end_ts; không nối dữ liệu vào schema cũ."
            )
    source = args.source or args.raw_path.stem
    with open(args.output, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(expected_header)
        for feat in rows:
            writer.writerow(
                [feat[k] for k in FEATURE_ORDER]
                + [label, source, feat["window_end_ts"]]
            )

    print(f"Đã ghi {len(rows)} cửa sổ (label={label}) từ {len(requests)} request vào {args.output}; "
          f"loại {excluded} request không khớp nguồn khỏi dataset (log gốc không đổi)")


if __name__ == "__main__":
    main()
