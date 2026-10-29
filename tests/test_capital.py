"""Basel IRB capital (ROADMAP 5.5): the residential-mortgage risk-weight
function must reproduce the Basel II framework's published table (Annex 5,
illustrative IRB risk weights, residential mortgages, LGD 45% and 25%)."""

import numpy as np
import pytest

from creditcast.models.capital import capital_k, irb, risk_weight

# PD -> (risk weight % at LGD 45%, at LGD 25%), Basel II Annex 5
BASEL_II_ANNEX_5 = {
    0.0003: (4.15, 2.30),
    0.0005: (6.23, 3.46),
    0.0010: (10.69, 5.94),
    0.0025: (21.30, 11.83),
    0.0040: (29.94, 16.64),
    0.0050: (35.08, 19.49),
    0.0075: (46.46, 25.81),
    0.0100: (56.40, 31.33),
    0.0130: (67.00, 37.22),
    0.0150: (73.45, 40.80),
    0.0200: (87.94, 48.85),
    0.0250: (100.64, 55.91),
    0.0300: (111.99, 62.22),
    0.0400: (131.63, 73.13),
    0.0500: (148.22, 82.35),
    0.0600: (162.52, 90.29),
    0.1000: (204.41, 113.56),
    0.1500: (235.72, 130.96),
    0.2000: (253.12, 140.62),
}


@pytest.mark.parametrize("pd_hat,expected", BASEL_II_ANNEX_5.items())
def test_matches_basel_ii_published_risk_weights(pd_hat, expected):
    for lgd, rw in zip((0.45, 0.25), expected, strict=True):
        assert risk_weight(pd_hat, lgd) * 100 == pytest.approx(rw, abs=0.01)


def test_capital_rises_with_pd_and_lgd_and_is_zero_without_loss():
    pds = np.array([0.001, 0.01, 0.05, 0.2])
    k = capital_k(pds, 0.3)
    assert np.all(np.diff(k) > 0)
    assert capital_k(0.02, 0.4) > capital_k(0.02, 0.2)
    assert capital_k(0.02, 0.0) == 0.0


def test_floors_apply_and_totals_add_up():
    out = irb([0.0001, 0.02], [0.01, 0.3], [100_000, 200_000])
    k_floored = capital_k(np.array([0.0005, 0.02]), np.array([0.05, 0.3]))
    assert np.allclose(out["k"], k_floored)
    assert out["total"]["capital"] == pytest.approx(float((k_floored * [100_000, 200_000]).sum()))
    assert out["total"]["rwa"] == pytest.approx(12.5 * out["total"]["capital"])
    assert out["total"]["risk_weight"] == pytest.approx(out["total"]["rwa"] / 300_000)


def test_invalid_inputs_are_refused():
    with pytest.raises(ValueError):
        capital_k(0.0, 0.4)
    with pytest.raises(ValueError):
        capital_k(0.02, 1.2)
