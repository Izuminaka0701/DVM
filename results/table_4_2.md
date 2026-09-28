# Bảng 4.2 — So sánh mô hình học máy (Offline Evaluation)

Dataset: 632 cửa sổ (182 attack, 450 normal)

Đặc trưng: 8 (request_rate, ip_entropy, inter_arrival_mean, inter_arrival_std, http_method_ratio, unique_path_ratio, unique_ip_count, post_ratio)


| Mô hình | Accuracy | Precision | Recall | F1-score | ROC-AUC | CV F1 (5-fold) |
|---------|----------|-----------|--------|----------|---------|----------------|
| Baseline - Fixed threshold (request_rate) | 0.7595 | 0.5686 | 0.6444 | 0.6042 | — | — |
| RandomForest | 0.9873 | 0.9574 | 1.0 | 0.9783 | 0.9992 | 0.9732 ± 0.0083 |
| MLP | 0.981 | 0.9375 | 1.0 | 0.9677 | 0.999 | 0.9633 ± 0.0187 |
| XGBoost | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9724 ± 0.0159 |

## Feature Importance

| Đặc trưng | Importance |
|-----------|------------|
| unique_path_ratio | 0.4822 |
| request_rate | 0.4189 |
| inter_arrival_std | 0.0700 |
| inter_arrival_mean | 0.0230 |
| ip_entropy | 0.0059 |
| http_method_ratio | 0.0000 |
| unique_ip_count | 0.0000 |
| post_ratio | 0.0000 |