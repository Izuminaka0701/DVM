"""
common/features.py
Tính 8 đặc trưng đại diện cho một cửa sổ request (mục 3.3.1 luận văn):

Nhóm 1 – Rate & Timing:
  - request_rate          : số request / giây trong cửa sổ
  - inter_arrival_mean    : thời gian trung bình giữa các request liên tiếp (s)
  - inter_arrival_std     : độ lệch chuẩn thời gian giữa các request (s)

Nhóm 2 – Source Distribution:
  - ip_entropy            : entropy Shannon của phân bố IP nguồn
  - unique_ip_count       : số IP phân biệt trong cửa sổ

Nhóm 3 – Request Pattern:
  - http_method_ratio     : tỉ lệ GET trên tổng số request
  - post_ratio            : tỉ lệ POST trên tổng số request
  - unique_path_ratio     : tỉ lệ path duy nhất / tổng request (bot thường lặp ít path)

Module này được import CẢ ở app/ (online inference) LẪN training/ (offline dataset
generation) để đảm bảo công thức đặc trưng giống hệt nhau giữa lúc train và lúc serve
(tránh train/serve skew - lỗi rất hay gặp trong hệ thống ML thời gian thực).
"""
import math
from collections import Counter


def shannon_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def extract_features(requests, window_seconds: float) -> dict:
    """
    requests: list các dict {"ts": float, "ip": str, "method": str, "path": str}
              đã nằm trong cửa sổ [now - window_seconds, now]
    """
    n = len(requests)
    if n == 0:
        return {
            "request_rate": 0.0,
            "ip_entropy": 0.0,
            "inter_arrival_mean": window_seconds,
            "inter_arrival_std": 0.0,
            "http_method_ratio": 0.0,
            "unique_path_ratio": 0.0,
            "unique_ip_count": 0,
            "post_ratio": 0.0,
        }

    # --- Nhóm 1: Rate & Timing ---
    request_rate = n / window_seconds

    timestamps = sorted(r["ts"] for r in requests)
    if len(timestamps) > 1:
        deltas = [t2 - t1 for t1, t2 in zip(timestamps[:-1], timestamps[1:])]
        mean_delta = sum(deltas) / len(deltas)
        var_delta = sum((d - mean_delta) ** 2 for d in deltas) / len(deltas)
        std_delta = math.sqrt(var_delta)
    else:
        mean_delta = window_seconds
        std_delta = 0.0

    # --- Nhóm 2: Source Distribution ---
    ip_counter = Counter(r["ip"] for r in requests)
    ip_entropy = shannon_entropy(ip_counter)
    unique_ip_count = len(ip_counter)

    # --- Nhóm 3: Request Pattern ---
    method_counter = Counter(r["method"] for r in requests)
    get_ratio = method_counter.get("GET", 0) / n
    post_ratio = method_counter.get("POST", 0) / n

    path_counter = Counter(r["path"] for r in requests)
    unique_path_ratio = len(path_counter) / n

    return {
        "request_rate": request_rate,
        "ip_entropy": ip_entropy,
        "inter_arrival_mean": mean_delta,
        "inter_arrival_std": std_delta,
        "http_method_ratio": get_ratio,
        "unique_path_ratio": unique_path_ratio,
        "unique_ip_count": unique_ip_count,
        "post_ratio": post_ratio,
    }


FEATURE_ORDER = [
    "request_rate",
    "ip_entropy",
    "inter_arrival_mean",
    "inter_arrival_std",
    "http_method_ratio",
    "unique_path_ratio",
    "unique_ip_count",
    "post_ratio",
]


def features_to_vector(features: dict) -> list:
    return [features[k] for k in FEATURE_ORDER]
