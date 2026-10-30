"use client";
// Fairness trade-off (ROADMAP 5.6): accuracy (Gini) against the lowest
// approval-rate ratio for each model variant, all at the same approval rate.
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ResponsiveContainer, LabelList, Cell,
} from "recharts";
import { api } from "@/lib/api";
import { CardTitle, ChartFrame, TableWrap, useFetch } from "@/components/ui";

const SHORT = {
  baseline: "Baseline", drop_dti: "No DTI", cap_fico: "Score cap",
  reweighing: "Reweighing", fairlearn_dp: "fairlearn",
};

export default function LdaTradeoff() {
  const { data } = useFetch(() => api.lda(), []);
  if (!data) return null;
  const points = Object.entries(data.variants).map(([k, v]) => ({
    key: k, name: SHORT[k], label: v.label, gini: v.gini, ratio: v.min_ratio, group: v.lowest_group,
  }));
  const chosen = data.variants[data.chosen];
  const base = data.variants.baseline;
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <CardTitle info="disparate_impact">Fairness vs accuracy: searching for a less discriminatory model</CardTitle>
      <p className="small muted" style={{ marginTop: -6 }}>
        Each point is a version of the model, all approving the same {Math.round(data.approval_share * 100)}% of applicants.
        Right is fairer (the lowest group&apos;s approval rate relative to White applicants), up is more accurate.
      </p>
      <ChartFrame summary={`Baseline: Gini ${base.gini.toFixed(3)}, lowest approval ratio ${base.min_ratio.toFixed(3)}. `
        + `Chosen, ${chosen.label}: Gini ${chosen.gini.toFixed(3)}, ratio ${chosen.min_ratio.toFixed(3)}.`}>
        <ResponsiveContainer width="100%" height={280}>
          <ScatterChart margin={{ left: 8, right: 24, top: 16, bottom: 8 }}>
            <CartesianGrid stroke="var(--border)" />
            <XAxis type="number" dataKey="ratio" name="Lowest approval ratio" stroke="var(--muted-2)"
              domain={[0.78, 0.9]} tickFormatter={(v) => v.toFixed(2)} />
            <YAxis type="number" dataKey="gini" name="Gini" stroke="var(--muted-2)"
              domain={[0.2, 0.5]} tickFormatter={(v) => v.toFixed(2)} />
            <Tooltip formatter={(v) => v.toFixed(3)} labelFormatter={() => ""}
              content={({ payload }) => payload?.[0] ? (
                <div className="card" style={{ padding: "8px 12px" }}>
                  <b>{payload[0].payload.label}</b>
                  <div className="small">Gini {payload[0].payload.gini.toFixed(3)} · ratio {payload[0].payload.ratio.toFixed(3)}</div>
                </div>) : null} />
            <ReferenceLine x={data.floor} stroke="var(--red)" strokeDasharray="4 4"
              label={{ value: "4/5ths rule", fill: "var(--red)", fontSize: 10, position: "insideTopLeft" }} />
            <Scatter data={points} isAnimationActive={false}>
              {points.map((p) => (
                <Cell key={p.key} fill={p.key === data.chosen ? "var(--green)" : "var(--series)"} />
              ))}
              <LabelList dataKey="name" position="top" fill="var(--muted)" fontSize={11} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </ChartFrame>
      <TableWrap>
        <table>
          <thead><tr><th>Version</th><th className="num">Gini</th><th className="num">Lowest approval ratio</th></tr></thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.key}>
                <td className="small">{p.label}{p.key === data.chosen && <b className="ok"> ✓ chosen</b>}</td>
                <td className="num">{p.gini.toFixed(3)}</td>
                <td className="num">{p.ratio.toFixed(3)} <span className="muted small">({p.group})</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableWrap>
      <p className="small muted" style={{ marginBottom: 0 }}>
        Chosen: the fairest version that loses at most {data.gini_tolerance} Gini. fairlearn&apos;s constrained training
        gets approvals closest to equal but loses most of its ability to rank risk, and it needs race during training,
        so it isn&apos;t chosen. Separate approval limits per group are never considered: they&apos;re illegal in lending.
        Study on a simple logistic model; the live model is a gradient-boosted tree.
      </p>
    </div>
  );
}
