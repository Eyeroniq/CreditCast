"""Cache staleness (Phase 3.6): a retrain in the same process must not keep
using the previously cached feature manifest."""

import copy
import json

import numpy as np
import pandas as pd

from creditcast import dataset
from creditcast.config import Config, load_config


def _cfg_with_gold(tmp_path) -> Config:
    cfg = Config(copy.deepcopy(dict(load_config())))
    cfg["paths"] = {
        **cfg["paths"],
        "gold": str(tmp_path / "gold"),
        "silver": str(tmp_path / "silver"),
    }
    return cfg


def test_reload_drops_cached_manifest(tmp_path, monkeypatch):
    cfg = _cfg_with_gold(tmp_path)
    gold = tmp_path / "gold"
    gold.mkdir()
    monkeypatch.setattr(dataset, "load_config", lambda: cfg)
    dataset.reload()
    try:
        (gold / "feature_manifest.json").write_text(
            json.dumps(
                {"numeric": ["fico"], "categorical": [], "protected": [], "target": "default_12m"}
            )
        )
        assert dataset.feature_columns() == ["fico"]
        (gold / "feature_manifest.json").write_text(
            json.dumps(
                {
                    "numeric": ["fico", "dti"],
                    "categorical": [],
                    "protected": [],
                    "target": "default_12m",
                }
            )
        )
        assert dataset.feature_columns() == ["fico"]  # still cached
        dataset.reload()
        assert dataset.feature_columns() == ["fico", "dti"]  # fresh
    finally:
        monkeypatch.undo()
        dataset.reload()  # back to the real manifest


def test_build_gold_reloads_the_manifest(tmp_path, monkeypatch):
    from creditcast.pipeline.gold import build_gold

    cfg = _cfg_with_gold(tmp_path)
    (tmp_path / "silver").mkdir()
    rng = np.random.default_rng(0)
    n = 40
    pd.DataFrame(
        {
            "loan_id": range(n),
            "vintage": ["2020-01", "2020-02"] * (n // 2),
            "default_12m": [0, 1] * (n // 2),
            "fico": rng.integers(600, 800, n),
            "dti": rng.uniform(10, 50, n),
            "ltv": rng.integers(50, 95, n),
            "orig_interest_rate": rng.uniform(3, 6, n),
            "orig_upb": 200_000,
            "orig_loan_term": 360,
            "occupancy_status": "P",
            "loan_purpose": "P",
            "property_type": "SF",
            "first_time_homebuyer": "N",
            "property_state": "TX",
            "borrower_race": "White",
            "ead": 190_000.0,
            "net_loss": 50_000.0,
            "resolved": 1,
        }
    ).to_parquet(tmp_path / "silver" / "loans.parquet", index=False)

    calls = []
    monkeypatch.setattr(dataset, "reload", lambda: calls.append(1))
    build_gold(cfg)
    assert calls == [1]
