# Bảng 4.3 — Hiệu năng Hệ thống Thời gian thực

## 4.3.1 Processing Latency

### Tổng Processing (T3→T6)

| Metric | Value |
|--------|-------|
| Mean | 4.751 ms |
| P50 (Median) | 4.111 ms |
| P95 | 8.847 ms |
| P99 | 13.359 ms |
| Max | 31.182 ms |

### Chi tiết theo mốc thời gian T1-T6

| Giai đoạn | Ý nghĩa | Mean | P95 |
|-----------|--------|------|-----|
| T1→T2 | Ghi log raw request | 0.1614 ms | 0.3264 ms |
| T3→T4 | Feature Extraction | 1.2301 ms | 4.576 ms |
| T4→T5 | ML Inference | 2.8168 ms | 4.051 ms |
| T5→T6 | Alert | 0.7043 ms | 3.0618 ms |
| T1→T6 | End-to-End | 4.6379 s | 5.0141 s (max) |

## 4.3.2 Detection Delay

| Kịch bản tấn công | Delay (s) | Phát hiện? |
|-------------------|-----------|------------|
| get_flood_c200_start | 3.86 | ✅ Có |
| bot_mimicry_start | 7.51 | ✅ Có |

## 4.3.3 Resource Usage

| Metric | Value |
|--------|-------|
| CPU mean | 164.81% |
| CPU max | 237.4% |
| CPU P95 | 231.2% |
| RAM mean | 294.55 MB |
| RAM max | 348.33 MB |