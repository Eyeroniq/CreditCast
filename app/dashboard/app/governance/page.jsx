"use client";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell, ReferenceLine,
} from "recharts";
import { api, pct } from "@/lib/api";
import { PageHead, Stat, Pill, VerdictBanner, Band, useFetch, PageSkeleton, ErrorState, CardTitle, TableWrap, InfoTip } from "@/components/ui";
import { governanceVerdict } from "@/lib/verdicts";
import { PrintButton, PrintHeader } from "@/components/Print";
import { featureLabel } from "@/lib/labels";
import ThresholdExplorer from "@/components/ThresholdExplorer";
import LdaTradeoff from "@/components/LdaTradeoff";

export default function GovernancePage() {
  const { data, error, loading, retry } = useFetch(() => api.governance(), []);
  if (loading) return (<><Head /><PageSkeleton stats={4} charts={2} table label="Loading fairness report" /></>);
  if (error) return (<><Head /><ErrorState error={error} onRetry={retry} /></>);

  const f = data.fairness;
  const shap = data.shap_global.slice(0, 8).map((s) => ({ feature: featureLabel(s.feature), imp: s.mean_abs_shap }));
  const groups = [...f.groups].sort((a, b) => b.disparate_impact - a.disparate_impact);
  const ex = data.adverse_action_example;

  return (
    <>
      <PrintHeader title="Fairness and explanations report" stamp={data.stamp} />
      <Head />
      <VerdictBanner verdict={governanceVerdict(data)} />
      <div className="page-actions"><PrintButton label="⤓ Download report (PDF)" filename="CreditCast fairness and explanations report" /></div>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Stat label="Champion model"
          value={(data.champion_model || "challenger").split(" ")[0].replace(/^./, (c) => c.toUpperCase())}
          sub={(data.champion_model || "").replace(/^\S+\s*\(?|\)$/g, "") || "LightGBM · calibrated"} />
        <Stat label="Approval rate" info="threshold" value={pct(data.decision.approval_rate, 1)}
          sub={`PD threshold ${pct(data.decision.threshold)}${data.decision.threshold_source ? " · set on calibration data" : ""}`} />
        <Stat label="Lowest approval ratio" info="disparate_impact" value={f.di_ratio_min_observed.toFixed(3)}
          tone={f.passes_four_fifths ? "ok" : "bad"} sub={`4/5ths floor ${f.di_ratio_floor}`} />
        <div className="card stat">
          <div className="label">Fairness (4/5ths rule)<InfoTip k="disparate_impact" /></div>
          <div style={{ marginTop: 10 }}>
            <Pill status={f.passes_four_fifths ? "PASS" : "REVIEW"}>
              {f.passes_four_fifths ? "pass" : "review"}
            </Pill>
          </div>
          <div className="sub">max EO diff {f.max_equal_opportunity_diff.toFixed(3)}</div>
        </div>
      </div>

      <ThresholdExplorer />
      <LdaTradeoff />

      <div className="grid cols-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <CardTitle info="shap">What drives risk most, across all loans</CardTitle>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={shap} layout="vertical" margin={{ left: 10, right: 12 }}>
              <XAxis type="number" stroke="var(--muted-2)" />
              <YAxis type="category" dataKey="feature" width={150} stroke="var(--muted-2)" tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => v.toFixed(4)} />
              <Bar isAnimationActive={false} dataKey="imp" fill="var(--series)" radius={3} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <CardTitle info="disparate_impact">Approval ratio by group (vs {f.privileged_group})</CardTitle>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={groups} margin={{ left: 4, right: 12 }}>
              <XAxis dataKey="group" stroke="var(--muted-2)" />
              <YAxis stroke="var(--muted-2)" domain={[0, 1.2]} />
              <Tooltip formatter={(v) => v.toFixed(3)} />
              <ReferenceLine y={f.di_ratio_floor} stroke="var(--red)" strokeDasharray="4 4"
                label={{ value: "4/5ths floor", fill: "var(--red)", fontSize: 10, position: "insideTopRight" }} />
              <Bar isAnimationActive={false} dataKey="disparate_impact" radius={3}>
                {groups.map((g, i) => (
                  <Cell key={i} fill={g.disparate_impact >= f.di_ratio_floor ? "var(--green)" : "var(--red)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <CardTitle info="equal_opportunity">Fairness by group</CardTitle>
        <TableWrap>
        <table>
          <thead><tr>
            <th>Group</th><th className="num">N</th><th className="num">Approval</th>
            <th className="num">Default rate</th><th className="num">Disparate impact</th>
            <th className="num">Equal-opportunity gap</th>
          </tr></thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.group}>
                <td>{g.group}</td>
                <td className="num">{g.n.toLocaleString()}</td>
                <td className="num">{pct(g.approval_rate, 1)}</td>
                <td className="num">{pct(g.default_rate, 2)}</td>
                <td className="num"><span className={g.disparate_impact >= f.di_ratio_floor ? "ok" : "bad"}>{g.disparate_impact.toFixed(3)}</span></td>
                <td className="num">{g.equal_opportunity_diff >= 0 ? "+" : ""}{g.equal_opportunity_diff.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </TableWrap>
        <p className="small muted" style={{ marginTop: 10 }}>
          The model excludes race, yet neutral features (credit score, DTI) proxy historical disparity, producing
          disparate impact. Mitigation: feature review, fairness-constrained training, monitoring — not group-specific
          thresholds (illegal in lending). Surfacing this is an EU AI Act high-risk expectation.
        </p>
      </div>

      {ex && (
        <div className="card">
          <CardTitle info="reason_codes">Example letter to a declined applicant</CardTitle>
          <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
            <span className="mono small muted">loan {ex.loan_id}</span>
            <span>PD <b className="mono">{pct(ex.pd)}</b></span>
            <span>score <b className="mono">{ex.credit_score.toFixed(0)}</b></span>
            <Band grade={ex.band} />
            <Pill status={false}>decline</Pill>
          </div>
          <pre className="mono small" style={{ whiteSpace: "pre-wrap", background: "var(--panel-2)", padding: 14, borderRadius: 8, border: "1px solid var(--border)" }}>{ex.letter}</pre>
        </div>
      )}
    </>
  );
}

const Head = () => (
  <PageHead title="Fairness & explanations"
    subtitle="Why the model decides what it does, whether outcomes are fair across groups, and what declined applicants are told." />
);
