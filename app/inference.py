"""
app/inference.py
3.4.1 nạp model + scaler đã huấn luyện offline (training/train_offline.py)
3.4.2 dùng cho online inference trong vòng lặp nền của app/main.py
"""
from pathlib import Path
import warnings

import joblib

from common.features import features_to_vector

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


class InferenceEngine:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.ready = False
        self.load_error = None
        self._runtime_warning_emitted = False
        model_path = MODEL_DIR / "model.pkl"
        scaler_path = MODEL_DIR / "scaler.pkl"
        if model_path.exists() and scaler_path.exists():
            try:
                # Model trong ZIP có thể được tạo bởi phiên bản scikit-learn/
                # xgboost khác máy đang chạy. Không để lỗi tương thích model
                # làm uvicorn chết trước Giai đoạn 1 (thu dữ liệu).
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                self.ready = True
            except Exception as exc:  # model cũ/hỏng/thiếu dependency
                self.load_error = f"{type(exc).__name__}: {exc}"
                warnings.warn(
                    "Không nạp được model hiện có; tạm dùng ngưỡng request_rate "
                    f"cho đến khi Giai đoạn 2 train lại model. Chi tiết: {self.load_error}",
                    RuntimeWarning,
                )

    def predict_proba(self, features: dict) -> float:
        if not self.ready:
            return 1.0 if features["request_rate"] > 50 else 0.0
        try:
            vector = [features_to_vector(features)]
            vector_scaled = self.scaler.transform(vector)
            proba_matrix = self.model.predict_proba(vector_scaled)
        except Exception as exc:
            # Một model có thể load được nhưng lỗi khi suy luận do khác phiên bản.
            # Giữ server hoạt động để raw request vẫn được thu thập.
            if not self._runtime_warning_emitted:
                warnings.warn(
                    "Model lỗi khi suy luận; chuyển sang ngưỡng request_rate. "
                    f"Chi tiết: {type(exc).__name__}: {exc}",
                    RuntimeWarning,
                )
                self._runtime_warning_emitted = True
            self.ready = False
            return 1.0 if features["request_rate"] > 50 else 0.0
        # Xử lý an toàn: nếu model chỉ train với 1 class, proba_matrix chỉ có 1 cột
        if proba_matrix.shape[1] >= 2:
            return float(proba_matrix[0][1])
        else:
            return float(proba_matrix[0][0])
