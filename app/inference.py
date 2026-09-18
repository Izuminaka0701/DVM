"""
app/inference.py
3.4.1 nạp model + scaler đã huấn luyện offline (training/train_offline.py)
3.4.2 dùng cho online inference trong vòng lặp nền của app/main.py
"""
from pathlib import Path

import joblib

from common.features import features_to_vector

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


class InferenceEngine:
    def __init__(self):
        model_path = MODEL_DIR / "model.pkl"
        scaler_path = MODEL_DIR / "scaler.pkl"
        if model_path.exists() and scaler_path.exists():
            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            self.ready = True
        else:
            # Chưa chạy training/train_offline.py -> dùng luật ngưỡng tạm
            # để hệ thống vẫn chạy được ngay khi demo, không bị crash.
            self.model = None
            self.scaler = None
            self.ready = False

    def predict_proba(self, features: dict) -> float:
        if not self.ready:
            return 1.0 if features["request_rate"] > 50 else 0.0
        vector = [features_to_vector(features)]
        vector_scaled = self.scaler.transform(vector)
        proba = self.model.predict_proba(vector_scaled)[0][1]
        return float(proba)
