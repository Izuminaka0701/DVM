"""
experiments/locustfile_normal.py
4.1.2 Giả lập lưu lượng người dùng bình thường (duyệt web thong thả).
Thêm X-Forwarded-For giả lập nhiều IP khác nhau (mô phỏng user từ nhiều nguồn).

Chạy: locust -f experiments/locustfile_normal.py --host=http://localhost:8000 \
         -u 20 -r 5 --run-time 120s --headless
"""
import random

from locust import HttpUser, between, task


class NormalShopper(HttpUser):
    wait_time = between(2, 6)  # người thật duyệt web thong thả

    def on_start(self):
        # Mỗi user mô phỏng 1 IP riêng (giả lập qua X-Forwarded-For)
        self.fake_ip = f"203.0.{random.randint(1, 50)}.{random.randint(1, 254)}"

    @task(3)
    def browse_home(self):
        self.client.get("/", headers={"X-Forwarded-For": self.fake_ip})

    @task(5)
    def view_product(self):
        self.client.get(
            f"/products/{random.randint(1, 50)}",
            headers={"X-Forwarded-For": self.fake_ip},
        )

    @task(1)
    def add_to_cart(self):
        self.client.post(
            "/cart",
            params={"product_id": random.randint(1, 50)},
            headers={"X-Forwarded-For": self.fake_ip},
        )
