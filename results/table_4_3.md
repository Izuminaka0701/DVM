# Bảng 4.3 — Hiệu năng Hệ thống Thời gian thực

## 4.3.1 Processing Latency

### Tổng Processing (T3→T6)

| Metric | Value |
|--------|-------|
| Mean | 34.191 ms |
| P50 (Median) | 33.626 ms |
| P95 | 46.238 ms |
| P99 | 59.858 ms |
| Max | 87.546 ms |

### Chi tiết theo mốc thời gian T1-T6

| Giai đoạn | Mean | P95 |
|-----------|------|-----|
| T3→T4 Feature Extraction | 1.1462 ms | 4.4907 ms |
| T4→T5 ML Inference | 32.5548 ms | 40.6155 ms |
| T5→T6 Alert | 0.4902 ms | 1.6471 ms |
| T1→T6 End-to-End | 4.6669 s | 5.0589 s (max) |

## 4.3.2 Detection Delay

| Kịch bản tấn công | Delay (s) | Phát hiện? |
|-------------------|-----------|------------|
| get_flood_c200_start | 44.66 | ✅ Có |
| bot_mimicry_start | 8.29 | ✅ Có |

## 4.3.3 Resource Usage

| Metric | Value |
|--------|-------|
| CPU mean | 29.16% |
| CPU max | 103.0% |
| CPU P95 | 98.4% |
| RAM mean | 189.7 MB |
| RAM max | 207.22 MB |