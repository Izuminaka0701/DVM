# Walkthrough — Cải thiện & Chạy Hệ thống Phát hiện DDoS

## Tổng kết thay đổi đã thực hiện

### ✅ Đã sửa/cải thiện 14 file

| File | Thay đổi chính |
|------|---------------|
| [features.py](file:///d:/Code/DVM/common/features.py) | **+3 đặc trưng mới** (5→8): `unique_path_ratio`, `unique_ip_count`, `post_ratio` |
| [main.py](file:///d:/Code/DVM/app/main.py) | Atomic logging, lifespan thay on_event, `/cart` fix, `/metrics/latest` chống crash |
| [dashboard.py](file:///d:/Code/DVM/dashboard/dashboard.py) | **Fix JSONDecodeError** crash, thêm metric cards, charts cho 8 đặc trưng |
| [attack_slow_post.py](file:///d:/Code/DVM/experiments/attack_slow_post.py) | **Fix 0 cửa sổ**: thêm fast POST workers song song, giảm Content-Length |
| [attack_bot_mimicry.py](file:///d:/Code/DVM/experiments/attack_bot_mimicry.py) | Tăng duration 60s, rate 15 req/s, chỉ 2 paths → unique_path_ratio thấp |
| [locustfile_normal.py](file:///d:/Code/DVM/experiments/locustfile_normal.py) | Thêm `X-Forwarded-For` giả lập IP đa dạng |
| [locustfile_burst.py](file:///d:/Code/DVM/experiments/locustfile_burst.py) | Thêm `X-Forwarded-For`, giảm 300→150 users (tránh ConnectionAbortedError) |
| [run_attack_suite.py](file:///d:/Code/DVM/experiments/run_attack_suite.py) | Thêm slowloris, tăng duration, 10s pause, summary table |
| [train_offline.py](file:///d:/Code/DVM/training/train_offline.py) | **5-fold CV**, ROC-AUC, feature importance, classification_report, auto-save JSON+markdown |
| [benchmark_latency.py](file:///d:/Code/DVM/experiments/benchmark_latency.py) | **Auto PID**, CLI args, JSON report, markdown table cho 4.3 |
| [plot_results.py](file:///d:/Code/DVM/experiments/plot_results.py) | **7 biểu đồ**: latency, resources, detection delay, timeline, confusion matrix, feature importance, ROC |
| [run_full_experiment.py](file:///d:/Code/DVM/experiments/run_full_experiment.py) | **[MỚI]** Script master tự động toàn bộ pipeline |
| [README.md](file:///d:/Code/DVM/README.md) | Cập nhật đầy đủ 8 đặc trưng, hướng dẫn mới |
| [baseline_fixed_threshold.py](file:///d:/Code/DVM/training/baseline_fixed_threshold.py) | Giữ nguyên logic (tương thích 8 features) |

### ✅ Đã verify thành công
- Import tất cả modules: OK
- Compile syntax tất cả files: OK  
- Server khởi động + trả 8 đặc trưng: OK
- Pip install tất cả dependencies: OK

---

## HƯỚNG DẪN CHẠY THÍ NGHIỆM

> [!IMPORTANT]
> Bạn cần **4 terminal CMD riêng biệt** để chạy từng bước thủ công, hoặc chỉ cần **1 terminal** nếu dùng script tự động.

### Cách A — Tự động hoàn toàn (Khuyến nghị)

Mở 1 terminal CMD, chạy:

```cmd
cd d:\Code\DVM
venv\Scripts\activate
python experiments\run_full_experiment.py
```

Script sẽ tự động chạy toàn bộ 4 giai đoạn (~15-20 phút):
1. Thu dữ liệu: normal 120s + burst 90s + 5 attack scenarios
2. Sinh dataset + train model (5-fold CV)
3. Đo hiệu năng real-time
4. Sinh 7 biểu đồ

Sau khi xong, kết quả nằm ở:
- `results/table_4_2.md` → Copy vào **Bảng 4.2** (so sánh model)
- `results/table_4_3.md` → Copy vào **Bảng 4.3** (hiệu năng)
- `results/offline_evaluation.json` → Chi tiết đánh giá
- `results/benchmark_report.json` → Chi tiết benchmark
- `figures/*.png` → 7 hình cho Chương 4

---

### Cách B — Chạy từng bước thủ công (Để kiểm soát chi tiết)

#### CMD 1 — Server

```cmd
cd d:\Code\DVM
venv\Scripts\activate
uvicorn app.main:app --port 8000
```

#### CMD 2 — Thu dữ liệu Normal (120s)

```cmd
cd d:\Code\DVM
venv\Scripts\activate

REM 1. Thu traffic normal
locust -f experiments\locustfile_normal.py --host=http://localhost:8000 -u 20 -r 5 --run-time 120s --headless
move logs\raw_requests.jsonl logs\raw_requests_normal.jsonl
```

> [!TIP]
> Sau bước này, **restart server** (Ctrl+C trong CMD 1 rồi chạy lại) để buffer sạch.

#### CMD 2 — Thu dữ liệu Burst (90s)

```cmd
locust -f experiments\locustfile_burst.py --host=http://localhost:8000 -u 150 -r 30 --run-time 90s --headless
move logs\raw_requests.jsonl logs\raw_requests_burst.jsonl
```

> [!TIP]
> **Restart server** lần nữa.

#### CMD 2 — Chạy Attack Suite (5 kịch bản)

```cmd
python experiments\run_attack_suite.py
```

#### CMD 2 — Sinh Dataset

```cmd
REM Xóa CSV cũ nếu có
del data\training_data.csv 2>nul

python training\generate_dataset.py logs\raw_requests_normal.jsonl normal
python training\generate_dataset.py logs\raw_requests_burst.jsonl normal
python training\generate_dataset.py logs\raw_requests_attack_get_flood_low.jsonl attack
python training\generate_dataset.py logs\raw_requests_attack_get_flood_high.jsonl attack
python training\generate_dataset.py logs\raw_requests_attack_slow_post.jsonl attack
python training\generate_dataset.py logs\raw_requests_attack_bot_mimicry.jsonl attack
python training\generate_dataset.py logs\raw_requests_attack_slowloris.jsonl attack
```

#### CMD 2 — Train Model

```cmd
python training\train_offline.py
```

> [!IMPORTANT]
> Sau bước này, **restart server** để nạp model mới từ `models/model.pkl`.

#### CMD 3 — Đo CPU/RAM (trong lúc server chạy + traffic)

```cmd
cd d:\Code\DVM
venv\Scripts\activate
python experiments\benchmark_latency.py --monitor 120
```

#### CMD 4 — Trong lúc CMD 3 đang đo, chạy flood để test detection

```cmd
cd d:\Code\DVM
venv\Scripts\activate

REM Chạy flood trong lúc benchmark đang đo
python experiments\attack_get_flood_variable.py --concurrency 200 --duration 30

REM Chạy bot mimicry
python experiments\attack_bot_mimicry.py
```

#### CMD 2 — Tổng hợp kết quả

```cmd
python experiments\benchmark_latency.py --report
python experiments\plot_results.py
```

#### CMD 2 — Dashboard (optional)

```cmd
streamlit run dashboard\dashboard.py
```

---

## Kết quả thu được → Mapping vào Chương 4

| Mục luận văn | File kết quả | Nội dung |
|-------------|-------------|----------|
| **4.1** Thiết lập môi trường | README.md | Cấu hình server, locust, attack scripts |
| **4.2** Đánh giá offline | `results/table_4_2.md` | Bảng Accuracy/Precision/Recall/F1/ROC-AUC + 5-fold CV |
| **4.2** Feature importance | `figures/fig_4_2_feature_importance.png` | Đặc trưng nào đóng góp nhiều nhất |
| **4.2** Confusion matrix | `figures/fig_4_2_confusion_matrix.png` | Ma trận nhầm lẫn |
| **4.2** ROC curve | `figures/fig_4_2_roc_curve.png` | Đường cong ROC |
| **4.3.1** Processing latency | `results/table_4_3.md` + `figures/fig_4_3_1_processing_latency.png` | Mean/P50/P95/P99/Max (ms) |
| **4.3.2** Detection delay | `results/table_4_3.md` + `figures/fig_4_3_2_detection_delay.png` | Thời gian phát hiện từng loại tấn công |
| **4.3.3** CPU/RAM | `results/table_4_3.md` + `figures/fig_4_3_3_resource_usage.png` | CPU%/RAM MB theo thời gian |
| **4.3** Timeline | `figures/fig_4_3_timeline.png` | Request rate + attack probability theo thời gian |
| **4.4** So sánh | `results/table_4_2.md` (baseline row) | Baseline F1 vs ML F1 |
| **4.5** Thảo luận | Từ kết quả detection delay + F1 | Slowloris hạn chế, bot mimicry analysis |

> [!NOTE]
> Về 13 errors IDE: đây là Pylance/lint warnings do IDE chưa trỏ đúng interpreter. Chọn **Python interpreter** trong VS Code → `d:\Code\DVM\venv\Scripts\python.exe` để fix.
