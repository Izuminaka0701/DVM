# Bảng 4.2 — So sánh mô hình học máy (Offline Evaluation)

Dataset: 377 cửa sổ (182 attack, 195 normal)

Đặc trưng: 8 (request_rate, ip_entropy, inter_arrival_mean, inter_arrival_std, http_method_ratio, unique_path_ratio, unique_ip_count, post_ratio)


| Mô hình | Accuracy | Precision | Recall | F1-score | ROC-AUC | CV F1 (5-fold) |
|---------|----------|-----------|--------|----------|---------|----------------|
| Baseline - Fixed threshold (request_rate) | 0.6737 | 0.6316 | 0.7826 | 0.699 | — | — |
| RandomForest | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 ± 0.0 |
| MLP | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 ± 0.0 |
| XGBoost | 0.9895 | 0.9787 | 1.0 | 0.9892 | 0.9898 | 0.9973 ± 0.0053 |

## Feature Importance

| Đặc trưng | Importance |
|-----------|------------|
| unique_path_ratio | 0.3830 |
| post_ratio | 0.1173 |
| http_method_ratio | 0.1163 |
| ip_entropy | 0.1098 |
| request_rate | 0.0765 |
| unique_ip_count | 0.0709 |
| inter_arrival_mean | 0.0689 |
| inter_arrival_std | 0.0573 |