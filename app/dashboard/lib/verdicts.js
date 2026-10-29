// One-sentence page verdicts (ROADMAP 6.1.3). Each rule reads its limits from
// the API response it summarises, so the banner can never disagree with the
// gates in config.yaml. Returns { tone: "ok" | "warn" | "bad" | "info", text }.
import { pct, moneyShort } from "@/lib/api";
import { featureLabel } from "@/lib/labels";

const lowerFirst = (s) => s.charAt(0).toLowerCase() + s.slice(1);
const list = (xs) => (xs.length <= 1 ? xs.join("")
  : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

export function validationVerdict(v) {
  const t = v.thresholds;
  const m = v.models[v.champion];
  const gini = m.discrimination.gini, ks = m.discrimination.ks;
  const cal = m.calibration.max_band_error;
  const fails = [];
  if (gini < t.gini_min) fails.push(`Gini ${gini.toFixed(2)} is below the ${t.gini_min} minimum`);
  if (ks < t.ks_min) fails.push(`KS ${ks.toFixed(2)} is below the ${t.ks_min} minimum`);
  if (cal > t.calibration_max_band_error)
    fails.push(`worst calibration error ${pct(cal, 1)} is above the ${pct(t.calibration_max_band_error, 0)} limit`);
  if (fails.length) {
    const text = fails.join("; ");
    return { tone: "bad", text: `Model quality needs review: ${text}.` };
  }
  return {
    tone: "ok",
    text: `Model quality is good: Gini ${gini.toFixed(2)} (min ${t.gini_min}), worst calibration error `
      + `${pct(cal, 1)} (max ${pct(t.calibration_max_band_error, 0)}).`,
  };
}

/** `mon` is /api/monitoring, `v` is /api/validation (for thresholds and the per-vintage shift). */
export function monitoringVerdict(mon, v) {
  const t = v.thresholds;
  const name = (s) => (s === "score" ? "the credit score" : lowerFirst(featureLabel(s)));
  const alerts = mon.alerts || [];
  if (alerts.length) {
    const unstable = alerts.some((a) => a.status === "unstable");
    const n = alerts.length;
    return {
      tone: unstable ? "bad" : "warn",
      text: `${n} signal${n > 1 ? "s" : ""} drifting: ${list(alerts.map((a) => name(a.signal)))} `
        + `${n > 1 ? "have" : "has"} changed since training.`,
    };
  }
  const worst = v.stability.max_score_psi;
  if (worst > t.psi_watch) {
    const at = v.stability.score_psi_by_vintage.reduce((a, b) => (b.psi > a.psi ? b : a));
    return {
      tone: worst > t.psi_unstable ? "bad" : "warn",
      text: `Scores shifted in the ${at.vintage} vintage: PSI ${worst.toFixed(2)} is above the ${t.psi_watch} watch level.`,
    };
  }
  return {
    tone: "ok",
    text: `No drift: the score and all ${mon.feature_csi.length} inputs match training `
      + `(largest shift PSI ${worst.toFixed(2)}, watch level ${t.psi_watch}).`,
  };
}

export function governanceVerdict(g) {
  const f = g.fairness;
  const low = f.groups.reduce((a, b) => (b.disparate_impact < a.disparate_impact ? b : a));
  const ratio = f.di_ratio_min_observed.toFixed(3);   // 0.7986 must not read as "0.80"
  if (!f.passes_four_fifths) {
    return {
      tone: "warn",
      text: `Fairness review needed: ${low.group} applicants are approved at ${ratio}× the rate of `
        + `${f.privileged_group} applicants (rule: at least ${f.di_ratio_floor}).`,
    };
  }
  return {
    tone: "ok",
    text: `Fairness check passed: the lowest approval ratio is ${ratio} (${low.group}; rule: at least ${f.di_ratio_floor}).`,
  };
}

export function portfolioVerdict(p) {
  return {
    tone: "info",
    text: `${pct(p.approval_rate, 1)} of loans would be approved; expected loss is ${moneyShort(p.portfolio_el)}, `
      + `${pct(p.portfolio_el / p.total_ead)} of the ${moneyShort(p.total_ead)} lent.`,
  };
}

/** The configured worst case, in one sentence (5.2 / 6.2.7). */
export function stressVerdict(report) {
  const sc = Object.values(report.scenarios);
  const base = report.scenarios.baseline;
  const worst = sc.reduce((a, b) => (b.expected_loss > a.expected_loss ? b : a));
  const sign = (v) => (v > 0 ? `+${v}` : `${v}`);
  return {
    tone: "info",
    text: `In the ${worst.label.toLowerCase()} scenario (unemployment ${sign(worst.unemployment_pts)} pts, house prices `
      + `${sign(worst.hpi_change_pct)}%), expected loss rises from ${base.el_bps.toFixed(0)} to `
      + `${worst.el_bps.toFixed(0)} bps of the amount lent and approvals fall from `
      + `${pct(base.approval_rate, 0)} to ${pct(worst.approval_rate, 0)}.`,
  };
}

/** `ready` is null while loading, then true/false from /api/agent/team. */
export function copilotVerdict(ready) {
  if (ready === null) return null;
  return ready
    ? { tone: "ok", text: "Copilot is online: ask about any page and the agents answer from the same live reports." }
    : { tone: "warn", text: "Copilot is offline: the server has no LLM key yet, so questions can't be answered. Every other page works." };
}
