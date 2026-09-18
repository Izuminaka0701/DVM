"""
dashboard/dashboard.py
3.6 Giao diện Giám sát Lưu lượng.
Chạy (trong lúc app/main.py đang chạy): streamlit run dashboard/dashboard.py
"""
import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
METRICS_LOG = LOG_DIR / "metrics.jsonl"
ALERTS_LOG = LOG_DIR / "alerts.jsonl"

st.set_page_config(page_title="DDoS Real-time Monitor", layout="wide")
st.title("🛡️ Giám sát lưu lượng thời gian thực")

placeholder = st.empty()


def load_jsonl(path, max_rows=500):
    """Đọc file JSONL, bỏ qua dòng hỏng thay vì crash."""
    if not path.exists():
        return pd.DataFrame(), 0
    with open(path) as f:
        lines = f.readlines()[-max_rows:]
    rows = []
    skipped = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            skipped += 1
    return pd.DataFrame(rows), skipped


while True:
    metrics_df, skipped_metrics = load_jsonl(METRICS_LOG)
    alerts_df, _ = load_jsonl(ALERTS_LOG, max_rows=50)

    with placeholder.container():
        if skipped_metrics > 0:
            st.warning(f"⚠️ Đã bỏ qua {skipped_metrics} dòng log bị hỏng trong metrics.jsonl")

        if metrics_df.empty:
            st.info("Chưa có dữ liệu - hãy chạy app/main.py và gửi traffic vào trước.")
        else:
            metrics_df["time"] = pd.to_datetime(metrics_df["ts"], unit="s")

            # --- Hàng 1: Các chỉ số tổng quan ---
            latest = metrics_df.iloc[-1]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Request Rate", f"{latest.get('request_rate', 0):.1f} req/s")
            m2.metric("IP Entropy", f"{latest.get('ip_entropy', 0):.2f}")
            m3.metric("Attack Prob", f"{latest.get('attack_probability', 0):.2%}")
            m4.metric("Latency", f"{latest.get('processing_latency_ms', 0):.2f} ms")

            # --- Hàng 2: Biểu đồ chính ---
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📈 Request rate (req/s)")
                st.line_chart(metrics_df.set_index("time")["request_rate"])
                st.subheader("🌐 IP entropy")
                st.line_chart(metrics_df.set_index("time")["ip_entropy"])
            with col2:
                st.subheader("⚠️ Xác suất tấn công")
                st.line_chart(metrics_df.set_index("time")["attack_probability"])
                st.subheader("⏱️ Processing latency (ms)")
                st.line_chart(metrics_df.set_index("time")["processing_latency_ms"])

            # --- Hàng 3: Biểu đồ bổ sung (đặc trưng mới) ---
            col3, col4 = st.columns(2)
            with col3:
                if "unique_path_ratio" in metrics_df.columns:
                    st.subheader("📂 Unique path ratio")
                    st.line_chart(metrics_df.set_index("time")["unique_path_ratio"])
                if "unique_ip_count" in metrics_df.columns:
                    st.subheader("👤 Unique IP count")
                    st.line_chart(metrics_df.set_index("time")["unique_ip_count"])
            with col4:
                if "post_ratio" in metrics_df.columns:
                    st.subheader("📮 POST ratio")
                    st.line_chart(metrics_df.set_index("time")["post_ratio"])
                if "inter_arrival_mean" in metrics_df.columns:
                    st.subheader("⏲️ Inter-arrival mean (s)")
                    st.line_chart(metrics_df.set_index("time")["inter_arrival_mean"])

            # --- Cảnh báo ---
            st.subheader("🚨 Cảnh báo gần đây")
            if not alerts_df.empty:
                alerts_df["time"] = pd.to_datetime(alerts_df["ts"], unit="s")
                st.dataframe(alerts_df.tail(20), use_container_width=True)
            else:
                st.write("Chưa có cảnh báo nào.")

    time.sleep(2)
    st.rerun()
