"""Leakage tripwires (Part 10.1 & 10.6).

The #1 way credit models lie is look-ahead. These tests assert the out-of-time
split never lets train/calib vintages reach into the test vintages.
"""

import pandas as pd
import pytest

from creditcast.config import load_config
from creditcast.pipeline.split import Split, assert_no_vintage_overlap


def _frame(vintages, n_each=20):
    rows = []
    for v in vintages:
        for i in range(n_each):
            rows.append({"vintage": v, "default_12m": i % 5 == 0})
    return pd.DataFrame(rows)


def test_clean_split_passes():
    cfg = load_config()  # test boundary is 2020-01
    split = Split(
        train=_frame(["2017-01", "2018-06"]),
        calib=_frame(["2019-01"]),
        test=_frame(["2020-03", "2021-01"]),
    )
    assert_no_vintage_overlap(split, cfg)  # must not raise


def test_train_reaching_into_test_is_caught():
    cfg = load_config()
    bad = Split(
        train=_frame(["2017-01", "2020-06"]),  # 2020-06 >= test boundary
        calib=_frame(["2019-01"]),
        test=_frame(["2020-03"]),
    )
    with pytest.raises(AssertionError, match="LEAKAGE"):
        assert_no_vintage_overlap(bad, cfg)


def test_test_reaching_into_train_is_caught():
    cfg = load_config()
    bad = Split(
        train=_frame(["2017-01"]),
        calib=_frame(["2018-01"]),
        test=_frame(["2019-06", "2021-01"]),  # 2019-06 < boundary
    )
    with pytest.raises(AssertionError, match="LEAKAGE"):
        assert_no_vintage_overlap(bad, cfg)


def test_valid_reaching_into_test_is_caught():
    cfg = load_config()
    bad = Split(
        train=_frame(["2017-01"]),
        calib=_frame(["2018-01"]),
        test=_frame(["2020-03"]),
        valid=_frame(["2020-02"]),  # early-stopping slice leaks
    )
    with pytest.raises(AssertionError, match="LEAKAGE"):
        assert_no_vintage_overlap(bad, cfg)


def test_shared_loan_between_in_time_slices_is_caught():
    cfg = load_config()
    train = _frame(["2017-01"]).assign(loan_id=range(0, 20))
    calib = _frame(["2018-01"]).assign(loan_id=range(19, 39))  # loan 19 shared
    valid = _frame(["2018-06"]).assign(loan_id=range(100, 120))
    bad = Split(train=train, calib=calib, test=_frame(["2020-03"]), valid=valid)
    with pytest.raises(AssertionError, match="loan 19"):
        assert_no_vintage_overlap(bad, cfg)


def test_make_split_gives_four_disjoint_stratified_slices():
    cfg = load_config()
    rows = []
    for i, v in enumerate(["2016-01", "2017-01", "2018-01", "2019-01", "2020-01", "2021-01"] * 200):
        rows.append({"loan_id": i, "vintage": v, "default_12m": int(i % 10 == 0)})
    from creditcast.pipeline.split import make_split

    s = make_split(pd.DataFrame(rows), cfg)
    ids = [set(f["loan_id"]) for f in (s.train, s.valid, s.calib, s.test)]
    assert sum(map(len, ids)) == len(rows) == len(set().union(*ids))
    pool = len(s.train) + len(s.valid) + len(s.calib)
    oot = cfg.target.oot
    assert len(s.calib) / pool == pytest.approx(float(oot.calib_fraction), abs=0.01)
    assert len(s.valid) / pool == pytest.approx(float(oot.valid_fraction), abs=0.01)
    # stratified: each slice keeps the pool's default rate
    for f in (s.train, s.valid, s.calib):
        assert f["default_12m"].mean() == pytest.approx(0.10, abs=0.01)
