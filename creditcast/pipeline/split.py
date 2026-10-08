"""Out-of-time split + leakage tripwires.

The only honest test of a credit model: train on older origination vintages,
test on newer ones (never a random split — random splits leak the future into
the past via macro/vintage effects). Two held-out slices are carved from the
training vintages, each with a single job:
  - **valid** — early stopping for the challenger (it tunes the model, so it
    cannot also be used to fit the calibrator);
  - **calib** — fits the calibrators and picks the decision threshold, on data
    no model has trained or early-stopped on (Part 3.2).

`assert_no_vintage_overlap` is the leakage tripwire enforced in tests + CI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from creditcast.config import Config, load_config


@dataclass
class Split:
    train: pd.DataFrame
    calib: pd.DataFrame
    test: pd.DataFrame
    valid: pd.DataFrame = field(default_factory=pd.DataFrame)

    def summary(self) -> dict:
        def desc(d: pd.DataFrame) -> dict:
            return {
                "n": int(len(d)),
                "default_rate": float(d["default_12m"].mean()),
                "vintage_min": str(d["vintage"].min()),
                "vintage_max": str(d["vintage"].max()),
            }
        return {"train": desc(self.train), "valid": desc(self.valid),
                "calib": desc(self.calib), "test": desc(self.test)}


def _vintage_le(series: pd.Series, bound: str) -> pd.Series:
    return series <= bound        # 'YYYY-MM' strings sort chronologically

def _vintage_ge(series: pd.Series, bound: str) -> pd.Series:
    return series >= bound


def make_split(df: pd.DataFrame | None = None, cfg: Config | None = None) -> Split:
    cfg = cfg or load_config()
    if df is None:
        df = pd.read_parquet(cfg.path("gold") / "feature_matrix.parquet")

    oot = cfg.target.oot
    train_pool = df[_vintage_le(df["vintage"], oot.train_vintage_end)].copy()
    test = df[_vintage_ge(df["vintage"], oot.test_vintage_start)].copy()

    # Carve calib then valid from the training pool (stratified by target),
    # seeded for reproducibility. Fractions are of the whole training pool.
    # Neither slice may ever touch test vintages.
    seed = int(cfg.run.seed)
    calib_frac = float(oot.calib_fraction)
    valid_frac = float(oot.valid_fraction)
    calib = _stratified_sample(train_pool, calib_frac, seed)
    rest = train_pool.drop(index=calib.index)
    valid = _stratified_sample(rest, valid_frac / (1.0 - calib_frac), seed + 1)
    train = rest.drop(index=valid.index)

    split = Split(train=train.reset_index(drop=True),
                  calib=calib.reset_index(drop=True),
                  test=test.reset_index(drop=True),
                  valid=valid.reset_index(drop=True))
    assert_no_vintage_overlap(split, cfg)
    return split


def _stratified_sample(df: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    return (df.groupby("default_12m", group_keys=False)
            .sample(frac=frac, random_state=seed))


def assert_no_vintage_overlap(split: Split, cfg: Config | None = None) -> None:
    """Leakage tripwires: in-time slices (train/valid/calib) must not reach into
    test vintages, and must not share loans with each other."""
    cfg = cfg or load_config()
    boundary = cfg.target.oot.test_vintage_start
    in_time = (("train", split.train), ("valid", split.valid), ("calib", split.calib))
    for name, frame in in_time:
        if len(frame) and frame["vintage"].max() >= boundary:
            raise AssertionError(
                f"LEAKAGE: {name} contains vintage >= test boundary {boundary} "
                f"(max={frame['vintage'].max()})")
    if len(split.test) and split.test["vintage"].min() < boundary:
        raise AssertionError(
            f"LEAKAGE: test contains vintage < boundary {boundary} "
            f"(min={split.test['vintage'].min()})")

    seen: dict[int, str] = {}
    for name, frame in in_time:
        if not len(frame) or "loan_id" not in frame:
            continue
        for lid in frame["loan_id"]:
            if lid in seen:
                raise AssertionError(
                    f"LEAKAGE: loan {lid} appears in both {seen[lid]} and {name}")
            seen[lid] = name


if __name__ == "__main__":
    import json
    s = make_split()
    print("[split]", json.dumps(s.summary(), indent=2))
