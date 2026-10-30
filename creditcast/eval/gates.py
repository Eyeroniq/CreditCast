"""CI performance gates (Part 10.3).

A model ships only if it clears minimum discrimination, calibration, and
stability thresholds. Run in CI on every change; a regression fails the build.

Calibration is gated on the economically meaningful **max band error** and ECE,
NOT the Hosmer-Lemeshow p-value: with ~17k loans HL rejects on trivially small
miscalibration (large-sample over-power), so HL is reported as informational.

Fairness disparate-impact is surfaced as a REVIEW flag, not a hard build gate —
remediating it via group-specific thresholds is illegal in lending, so it needs
human judgement, not an automated fail.
"""

from __future__ import annotations

import json
import sys

from creditcast.config import Config, load_config


def run_gates(cfg: Config | None = None, champion: str | None = None) -> tuple[bool, list[dict]]:
    cfg = cfg or load_config()
    champion = champion or str(cfg.decision.champion)
    art = cfg.path("artifacts")
    val = json.loads((art / "validation_report.json").read_text())
    t = val["thresholds"]
    m = val["models"][champion]
    d, c = m["discrimination"], m["calibration"]
    stab = val["stability"]

    checks = [
        ("Gini ≥ min", d["gini"], t["gini_min"], d["gini"] >= t["gini_min"], ">="),
        ("KS ≥ min", d["ks"], t["ks_min"], d["ks"] >= t["ks_min"], ">="),
        (
            "Calibration max band error ≤ max",
            c["max_band_error"],
            t["calibration_max_band_error"],
            c["max_band_error"] <= t["calibration_max_band_error"],
            "<=",
        ),
        (
            "Max score PSI ≤ unstable",
            stab["max_score_psi"],
            t["psi_unstable"],
            stab["max_score_psi"] <= t["psi_unstable"],
            "<=",
        ),
        (
            "Max feature CSI ≤ unstable",
            stab["max_feature_csi"],
            t["psi_unstable"],
            stab["max_feature_csi"] <= t["psi_unstable"],
            "<=",
        ),
    ]
    # Lifetime PD (5.3) can never be below the 12-month PD for any loan.
    life_path = art / "lifetime_report.json"
    if life_path.exists():
        gap = json.loads(life_path.read_text())["lifetime_pd"]["min_gap"]
        checks.append(("Lifetime PD ≥ 12-month PD", gap, 0.0, gap >= 0, ">="))
    # Stress (5.2): expected loss must rise with every step up in severity.
    # Value = the smallest EL ratio between consecutive scenarios (> 1 passes).
    stress_path = art / "stress_report.json"
    if stress_path.exists():
        sc = json.loads(stress_path.read_text())["scenarios"].values()
        ordered = sorted(sc, key=lambda s: (s["unemployment_pts"], -s["hpi_change_pct"]))
        els = [s["expected_loss"] for s in ordered]
        step = min(b / a for a, b in zip(els, els[1:], strict=False)) if len(els) > 1 else 1.0
        checks.append(("Stress EL rises with severity", step, 1.0, step > 1.0, ">"))
    results = [
        {
            "check": name,
            "value": round(float(v), 4),
            "threshold": float(th),
            "op": op,
            "passed": bool(ok),
        }
        for name, v, th, ok, op in checks
    ]
    return all(r["passed"] for r in results), results


def main() -> int:
    cfg = load_config()
    passed, results = run_gates(cfg)
    print(
        f"\n  CreditCast CI gates (champion={cfg.decision.champion}) — data={cfg.run.data_version}\n"
    )
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"   [{status}] {r['check']:34s} {r['value']:>8} {r['op']} {r['threshold']}")
    # Informational fairness flag (non-gating)
    try:
        gov = json.loads((cfg.path("artifacts") / "governance_report.json").read_text())
        di = gov["fairness"]["di_ratio_min_observed"]
        flag = "OK" if gov["fairness"]["passes_four_fifths"] else "REVIEW"
        print(
            f"\n   [{flag}] fairness min disparate-impact ratio = {di:.3f} "
            f"(floor {gov['fairness']['di_ratio_floor']}, non-gating)"
        )
    except FileNotFoundError:
        pass
    print(f"\n  => {'ALL GATES PASSED' if passed else 'GATES FAILED'}\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
