# Bảng 4.3 — Hiệu năng Hệ thống Thời gian thực

## 4.3.1 Processing Latency

### Tổng Processing (T3→check_done, mỗi window)

| Metric | Value |
|--------|-------|
| Mean | 4.548 ms |
| P50 (Median) | 3.935 ms |
| P95 | 9.966 ms |
| P99 | 23.011 ms |
| Max | 35.2 ms |

### Chi tiết theo mốc thời gian T1-T6

| Giai đoạn | Ý nghĩa | Mean | P95 |
|-----------|--------|------|-----|
| T1→T2 | Ghi log raw request | 0.2911 ms | 0.6537 ms |
| T3→T4 | Feature Extraction | 1.1643 ms | 4.2636 ms |
| T4→T5 | ML Inference | 2.7098 ms | 4.9935 ms |
| T5→check_done | Alert check | 0.6737 ms | 2.8811 ms |
| T1→T6 | End-to-End | 4.8958 s | 5.0114 s (max) |

## 4.3.2 Detection Delay

| Kịch bản tấn công | Delay (s) | Phát hiện? |
|-------------------|-----------|------------|
| get_flood_c200_start | 3.06 | ✅ Có |
| bot_mimicry_start | 4.29 | ✅ Có |

## 4.3.3 Resource Usage

| Metric | Value |
|--------|-------|
| CPU mean | 81.61% |
| CPU max | 165.5% |
| CPU P95 | 159.3% |
| RAM mean | 300.4 MB |
| RAM max | 318.85 MB |