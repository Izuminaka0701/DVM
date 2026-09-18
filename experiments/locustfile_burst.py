"""
experiments/locustfile_burst.py
4.1.2 Giả lập lưu lượng tăng đột biến NHƯNG hợp lệ (flash-sale) — dùng để đo
false positive rate của hệ thống (nhiều người dùng thật cùng lúc, không phải tấn công).
Thêm X-Forwarded-For giả lập nhiều IP (mô phỏng đợt sale thu hút nhiều user).

Chạy:
    locust -f experiments/locustfile_burst.py --host=http://localhost:8000 \
         -u 150 -r 30 --run-time 90s --headless
"""
import random

from locust import HttpUser, between, task


class FlashSaleShopper(HttpUser):
    wait_time = between(0.3, 1.5)  # người dùng thao tác nhanh trong đợt sale

    def on_start(self):
        # Mỗi user mô phỏng 1 IP riêng — burst hợp lệ có NHIỀU IP đa dạng
        self.fake_ip = f"198.51.{random.randint(1, 100)}.{random.randint(1, 254)}"

    @task(4)
    def view_product(self):
        self.client.get(
            f"/products/{random.randint(1, 30)}",
            headers={"X-Forwarded-For": self.fake_ip},
        )

    @task(2)
    def add_to_cart(self):
        self.client.post(
            "/cart",
            params={"product_id": random.randint(1, 30)},
            headers={"X-Forwarded-For": self.fake_ip},
        )

    @task(1)
    def browse_home(self):
        self.client.get("/", headers={"X-Forwarded-For": self.fake_ip})
