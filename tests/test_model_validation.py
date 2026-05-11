"""
test_model_validation.py — Validate ML model artifacts
"""
import os, sys, pytest, numpy as np
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

MODEL_DIR = os.path.join(PROJECT_ROOT, "models")
H5_PATH = os.path.join(MODEL_DIR, "lstm_autoencoder.h5")
KERAS_PATH = os.path.join(MODEL_DIR, "lstm_autoencoder.keras")
THRESHOLD_PATH = os.path.join(MODEL_DIR, "threshold.npy")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")

class TestArtifactsExist:
    def test_model_file_exists(self):
        assert os.path.exists(H5_PATH) or os.path.exists(KERAS_PATH), \
            "No model file found (need .h5 or .keras)"

    def test_threshold_exists(self):
        assert os.path.exists(THRESHOLD_PATH), "threshold.npy missing"

    def test_scaler_exists(self):
        assert os.path.exists(SCALER_PATH), "scaler.pkl missing"

class TestThreshold:
    def test_threshold_loadable(self):
        thr = np.load(THRESHOLD_PATH)
        assert thr.size == 1
        assert float(thr.item()) > 0

    def test_threshold_reasonable(self):
        thr = float(np.load(THRESHOLD_PATH).item())
        assert 0.001 < thr < 1000, f"Threshold {thr} seems unreasonable"

class TestScaler:
    def test_scaler_loadable(self):
        import joblib
        scaler = joblib.load(SCALER_PATH)
        assert hasattr(scaler, "transform")
        assert hasattr(scaler, "mean_")

    def test_scaler_has_8_features(self):
        import joblib
        scaler = joblib.load(SCALER_PATH)
        assert len(scaler.mean_) == 8, f"Scaler expects {len(scaler.mean_)} features, need 8"

    def test_scaler_transform(self):
        import joblib
        scaler = joblib.load(SCALER_PATH)
        sample = np.random.rand(1, 8).astype(np.float32)
        result = scaler.transform(sample)
        assert result.shape == (1, 8)

class TestModel:
    @pytest.fixture(autouse=True)
    def _load(self):
        import tensorflow as tf
        path = H5_PATH if os.path.exists(H5_PATH) else KERAS_PATH
        _orig = tf.keras.layers.Dense.__init__
        def _patch(self, *a, **kw):
            kw.pop("quantization_config", None)
            _orig(self, *a, **kw)
        tf.keras.layers.Dense.__init__ = _patch
        try:
            self.model = tf.keras.models.load_model(path, compile=False)
        finally:
            tf.keras.layers.Dense.__init__ = _orig

    def test_model_loads(self):
        assert self.model is not None

    def test_input_shape(self):
        inp = self.model.input_shape
        assert inp[-1] == 8, f"Model expects {inp[-1]} features, need 8"
        assert inp[-2] == 60, f"Model expects {inp[-2]} timesteps, need 60"

    def test_output_matches_input(self):
        assert self.model.output_shape == self.model.input_shape

    def test_inference_runs(self):
        x = np.random.rand(1, 60, 8).astype(np.float32)
        out = self.model.predict(x, verbose=0)
        assert out.shape == (1, 60, 8)

    def test_reconstruction_error_finite(self):
        x = np.random.rand(1, 60, 8).astype(np.float32)
        out = self.model.predict(x, verbose=0)
        err = float(np.mean(np.square(x - out)))
        assert np.isfinite(err)
        assert err >= 0
