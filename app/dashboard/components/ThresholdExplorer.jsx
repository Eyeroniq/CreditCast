"use client";
// Approval-limit explorer (ROADMAP 6.2.5): drag the cut-off and watch approval
// rate, expected loss and fairness move together. The whole curve is
// precomputed by the governance build, so scrubbing needs no API calls.
import { useMemo, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip, ReferenceLine, Legend,
} from "recharts";
import { api, pct, moneyShort } from "@/lib/api";
import { useFetch, CardTitle, InfoTip, Pill, Skeleton, ErrorState } from "@/components/ui";

const nearest = (points, thr) =>
  points.reduce((best, p, i) =>
    Math.abs(p.threshold - thr) < Math.abs(points[best].threshold - thr) ? i : best, 0);

export default function ThresholdExplorer() {
  const { data, error, loading, retry } = useFetch(() => api.thresholdCurve(), []);
  const [idx, setIdx] = useState(null);

  const chart = useMemo(() => (data?.points || []).map((p) => ({
    thr: +(p.threshold * 100).toFixed(2),
    approval: p.approval_rate, fairness: p.di_min,
  })), [data]);

  if (loading) return (
    <div className="card mb-16">
      <Skeleton width="40%" height={11} /><Skeleton height={180} className="mt-16" />
    </div>);
  // The rest of the page still works without the explorer.
  if (error) return <div className="mb-16"><ErrorState error={error} onRetry={retry} /></div>;

  const pts = data.points;
  const policyIdx = nearest(pts, data.policy_threshold);
  const i = idx ?? policyIdx;
  const cur = pts[i], policy = pts[policyIdx];
  const fair = cur.di_min >= data.di_floor;
  const delta = (a, b, fmt) => {
    const d = a - b;
    if (Math.abs(d) < 1e-9) return "same as policy";
    return `${d > 0 ? "+" : "−"}${fmt(Math.abs(d))} vs policy`;
  };

  return (
    <div className="card mb-16" data-tour="threshold">
      <CardTitle info="threshold">Try a different approval limit</CardTitle>
      <p className="small muted mt-n6">
        Approve every application whose default risk is at or below the limit. A higher limit
        approves more people — and takes on more expected loss. See how fairness moves too.
      </p>

      <div className="slider-field m-0 mt-14 mb-18">
        <div className="slider-head">
          <label htmlFor="thr-slider">Approval limit (maximum default risk)</label>
          <span className="mono big-num">{pct(cur.threshold)}</span>
        </div>
        <input id="thr-slider" type="range" min={0} max={pts.length - 1} step={1} value={i}
          aria-valuetext={`${pct(cur.threshold)} approval limit`}
          onChange={(e) => setIdx(Number(e.target.value))} />
        <div className="slider-hint spread gap-8 wrap">
          <span>{pct(pts[0].threshold, 1)} — strict</span>
          <button type="button" className="chip" onClick={() => setIdx(null)} disabled={i === policyIdx}>
            Reset to policy ({pct(data.policy_threshold)})
          </button>
          <span>lenient — {pct(pts[pts.length - 1].threshold, 0)}</span>
        </div>
      </div>

      <div className="grid cols-4 gap-12">
        <Readout label="Approval rate" value={pct(cur.approval_rate, 1)}
          sub={delta(cur.approval_rate, policy.approval_rate, (v) => `${(v * 100).toFixed(1)} pts`)} />
        <Readout label="Defaults among approved" info="pd" value={pct(cur.approved_default_rate, 2)}
          sub={`${pct(cur.defaults_approved_share, 0)} of all defaults approved`} />
        <Readout label="Expected loss (approved)" info="el" value={moneyShort(cur.expected_loss_approved)}
          sub={`${cur.el_bps_approved.toFixed(0)} bps · ${delta(cur.expected_loss_approved, policy.expected_loss_approved, moneyShort)}`} />
        <Readout label="Lowest approval ratio" info="disparate_impact"
          value={<span className={fair ? "ok" : "bad"}>{cur.di_min.toFixed(3)}</span>}
          sub={<Pill status={fair ? "PASS" : "REVIEW"}>{fair ? "✓ meets 4/5ths" : "✗ below 0.80"}</Pill>} />
      </div>

      <div className="mt-16">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chart} margin={{ left: 0, right: 12, top: 8 }}>
            <XAxis dataKey="thr" type="number" domain={["dataMin", "dataMax"]} stroke="var(--muted-2)"
              tickFormatter={(v) => `${v}%`} />
            <YAxis stroke="var(--muted-2)" domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} width={44} />
            <Tooltip formatter={(v, n) => [n === "fairness" ? v.toFixed(3) : pct(v, 1), n === "fairness" ? "lowest approval ratio" : "approval rate"]}
              labelFormatter={(l) => `limit ${l}%`} />
            <Legend formatter={(v) => (v === "fairness" ? "lowest approval ratio (fairness)" : "approval rate")} />
            <ReferenceLine y={data.di_floor} stroke="var(--red)" strokeDasharray="4 4" />
            <ReferenceLine x={+(policy.threshold * 100).toFixed(2)} stroke="var(--muted)" strokeDasharray="2 4"
              label={{ value: "policy", fill: "var(--muted)", fontSize: 10, position: "top" }} />
            <ReferenceLine x={+(cur.threshold * 100).toFixed(2)} stroke="var(--accent)" strokeWidth={2} />
            <Line type="monotone" dataKey="approval" stroke="var(--series)" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line type="monotone" dataKey="fairness" stroke="var(--green)" dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        <p className="small muted m-0 mt-6">
          The policy limit ({pct(data.policy_threshold)}) comes from the cost ratio, not from these results;
          the dashed red line is the 0.80 fairness floor. Remediating fairness with different limits per group is
          illegal in lending — this view is for understanding the trade-off.
        </p>
      </div>
    </div>
  );
}

function Readout({ label, info, value, sub }) {
  return (
    <div className="card stat inset">
      <div className="label">{label}{info && <InfoTip k={info} />}</div>
      <div className="value value-sm">{value}</div>
      <div className="sub">{sub}</div>
    </div>
  );
}
