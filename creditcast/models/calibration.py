"""Calibration — turn rankings into true probabilities (Part 3.2).

A model can rank perfectly yet output miscalibrated probabilities, which makes
the Expected-Loss/capital numbers wrong. We fit the calibrator on a held-out
**calibration** slice (never train, never test) so the mapping is honest.

Model-agnostic by design: it maps any model's raw PD -> calibrated PD, so the
scorecard and the challenger are calibrated through the identical mechanism.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from creditcast.config import Config, load_config, run_stamp


class Calibrator:
    """Maps raw predicted PD -> calibrated PD via isotonic or Platt scaling."""

    def __init__(self, method: str = "isotonic", pd_floor: float = 0.0):
        self.method = method
        self.pd_floor = float(pd_floor)
        self._iso: IsotonicRegression | None = None
        self._platt: LogisticRegression | None = None

    def fit(self, raw_p: np.ndarray, y: np.ndarray) -> Calibrator:
        raw_p = np.asarray(raw_p, float)
        y = np.asarray(y, int)
        if self.method == "isotonic":
            self._iso = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            self._iso.fit(raw_p, y)
        elif self.method in ("sigmoid", "platt"):
            # Platt scaling: logistic regression on the logit of the raw score
            z = np.log(np.clip(raw_p, 1e-6, 1 - 1e-6) / (1 - np.clip(raw_p, 1e-6, 1 - 1e-6)))
            self._platt = LogisticRegression().fit(z.reshape(-1, 1), y)
        else:
            raise ValueError(f"unknown calibration method: {self.method}")
        return self

    def transform(self, raw_p: np.ndarray) -> np.ndarray:
        raw_p = np.asarray(raw_p, float)
        if self._iso is not None:
            out = self._iso.transform(raw_p)
        elif self._platt is not None:
            z = np.log(np.clip(raw_p, 1e-6, 1 - 1e-6) / (1 - np.clip(raw_p, 1e-6, 1 - 1e-6)))
            out = self._platt.predict_proba(z.reshape(-1, 1))[:, 1]
        else:
            raise RuntimeError("Calibrator not fitted")
        # Regulatory PD floor: isotonic steps can hit exactly 0 and sigmoid
        # tails get arbitrarily close; no applicant is ever "riskless".
        return np.clip(out, getattr(self, "pd_floor", 0.0), 1.0)


def fit_calibrator(raw_p: np.ndarray, y: np.ndarray, cfg: Config | None = None) -> Calibrator:
    cfg = cfg or load_config()
    return Calibrator(
        method=str(cfg.calibration.method), pd_floor=float(cfg.calibration.pd_floor)
    ).fit(raw_p, y)


def cross_fit_transform(
    raw_p: np.ndarray, y: np.ndarray, cfg: Config | None = None, n_splits: int = 5
) -> np.ndarray:
    """Out-of-fold calibrated PDs for the calibration slice itself.

    The final calibrator is fit on the whole calib slice, so its in-sample
    output on that slice is optimistic. Anything *decided* on calib data (the
    approve/decline threshold) uses these cross-fitted PDs instead: each fold
    is calibrated by a calibrator that never saw it.
    """
    cfg = cfg or load_config()
    raw_p = np.asarray(raw_p, float)
    y = np.asarray(y, int)
    folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=int(cfg.run.seed))
    out = np.empty(len(raw_p), dtype=float)
    for fit_idx, oof_idx in folds.split(raw_p.reshape(-1, 1), y):
        cal = Calibrator(
            method=str(cfg.calibration.method), pd_floor=float(cfg.calibration.pd_floor)
        ).fit(raw_p[fit_idx], y[fit_idx])
        out[oof_idx] = cal.transform(raw_p[oof_idx])
    return out


def save(calibrator: Calibrator, name: str, cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    out = cfg.path("artifacts") / f"calibrator_{name}.joblib"
    joblib.dump({"calibrator": calibrator, "stamp": run_stamp()}, out)
    return out


def load(name: str, cfg: Config | None = None) -> Calibrator:
    cfg = cfg or load_config()
    return joblib.load(cfg.path("artifacts") / f"calibrator_{name}.joblib")["calibrator"]
