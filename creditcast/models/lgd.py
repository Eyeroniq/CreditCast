"""LGD — Loss Given Default, a two-stage model on realized losses (Part 3.3).

LGD distributions are bimodal (mass near 0 = cured / fully recovered, mass near
1 = heavy loss), so naive OLS is wrong. Two stages:
  1. **Cure model**  — P(realized loss > 0 | defaulted)  (logistic)
  2. **Severity**    — E[LGD | loss > 0], LGD in (0,1]   (gradient-boosted reg.)
Predicted LGD = P(loss>0) · E[severity | loss>0]. Fit only on the *defaulted*
population (the only place LGD is observed), out-of-time like everything else.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from creditcast.config import Config, load_config, run_stamp
from creditcast.dataset import categorical_columns, feature_columns


class LGDModel:
    """Two-stage cure + severity model."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.cure = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        self.severity = LGBMRegressor(
            n_estimators=300,
            learning_rate=0.03,
            num_leaves=15,
            min_child_samples=30,
            random_state=seed,
            n_jobs=-1,
            verbose=-1,
        )
        self.features = feature_columns()
        self.categorical = categorical_columns()
        self._cat_maps: dict[str, list] = {}
        # Set when the resolved defaults hold only one outcome (e.g. every
        # default ended in a loss): the cure stage is then that constant rate.
        self._p_loss_const: float | None = None

    def _encode(self, X: pd.DataFrame) -> pd.DataFrame:
        """Ordinal-encode categoricals (stable codes for cure logit + severity)."""
        X = X[self.features].copy()
        for c in self.categorical:
            cats = self._cat_maps.get(c)
            if cats is None:
                cats = list(pd.Series(X[c].astype(str)).astype("category").cat.categories)
                self._cat_maps[c] = cats
            X[c] = pd.Categorical(X[c].astype(str), categories=cats).codes
        return X

    def fit(self, defaults: pd.DataFrame) -> "LGDModel":
        d = defaults.copy()
        d["loss_occurred"] = (d["lgd"] > 0).astype(int)
        X = self._encode(d)
        if d["loss_occurred"].nunique() < 2:
            self._p_loss_const = float(d["loss_occurred"].iloc[0])
        else:
            self.cure.fit(X, d["loss_occurred"])
        loss = d[d["loss_occurred"] == 1]
        self.severity.fit(self._encode(loss), loss["lgd"].clip(1e-3, 1))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        Xe = self._encode(X)
        p_loss = (
            np.full(len(Xe), self._p_loss_const)
            if self._p_loss_const is not None
            else self.cure.predict_proba(Xe)[:, 1]
        )
        sev = np.clip(self.severity.predict(Xe), 0, 1)
        return np.clip(p_loss * sev, 0, 1)


def _defaulted(df: pd.DataFrame) -> pd.DataFrame:
    """Resolved defaults only — the population where the final loss is known.
    (`lgd` is NaN for unresolved defaults by construction in Gold.)"""
    return df[(df["default_12m"] == 1) & df["lgd"].notna()].copy()


def fit_lgd(train: pd.DataFrame, cfg: Config | None = None) -> LGDModel:
    cfg = cfg or load_config()
    return LGDModel(seed=int(cfg.run.seed)).fit(_defaulted(train))


def save(model: LGDModel, cfg: Config | None = None) -> Path:
    cfg = cfg or load_config()
    out = cfg.path("artifacts") / "lgd.joblib"
    joblib.dump({"model": model, "stamp": run_stamp()}, out)
    return out


def load(cfg: Config | None = None) -> LGDModel:
    cfg = cfg or load_config()
    return joblib.load(cfg.path("artifacts") / "lgd.joblib")["model"]


if __name__ == "__main__":
    from creditcast.pipeline.split import make_split

    split = make_split()
    model = fit_lgd(split.train)
    save(model)
    test_def = _defaulted(split.test)
    pred = model.predict(test_def)
    obs = test_def["lgd"].to_numpy()
    print(
        f"[lgd] fit on {len(_defaulted(split.train)):,} train defaults | "
        f"OOT defaults={len(test_def):,} | mean realized LGD={obs.mean():.3f} "
        f"pred={pred.mean():.3f} | MAE={mean_absolute_error(obs, pred):.3f}"
    )
