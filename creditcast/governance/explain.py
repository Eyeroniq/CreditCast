"""Local explanations for the *champion* model (feeds adverse-action reasons).

The reasons given to a declined applicant must come from the model that made
the decision. `decision.champion` in config picks it:

- **challenger** — signed local SHAP contributions (TreeExplainer);
- **scorecard**  — *points lost* per characteristic: for each variable, the
  points the applicant's bin earns vs the best attainable bin of that
  variable. This is the standard scorecard adverse-action method.

Both return the same frame — columns `feature`, `value`, `shap` (positive =
raises risk), sorted by |shap| — so `reason_codes.reason_codes` works on either.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config
from creditcast.dataset import feature_columns
from creditcast.governance import shap_explain


def scorecard_points_lost(scorecard, x_row: pd.DataFrame) -> pd.DataFrame:
    """Points lost vs the best bin, per feature, for one applicant."""
    feats = feature_columns()
    table = scorecard.table(style="detailed")
    woe = scorecard.binning_process_.transform(x_row[feats], metric="woe")
    rows = []
    for feat in feats:
        bins = table[table["Variable"] == feat]
        if bins.empty or feat not in woe:          # dropped by IV selection
            lost = 0.0
        else:
            # The applicant's bin is the one whose WoE matches their WoE.
            own = bins.iloc[int(np.argmin(np.abs(bins["WoE"].to_numpy(float)
                                                 - float(woe[feat].iloc[0]))))]
            lost = float(bins["Points"].max() - own["Points"])
        rows.append({"feature": feat, "value": str(x_row[feat].iloc[0]), "shap": lost})
    return (pd.DataFrame(rows)
            .sort_values("shap", key=np.abs, ascending=False).reset_index(drop=True))


def local_drivers(x_row: pd.DataFrame, cfg: Config | None = None,
                  scorecard=None, explainer=None) -> pd.DataFrame:
    """Champion-consistent local attribution for one applicant."""
    cfg = cfg or load_config()
    if str(cfg.decision.champion) == "scorecard":
        if scorecard is None:
            from creditcast.models import scorecard as sc_mod
            scorecard = sc_mod.load(cfg)
        return scorecard_points_lost(scorecard, x_row)
    explainer = explainer or shap_explain.build_explainer(cfg=cfg)
    return shap_explain.local_attribution(explainer, x_row)
