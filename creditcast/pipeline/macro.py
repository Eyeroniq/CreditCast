"""Macro-economic series and point-in-time macro features (ROADMAP 5.1).

Two monthly series per property state, stored as long CSVs in `data/macro/`
with the same shape as the public sources, so real files drop in unchanged:

- `unemployment.csv`  state, month, value   (BLS LAUS state unemployment rate, %)
- `hpi.csv`           state, month, value   (FHFA house-price index, level)

The synthetic series follow the broad 2013–2022 US path (a slow fall in
unemployment, a sharp 2020 shock, fast 2021 house-price growth) with seeded
state offsets and noise. A 30-year mortgage-rate series is deliberately not
used: the point-in-time `rate_spread` feature already measures each loan's
rate against the market rate of the months before it.

Leakage rule: a loan originated in month M only sees macro values from month
M - lag (lag >= 1), i.e. numbers already published when the loan was made.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from creditcast.config import Config, load_config

NATIONAL = "US"  # fallback row for an unknown or missing state
FEATURES = ["unemp_rate", "unemp_chg_12m", "hpi_chg_12m"]

# National unemployment anchors (month -> %), linearly interpolated between.
_UNEMP_ANCHORS = {
    "2013-01": 7.5, "2015-01": 5.8, "2017-01": 4.7, "2019-01": 3.9, "2020-02": 3.6,
    "2020-05": 7.6, "2020-12": 6.2, "2021-12": 4.2, "2022-06": 3.7,
}  # fmt: skip
# National house-price growth, annualised %, per calendar year.
_HPI_GROWTH = {2013: 6.0, 2014: 5.0, 2015: 5.5, 2016: 6.0, 2017: 6.3, 2018: 5.5,
               2019: 4.5, 2020: 6.5, 2021: 17.0, 2022: 18.0}  # fmt: skip
# Per state: unemployment offset (pts), 2020-shock multiplier, HPI growth multiplier.
_STATE_PROFILE = {
    "CA": (0.6, 1.25, 1.10), "TX": (0.2, 0.95, 1.00), "FL": (-0.1, 1.05, 1.20),
    "NY": (0.4, 1.20, 0.70), "IL": (0.8, 1.10, 0.60), "PA": (0.3, 1.05, 0.80),
    "OH": (0.4, 1.00, 0.90), "GA": (0.0, 0.95, 1.10), "NC": (0.0, 0.90, 1.00),
    "MI": (0.7, 1.40, 0.90),
}  # fmt: skip
STATES = list(_STATE_PROFILE)


def macro_dir(cfg: Config) -> Path:
    return cfg.path("macro")


def _months(cfg: Config) -> pd.PeriodIndex:
    # From two years before the first vintage (room for the lag + 12-month
    # change) to the data cutoff.
    start = pd.Period(cfg.generator.vintage_start, freq="M") - 24
    return pd.period_range(start, cfg.generator.data_cutoff, freq="M")


def generate_series(cfg: Config | None = None) -> dict[str, Path]:
    """Write seeded synthetic state series to data/macro/ and return the paths."""
    cfg = cfg or load_config()
    rng = np.random.default_rng(int(cfg.run.seed) + 11)
    months = _months(cfg)
    t = np.arange(len(months))

    anchors = pd.Series(_UNEMP_ANCHORS)
    a_idx = [
        months.get_loc(pd.Period(m, freq="M"))
        for m in anchors.index
        if pd.Period(m, freq="M") in months
    ]
    a_val = anchors[[m for m in anchors.index if pd.Period(m, freq="M") in months]].to_numpy()
    national_u = np.interp(t, a_idx, a_val)
    # The part of the path above its pre-shock level is "the 2020 shock".
    shock = np.where(
        months >= pd.Period("2020-03", freq="M"), np.clip(national_u - 3.6, 0, None), 0.0
    )
    growth = np.array([_HPI_GROWTH.get(p.year, 5.0) for p in months]) / 100 / 12

    unemp, hpi = [], []
    for state, (u_off, shock_mult, g_mult) in _STATE_PROFILE.items():
        noise = np.zeros(len(months))
        for i in range(1, len(months)):  # AR(1): persistent, not jumpy
            noise[i] = 0.85 * noise[i - 1] + rng.normal(0, 0.08)
        u = national_u + u_off + shock * (shock_mult - 1) + noise
        unemp.append(
            pd.DataFrame({"state": state, "month": months.astype(str), "value": u.round(2)})
        )
        g = growth * g_mult + rng.normal(0, 0.002, len(months))
        level = 100 * np.cumprod(1 + g)
        hpi.append(
            pd.DataFrame({"state": state, "month": months.astype(str), "value": level.round(2)})
        )

    out = macro_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    paths = {"unemployment": out / "unemployment.csv", "hpi": out / "hpi.csv"}
    pd.concat(unemp).to_csv(paths["unemployment"], index=False)
    pd.concat(hpi).to_csv(paths["hpi"], index=False)
    return paths


def load_series(cfg: Config | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or load_config()
    d = macro_dir(cfg)
    return {
        name: pd.read_csv(d / f"{name}.csv", dtype={"state": str, "month": str})
        for name in ("unemployment", "hpi")
    }


def macro_table(series: dict[str, pd.DataFrame], lag: int = 1) -> pd.DataFrame:
    """Point-in-time macro features for every (state, origination month).

    The row for (state, M) uses the series at M - lag, and the 12-month
    changes compare M - lag with M - lag - 12. A national row (state "US",
    the plain average of states) covers unknown states. Months run to one past
    the last observation so the next unseen month already has values.
    """
    if lag < 1:
        raise ValueError("macro lag must be >= 1 month (values known at origination)")
    u = series["unemployment"].pivot(index="month", columns="state", values="value")
    h = series["hpi"].pivot(index="month", columns="state", values="value")
    for frame in (u, h):
        frame.index = pd.PeriodIndex(frame.index, freq="M")
        frame[NATIONAL] = frame.mean(axis=1)
    full = pd.period_range(u.index.min(), u.index.max() + lag, freq="M")
    u, h = u.reindex(full), h.reindex(full)

    feats = {
        "unemp_rate": u.shift(lag),
        "unemp_chg_12m": u.shift(lag) - u.shift(lag + 12),
        "hpi_chg_12m": (h.shift(lag) / h.shift(lag + 12) - 1) * 100,
    }
    long = [
        f.stack(future_stack=True).rename(name).rename_axis(["vintage", "state"])
        for name, f in feats.items()
    ]
    table = pd.concat(long, axis=1).reset_index().dropna()
    table["vintage"] = table["vintage"].astype(str)
    return table[["state", "vintage", *FEATURES]].round(3).reset_index(drop=True)


def lookup_macro(df: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """Macro features for each row's (property_state, vintage).

    Unknown or missing state -> national row; missing or future vintage ->
    the latest month available for that state (what a lender would use today).
    """
    states = set(table["state"])
    st = (
        df["property_state"].where(df["property_state"].isin(states), NATIONAL)
        if "property_state" in df
        else pd.Series(NATIONAL, index=df.index)
    )
    cols = [c for c in table.columns if c not in ("state", "vintage")]
    vint = df["vintage"] if "vintage" in df else pd.Series([None] * len(df), index=df.index)
    keys = pd.DataFrame(
        {"state": st.astype(str).to_numpy(), "vintage": vint.astype("object").to_numpy()}
    )
    found = keys.merge(table, on=["state", "vintage"], how="left")[cols]
    latest = table.sort_values("vintage").groupby("state").tail(1).set_index("state")[cols]
    fallback = latest.reindex(keys["state"]).reset_index(drop=True)
    out = found.fillna(fallback).astype(float)
    out.index = df.index
    return out
