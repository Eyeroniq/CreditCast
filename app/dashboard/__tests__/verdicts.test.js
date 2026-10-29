// Page verdicts (6.1.3): limits come from the report, and the tone follows them.
import { describe, expect, it } from "vitest";
import {
  copilotVerdict, governanceVerdict, monitoringVerdict, portfolioVerdict, stressVerdict, validationVerdict,
} from "@/lib/verdicts";

const THRESHOLDS = { gini_min: 0.35, ks_min: 0.25, calibration_max_band_error: 0.03, psi_watch: 0.1, psi_unstable: 0.25 };
const validation = (gini, cal, maxPsi = 0.03) => ({
  champion: "challenger", thresholds: THRESHOLDS,
  models: { challenger: { discrimination: { gini, ks: 0.33 }, calibration: { max_band_error: cal } } },
  stability: { max_score_psi: maxPsi, score_psi_by_vintage: [{ vintage: "2021-03", psi: maxPsi }] },
});

describe("validationVerdict", () => {
  it("passes a model inside every limit and quotes the limits", () => {
    const v = validationVerdict(validation(0.43, 0.018));
    expect(v.tone).toBe("ok");
    expect(v.text).toContain("Gini 0.43 (min 0.35)");
    expect(v.text).toContain("1.8% (max 3%)");
  });
  it("fails on low Gini and poor calibration, naming both", () => {
    const v = validationVerdict(validation(0.3, 0.05));
    expect(v.tone).toBe("bad");
    expect(v.text).toMatch(/Gini 0.30 is below the 0.35 minimum.*calibration error 5.0% is above/);
  });
});

describe("monitoringVerdict", () => {
  const mon = (alerts) => ({ alerts, feature_csi: new Array(13).fill({}) });
  it("is healthy with no alerts and small shifts", () => {
    expect(monitoringVerdict(mon([]), validation(0.43, 0.01)).text).toMatch(/^No drift: the score and all 13 inputs/);
  });
  it("names drifting inputs in plain words", () => {
    const v = monitoringVerdict(mon([{ signal: "dti", status: "watch" }, { signal: "orig_upb", status: "watch" }]),
      validation(0.43, 0.01));
    expect(v.tone).toBe("warn");
    expect(v.text).toBe("2 signals drifting: debt-to-income and loan amount have changed since training.");
  });
  it("is red when any signal is unstable", () => {
    expect(monitoringVerdict(mon([{ signal: "score", status: "unstable" }]), validation(0.43, 0.01)).tone).toBe("bad");
  });
  it("flags a vintage whose score shift passes the watch level", () => {
    const v = monitoringVerdict(mon([]), validation(0.43, 0.01, 0.14));
    expect(v.tone).toBe("warn");
    expect(v.text).toContain("2021-03");
  });
});

describe("governanceVerdict", () => {
  const gov = (low, passes) => ({ fairness: {
    privileged_group: "White", di_ratio_floor: 0.8, di_ratio_min_observed: low, passes_four_fifths: passes,
    groups: [{ group: "White", disparate_impact: 1 }, { group: "Black", disparate_impact: low }],
  } });
  it("asks for review below the four-fifths floor without rounding up to it", () => {
    const v = governanceVerdict(gov(0.7986, false));
    expect(v.tone).toBe("warn");
    expect(v.text).toContain("Black applicants are approved at 0.799×");
  });
  it("passes above the floor", () => {
    expect(governanceVerdict(gov(0.86, true)).tone).toBe("ok");
  });
});

describe("portfolio and copilot verdicts", () => {
  it("summarises approvals and loss rate", () => {
    const v = portfolioVerdict({ approval_rate: 0.807, portfolio_el: 37.2e6, total_ead: 3.05e9 });
    expect(v).toEqual({ tone: "info", text: "80.7% of loans would be approved; expected loss is $37.20M, 1.22% of the $3.05B lent." });
  });
  it("waits for the team check, then reports online or offline", () => {
    expect(copilotVerdict(null)).toBeNull();
    expect(copilotVerdict(true).tone).toBe("ok");
    expect(copilotVerdict(false).tone).toBe("warn");
  });
});

describe("stressVerdict", () => {
  it("describes the worst configured scenario against baseline", () => {
    const sc = (label, u, h, bps, appr, el) => ({ label, unemployment_pts: u, hpi_change_pct: h, el_bps: bps, approval_rate: appr, expected_loss: el });
    const v = stressVerdict({ scenarios: {
      baseline: sc("Baseline", 0, 0, 133, 0.82, 40), adverse: sc("Adverse", 3, -10, 227, 0.62, 69),
      severely_adverse: sc("Severely adverse", 6, -25, 390, 0.27, 119),
    } });
    expect(v.tone).toBe("info");
    expect(v.text).toBe("In the severely adverse scenario (unemployment +6 pts, house prices -25%), expected loss "
      + "rises from 133 to 390 bps of the amount lent and approvals fall from 82% to 27%.");
  });
});
