# Bảng 4.2 — So sánh mô hình học máy (Offline Evaluation)

Dataset: 381 cửa sổ (182 attack, 199 normal)

**Chỉ số chính:** unseen-scenario out-of-fold; mỗi fold giữ trọn một normal source và một attack source ngoài tập train.

**Kiểm tra phụ:** purged chronological holdout theo từng source; purge 5 window (5 giây).

Train: 264 | Purged: 30 | Test: 87


| Mô hình | **Unseen-scenario AUC** | Balanced Acc. | F1 | Same-session F1 | Chronological AUC | Walk-forward AUC |
|---|---:|---:|---:|---:|---:|---:|
| Baseline - Fixed threshold (request_rate) | — | — | — | 0.5926 | — | — |
| LogisticRegression | 0.8709 | 0.6353 | 0.6447 | 1.0 | 1.0 | 1.0 ± 0.0 |
| RandomForest | 0.4705 | 0.5 | 0.6465 | 1.0 | 1.0 | 1.0 ± 0.0 |
| MLP | 0.5581 | 0.5901 | 0.6165 | 1.0 | 1.0 | 1.0 ± 0.0 |
| XGBoost | 0.6543 | 0.7839 | 0.8089 | 1.0 | 1.0 | 0.9834 ± 0.0156 |

## Feature Importance

| Đặc trưng | Importance |
|---|---:|
| unique_path_ratio | 1.0000 |
| request_rate | 0.0000 |
| ip_entropy | 0.0000 |
| inter_arrival_mean | 0.0000 |
| inter_arrival_std | 0.0000 |
| http_method_ratio | 0.0000 |
| unique_ip_count | 0.0000 |
| post_ratio | 0.0000 |

## Giới hạn đánh giá

Model được chọn là **XGBoost**, AUC chính = **0.6543**. AUC same-session cao không được dùng làm kết luận chính vì các window trong một phiên vẫn có phân phối rất giống nhau.

Các window chồng lấn đã được tách bằng purge gap. Tuy nhiên mỗi kịch bản hiện chỉ có một phiên thu thập; cần chạy thêm phiên độc lập và dùng toàn bộ phiên mới làm external test trước khi kết luận khả năng tổng quát hóa.