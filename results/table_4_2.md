# Bảng 4.2 — So sánh mô hình học máy (Offline Evaluation)

Dataset: 796439 cửa sổ (182 attack, 796257 normal)

Đặc trưng: 8 (request_rate, ip_entropy, inter_arrival_mean, inter_arrival_std, http_method_ratio, unique_path_ratio, unique_ip_count, post_ratio)


| Mô hình | Accuracy | Precision | Recall | F1-score | ROC-AUC | CV F1 (5-fold) |
|---------|----------|-----------|--------|----------|---------|----------------|
| Baseline - Fixed threshold (request_rate) | 0.9996 | 0.3158 | 0.6522 | 0.4255 | — | — |
| RandomForest | 1.0 | 1.0 | 0.9348 | 0.9663 | 1.0 | 0.9415 ± 0.0256 |
| MLP | 0.9998 | 0.6042 | 0.6304 | 0.617 | 0.9999 | 0.3474 ± 0.1264 |
| XGBoost | 0.9998 | 0.0 | 0.0 | 0.0 | 0.5 | — |

## Feature Importance

| Đặc trưng | Importance |
|-----------|------------|
| inter_arrival_mean | 0.2293 |
| ip_entropy | 0.2026 |
| request_rate | 0.1767 |
| unique_path_ratio | 0.1699 |
| inter_arrival_std | 0.1246 |
| unique_ip_count | 0.0632 |
| http_method_ratio | 0.0199 |
| post_ratio | 0.0139 |