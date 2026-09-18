"""
experiments/attack_bot_mimicry.py
CHỈ dùng để tấn công server localhost trong testbed của chính bạn.

4.4 / 4.5 - Tấn công "bắt chước" traffic hợp lệ: giữ request_rate KHÔNG quá cao
(không flood ồ ạt), nhưng dùng RẤT ÍT IP nguồn lặp lại liên tục, nhắm vào cùng
1-2 trang cụ thể — kiểm tra xem mô hình ML có phát hiện được nhờ:
  - ip_entropy thấp (ít IP phân biệt)
  - unique_ip_count thấp
  - unique_path_ratio thấp (lặp lại ít path)
mặc dù request_rate không cao bất thường.

Đây là kịch bản "khó" nên đưa vào 4.4 để chứng minh mô hình ML học được pattern
tinh vi hơn baseline ngưỡng tĩnh (baseline CHỈ nhìn request_rate nên gần như chắc
chắn sẽ bỏ sót kịch bản này).

Cải tiến so với phiên bản cũ:
  - Tăng duration lên 60s để có đủ cửa sổ
  - Tăng rate lên 15 req/s/bot để tạo nhiều window hơn
  - Giữ 3 IP nhưng chỉ nhắm 2 path (giảm unique_path_ratio rõ rệt)

Chạy: python experiments/attack_bot_mimicry.py
"""
import asyncio
import time
from pathlib import Path

import aiohttp

# Chỉ nhắm vào 2 path duy nhất (rất ít đa dạng so với user thật)
TARGET_PATHS = [
    "http://localhost:8000/products/1",
    "http://localhost:8000/products/2",
]
NUM_BOT_IPS = 3          # rất ít IP → ip_entropy thấp, unique_ip_count = 3
REQUEST_RATE_PER_BOT = 15  # req/s mỗi bot — tổng ~45 req/s, vừa phải
DURATION_S = 60

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


async def bot_worker(session, stop_at, fake_ip):
    headers = {"X-Forwarded-For": fake_ip}
    interval = 1.0 / REQUEST_RATE_PER_BOT
    idx = 0
    while time.time() < stop_at:
        target = TARGET_PATHS[idx % len(TARGET_PATHS)]
        try:
            async with session.get(target, headers=headers) as resp:
                await resp.read()
        except Exception:
            pass
        idx += 1
        await asyncio.sleep(interval)


async def main():
    start = time.time()
    with open(LOG_DIR / "attack_start.log", "a") as f:
        f.write(f"bot_mimicry_start\t{start}\n")

    stop_at = start + DURATION_S
    fake_ips = [f"172.16.0.{i}" for i in range(NUM_BOT_IPS)]
    async with aiohttp.ClientSession() as session:
        workers = [bot_worker(session, stop_at, ip) for ip in fake_ips]
        await asyncio.gather(*workers)

    print(f"Bot mimicry xong sau {DURATION_S}s, bắt đầu lúc {start}")


if __name__ == "__main__":
    asyncio.run(main())
