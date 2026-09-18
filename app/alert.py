"""
app/alert.py
3.5.1 Cơ chế phát cảnh báo theo ngưỡng xác suất + debounce (N cửa sổ liên tiếp
      vượt ngưỡng mới cảnh báo, tránh báo động giả do nhiễu tức thời)
3.5.2 Thử nghiệm phản ứng cơ bản: log IP nghi ngờ + "chặn" IP (ghi log mô phỏng,
      KHÔNG thật sự đổi iptables trong môi trường demo để tránh tự chặn máy mình)
"""
import json
import time
from collections import Counter
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
ALERTS_LOG = LOG_DIR / "alerts.jsonl"
BLOCKED_IPS_FILE = LOG_DIR / "blocked_ips.txt"


class AlertManager:
    def __init__(self, threshold: float = 0.7, debounce_windows: int = 3, block_duration_s: int = 300):
        self.threshold = threshold
        self.debounce_windows = debounce_windows
        self.block_duration_s = block_duration_s
        self._consecutive = 0
        self._blocked = {}  # ip -> unblock_ts

    def check(self, prob: float, window_requests: list):
        top_ip = None
        if window_requests:
            top_ip, _ = Counter(r["ip"] for r in window_requests).most_common(1)[0]

        if prob >= self.threshold:
            self._consecutive += 1
        else:
            self._consecutive = 0

        triggered = self._consecutive >= self.debounce_windows
        if triggered:
            self._trigger_alert(prob, top_ip)
            self._consecutive = 0  # reset sau khi đã cảnh báo, tránh spam liên tục

        self._expire_blocks()
        return triggered, top_ip

    def _trigger_alert(self, prob: float, top_ip: str):
        record = {"ts": time.time(), "probability": prob, "blocked_ip": top_ip}
        with open(ALERTS_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
        if top_ip:
            self._block_ip(top_ip)

    def _block_ip(self, ip: str):
        self._blocked[ip] = time.time() + self.block_duration_s
        with open(BLOCKED_IPS_FILE, "a") as f:
            f.write(f"{ip}\n")
        # Triển khai thật có thể gọi:
        #   subprocess.run(["sudo", "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"])
        # Demo chỉ ghi log để an toàn cho môi trường lab.

    def _expire_blocks(self):
        now = time.time()
        expired = [ip for ip, t in self._blocked.items() if t < now]
        for ip in expired:
            del self._blocked[ip]
