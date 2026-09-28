# Demo: Hệ thống phát hiện DDoS tầng ứng dụng thời gian thực

Project này hiện thực đúng 5 module ở **Chương 3** và tạo dữ liệu cho **Chương 4**.
Mỗi file code đều có docstring ghi rõ tương ứng với mục nào trong luận văn.

```
ddos_demo/
├── common/features.py          3.3.1, 3.3.2 - 8 đặc trưng + sliding window (dùng chung)
├── app/
│   ├── main.py                 3.1, 3.2, 3.3.2, 3.4.2 - server + collector + vòng lặp
│   ├── inference.py             3.4 - nạp model, suy luận
│   └── alert.py                 3.5 - cảnh báo + debounce + block IP
├── training/
│   ├── generate_dataset.py      3.4.1 - tái tạo cửa sổ offline từ log thô
│   ├── train_offline.py         3.4.1, 4.2 - huấn luyện + 5-fold CV + so sánh model
│   └── baseline_fixed_threshold.py   4.2, 4.4 - baseline không dùng ML
├── dashboard/dashboard.py       3.6 - giao diện giám sát (xử lý log hỏng)
├── experiments/
│   ├── locustfile_normal.py     4.1.2 - traffic bình thường (+ X-Forwarded-For)
│   ├── locustfile_burst.py      4.1.2 - traffic burst hợp lệ (+ X-Forwarded-For)
│   ├── attack_http_flood.py     4.1.2 - tấn công HTTP flood
│   ├── attack_slowloris.py      4.1.2 - tấn công Slow HTTP
│   ├── attack_get_flood_variable.py  4.1.2, 4.3.2 - GET flood cường độ tham số hoá
│   ├── attack_slow_post.py      4.1.2 - Slow POST + Fast POST flood (đã fix)
│   ├── attack_bot_mimicry.py    4.4, 4.5 - bot bắt chước traffic thật
│   ├── run_attack_suite.py      điều phối tự động 5 kịch bản tấn công
│   ├── benchmark_latency.py     4.3 - đo latency/delay/CPU-RAM (auto PID)
│   ├── plot_results.py          sinh 7 biểu đồ cho Chương 4
│   └── run_full_experiment.py   🚀 chạy TOÀN BỘ pipeline tự động
├── results/                     kết quả JSON + markdown tables
├── figures/                     biểu đồ PNG cho luận văn
├── models/                      model + scaler đã train
├── data/                        training dataset (CSV)
└── requirements.txt
```

## Cách 1 — Chạy TOÀN BỘ tự động (khuyến nghị)

```bash
cd ddos_demo
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

python experiments/run_full_experiment.py
```

Script sẽ tự động:
1. Khởi động server, thu dữ liệu normal (120s) + burst (90s)
2. Chạy 5 kịch bản tấn công (GET flood low/high, slow POST, bot mimicry, slowloris)
3. Sinh dataset + train model (5-fold CV)
4. Đo hiệu năng real-time (latency, detection delay, CPU/RAM)
5. Sinh 7 biểu đồ vào `figures/`
6. Sinh bảng markdown vào `results/` (copy vào luận văn)

Tổng thời gian: ~15-20 phút.

## Cách 2 — Chạy TỪNG BƯỚC thủ công

### Bước 0 - Cài đặt

```bash
cd ddos_demo
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

### Bước 1 - Chạy server

```bash
uvicorn app.main:app --reload --port 8000
```

Kiểm tra: `curl http://localhost:8000/` và `curl http://localhost:8000/metrics/latest`
(đợi ~5s để vòng lặp nền chạy lần đầu).

### Bước 2 - Thu dữ liệu (4.1.2)

Với **mỗi** kịch bản: khởi động lại server, chạy traffic, đổi tên log.

**A - Traffic bình thường (120s, 20 users):**
```bash
locust -f experiments/locustfile_normal.py --host=http://localhost:8000 -u 20 -r 5 --run-time 120s --headless
move logs\raw_requests.jsonl logs\raw_requests_normal.jsonl
```

**B - Traffic burst hợp lệ (90s, 150 users):**
```bash
locust -f experiments/locustfile_burst.py --host=http://localhost:8000 -u 150 -r 30 --run-time 90s --headless
move logs\raw_requests.jsonl logs\raw_requests_burst.jsonl
```

**C - 5 kịch bản tấn công (tự động):**
```bash
python experiments/run_attack_suite.py
```

