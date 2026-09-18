"""
training/baseline_fixed_threshold.py
Baseline đơn giản để so sánh (4.2, 4.4): chỉ dựa vào request_rate, KHÔNG dùng ML.
Chỉnh RATE_THRESHOLD dựa trên phân phối request_rate thực tế thu được (ví dụ lấy
percentile 90-95 của traffic burst hợp lệ để tránh false positive quá nhiều).
"""
from common.features import FEATURE_ORDER

RATE_THRESHOLD = 50.0  # request/giây


def fixed_threshold_predict(feature_row):
    idx = FEATURE_ORDER.index("request_rate")
    return 1 if feature_row[idx] > RATE_THRESHOLD else 0
