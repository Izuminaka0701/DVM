"""
app/main.py
Gộp chung trong 1 process cho đơn giản khi demo (nhưng logic vẫn tách thành
từng module riêng để mô tả đúng kiến trúc 5 module ở Chương 3):
  - Traffic Collector (3.2): middleware ghi request vào buffer trong bộ nhớ
  - Feature Extractor (3.3): vòng lặp nền trượt cửa sổ, tính 8 đặc trưng
  - ML Inference (3.4.2): gọi model đã train offline để suy luận
  - Alert (3.5): kiểm tra ngưỡng + debounce + "chặn" IP

Chạy từ thư mục gốc ddos_demo/:
    uvicorn app.main:app --reload --port 8000
"""
import asyncio
import json
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.alert import AlertManager
from app.inference import InferenceEngine
from common.features import extract_features

WINDOW_SECONDS = 5.0   # kích thước cửa sổ trượt W (3.3.2)
HOP_SECONDS = 1.0      # bước trượt - tính lại đặc trưng mỗi 1 giây

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
METRICS_LOG = LOG_DIR / "metrics.jsonl"
RAW_LOG = LOG_DIR / "raw_requests.jsonl"

# ---- Persistent file handles — tránh open/close mỗi request (Windows NTFS rất chậm) ----
_raw_fh = None
_metrics_fh = None


def _open_log_files():
    """Mở file handle persistent cho raw log và metrics log."""
    global _raw_fh, _metrics_fh
    _raw_fh = open(RAW_LOG, "a", buffering=1)       # line-buffered
    _metrics_fh = open(METRICS_LOG, "a", buffering=1)


def _close_log_files():
    """Đóng file handle khi shutdown."""
    global _raw_fh, _metrics_fh
    if _raw_fh:
        _raw_fh.close()
    if _metrics_fh:
        _metrics_fh.close()


# ---- 3.2 Traffic Collector: buffer request trong bộ nhớ ----
request_buffer: deque = deque()

engine = InferenceEngine()   # 3.4 nạp model đã train offline
alerter = AlertManager()     # 3.5 cảnh báo + debounce + block IP


# ---- 3.3 + 3.4.2 + 3.5: vòng lặp nền chạy mỗi HOP_SECONDS ----
async def feature_extraction_loop():
    while True:
        await asyncio.sleep(HOP_SECONDS)
        now = time.time()
        cutoff = now - WINDOW_SECONDS

        # 3.3.2: trượt cửa sổ - loại bỏ request cũ hơn (now - W)
        while request_buffer and request_buffer[0]["ts"] < cutoff:
            request_buffer.popleft()

        window_requests = list(request_buffer)

        t0 = time.perf_counter()
        features = extract_features(window_requests, WINDOW_SECONDS)
        prob = engine.predict_proba(features)  # 3.4.2 online inference
        processing_latency_ms = (time.perf_counter() - t0) * 1000

        triggered, top_ip = alerter.check(prob, window_requests)  # 3.5

        record = {
            "ts": now,
            **features,
            "attack_probability": prob,
            "processing_latency_ms": processing_latency_ms,
            "alert_triggered": triggered,
            "top_ip": top_ip,
        }
        # Ghi metrics qua file handle persistent (không open/close mỗi lần)
        line = json.dumps(record) + "\n"
        if _metrics_fh:
            _metrics_fh.write(line)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: mở log files + khởi tạo vòng lặp trích xuất đặc trưng
    _open_log_files()
    task = asyncio.create_task(feature_extraction_loop())
    yield
    # Shutdown: huỷ vòng lặp + đóng file handles
    task.cancel()
    _close_log_files()


app = FastAPI(title="DDoS Demo - Victim Web Server", lifespan=lifespan)


@app.middleware("http")
async def collector_middleware(request: Request, call_next):
    ts = time.time()
    # Đọc IP từ X-Forwarded-For nếu có (để attack_http_flood.py có thể giả lập
    # nhiều IP nguồn khác nhau khi demo trên 1 máy), fallback về socket IP thật.
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    method = request.method
    path = request.url.path
    entry = {"ts": ts, "ip": ip, "method": method, "path": path}
    request_buffer.append(entry)
    # Ghi raw log qua file handle persistent — KHÔNG open/close mỗi request
    # (trên Windows NTFS, open/close mỗi request + lock = ~100ms × N users = 2000ms)
    if _raw_fh:
        _raw_fh.write(json.dumps(entry) + "\n")
    response = await call_next(request)
    return response


# ---- Endpoint giả lập trang TMĐT để Locust/attack script gọi vào ----
@app.get("/")
async def home():
    return {"page": "home"}


@app.get("/products/{product_id}")
async def product_detail(product_id: int):
    return {"product_id": product_id, "name": f"Product {product_id}"}


@app.post("/cart")
async def add_to_cart(product_id: int = 0):
    """Nhận product_id qua query param hoặc body. Mặc định 0 nếu không có
    (để slow_post gửi body rỗng/partial không bị lỗi validation)."""
    return {"status": "added", "product_id": product_id}


@app.get("/metrics/latest")
async def latest_metrics():
    if not METRICS_LOG.exists():
        return JSONResponse({"detail": "no metrics yet"}, status_code=404)
    with open(METRICS_LOG) as f:
        lines = f.readlines()
    if not lines:
        return JSONResponse({"detail": "no metrics yet"}, status_code=404)
    # Đọc ngược để tìm dòng JSON hợp lệ cuối cùng (tránh crash do dòng ghi dở)
    for line in reversed(lines):
        line = line.strip()
        if line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return JSONResponse({"detail": "no valid metrics yet"}, status_code=404)