### Bước 3 - Sinh dataset (3.4.1)

```bash
python training/generate_dataset.py logs/raw_requests_normal.jsonl normal
python training/generate_dataset.py logs/raw_requests_burst.jsonl normal
python training/generate_dataset.py logs/raw_requests_attack_get_flood_low.jsonl attack
python training/generate_dataset.py logs/raw_requests_attack_get_flood_high.jsonl attack
python training/generate_dataset.py logs/raw_requests_attack_slow_post.jsonl attack
python training/generate_dataset.py logs/raw_requests_attack_bot_mimicry.jsonl attack
python training/generate_dataset.py logs/raw_requests_attack_slowloris.jsonl attack
```

### Bước 4 - Huấn luyện (3.4.1, 4.2)

```bash
python training/train_offline.py
```

Kết quả:
- Console: bảng metrics + 5-fold CV + feature importance
- `results/offline_evaluation.json`: kết quả chi tiết
- `results/table_4_2.md`: bảng markdown cho luận văn

### Bước 5 - Dashboard (3.6)

```bash
uvicorn app.main:app --reload --port 8000    # terminal 1
streamlit run dashboard/dashboard.py          # terminal 2
```

### Bước 6 - Đo hiệu năng (4.3)

```bash
# Đo CPU/RAM (auto tìm PID uvicorn, 60 giây):
python experiments/benchmark_latency.py --monitor 60

# Tổng hợp báo cáo:
python experiments/benchmark_latency.py --report

# Sinh biểu đồ:
python experiments/plot_results.py
```

Kết quả:
- `results/benchmark_report.json`: metrics chi tiết
- `results/table_4_3.md`: bảng markdown cho luận văn
- `figures/fig_4_*.png`: 7 biểu đồ

## 8 Đặc trưng (3.3.1)

| # | Đặc trưng | Mô tả |
|---|-----------|-------|
| 1 | `request_rate` | Số request/giây trong cửa sổ |
| 2 | `ip_entropy` | Entropy Shannon phân bố IP nguồn |
| 3 | `inter_arrival_mean` | Thời gian trung bình giữa 2 request liên tiếp |
| 4 | `inter_arrival_std` | Độ lệch chuẩn thời gian giữa 2 request |
| 5 | `http_method_ratio` | Tỉ lệ GET/tổng request |
| 6 | `unique_path_ratio` | Tỉ lệ path duy nhất/tổng (bot lặp ít path) |
| 7 | `unique_ip_count` | Số IP phân biệt (bot dùng ít IP) |
| 8 | `post_ratio` | Tỉ lệ POST/tổng (phát hiện slow POST) |

## Các mốc thời gian T1-T6 (Chương 4 - Đánh giá hiệu năng)

Pipeline phát hiện DDoS được đo tại 6 mốc thời gian:

```
T1: Request được Web Server tiếp nhận           (app/main.py - middleware)
↓
T2: Log được ghi nhận                            (app/main.py - raw_fh.write)
↓
T3: Window hoàn tất                              (app/main.py - feature_extraction_loop)
↓
T4: Feature extraction hoàn tất                  (common/features.py - extract_features)
↓
T5: ML inference hoàn tất                        (app/inference.py - predict_proba)
↓
T6: Alert được sinh ra                           (app/alert.py - check)
```

Từ đó Chương 4 có thể đo:

- **Feature Extraction Latency** = T4 – T3
- **Inference Latency** = T5 – T4
- **End-to-End Detection Delay** = T6 – T1 hoặc theo định nghĩa thống nhất của nhóm
- **Processing overhead** của collector/inference đối với Web Server = T6 – T3

Các mốc thời gian được ghi tự động vào `logs/metrics.jsonl` mỗi chu kỳ cửa sổ trượt.
Chạy `python experiments/benchmark_latency.py --report` để xem báo cáo chi tiết.

## Hạn chế (4.5)

- **Slowloris** không bắt được ở tầng ứng dụng (header chưa hoàn tất → không ghi log)
- Thử nghiệm trên 1 node, traffic mô phỏng
- IP giả lập qua `X-Forwarded-For`, không phải nhiều IP thật
- **Bot mimicry** với rate rất thấp có thể không phát hiện (cần thêm đặc trưng)

## Ghi chú

- **KHÔNG** chạy attack script nhắm vào server không thuộc quyền sở hữu của bạn
- Cơ chế "chặn IP" chỉ ghi log, không đổi firewall
#
