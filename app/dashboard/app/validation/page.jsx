"use client";
import {
  LineChart, Line, ScatterChart, Scatter, XAxis, YAxis, ResponsiveContainer,
  Tooltip, ReferenceLine, Legend, CartesianGrid,
} from "recharts";
import { api, pct } from "@/lib/api";
import { PageHead, Stat, Pill, VerdictBanner, useFetch, PageSkeleton, ErrorState, CardTitle, TableWrap, InfoTip, ChartFrame } from "@/components/ui";
import { validationVerdict } from "@/lib/verdicts";
import { PrintButton, PrintHeader } from "@/components/Print";

export default function ValidationPage() {
  const { data, error, loading, retry } = useFetch(() => api.validation(), []);
  if (loading) return (<><Head /><PageSkeleton stats={4} charts={2} label="Loading model quality report" /></>);
  if (error) return (<><Head /><ErrorState error={error} onRetry={retry} /></>);

  const t = data.thresholds;
  const sc = data.models.scorecard, ch = data.models.challenger;
  const b = data.benchmark;

  // reliability curve (challenger) — predicted vs observed, with diagonal
  const rel = ch.calibration.reliability.map((r) => ({ predicted: r.predicted, observed: r.observed }));
  const maxRel = Math.max(...rel.flatMap((r) => [r.predicted, r.observed]), 0.05);
  const worstRel = rel.reduce((a, r) => (Math.abs(r.observed - r.predicted) > Math.abs(a.observed - a.predicted) ? r : a));
  // gains capture curve (challenger)
  const gains = ch.discrimination.gains.map((g) => ({
    band: g.band, capture: g.cum_capture_rate, lift: g.lift, defaultRate: g.default_rate,
  }));

  const Metric = ({ label, info, sc, ch, fmt = (x) => x.toFixed(4), pass }) => (
    <tr>
      <td>{label}{info && <InfoTip k={info} />}</td>
      <td className="num">{fmt(sc)}</td>
      <td className="num">{fmt(ch)}</td>
      <td>{pass && <Pill status={pass(ch)}>{pass(ch) ? "pass" : "review"}</Pill>}</td>
    </tr>
  );

  return (
    <>
      <PrintHeader title="Model quality report" stamp={data.stamp} />
      <Head />
      <VerdictBanner verdict={validationVerdict(data)} />
      <div className="page-actions"><PrintButton label="⤓ Download report (PDF)" filename="CreditCast model quality report" /></div>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Stat label="Gini (on unseen loans)" info="gini" value={ch.discrimination.gini.toFixed(4)}
          tone={ch.discrimination.gini >= t.gini_min ? "ok" : "bad"} sub={`min ${t.gini_min}`} />
        <Stat label="KS statistic" info="ks" value={ch.discrimination.ks.toFixed(4)}
          tone={ch.discrimination.ks >= t.ks_min ? "ok" : "bad"} sub={`min ${t.ks_min}`} />
        <Stat label="Calibration error (ECE)" info="ece" value={ch.calibration.ece.toFixed(4)} sub="lower is better" />
        <Stat label="Test loans" info="oot" value={data.n_oot.toLocaleString()}
          sub={`default rate ${pct(data.oot_default_rate)}`} />
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <CardTitle info="scorecard_vs_challenger">Simple scorecard vs machine-learning challenger</CardTitle>
        <div className="grid cols-3" style={{ gap: 12, marginBottom: 6 }}>
          <Stat label="Scorecard Gini" value={b.scorecard_gini.toFixed(4)} />
          <Stat label="Challenger Gini" value={b.challenger_gini.toFixed(4)} />
          <Stat label="Gini gap" value={`${b.gini_gap >= 0 ? "+" : ""}${b.gini_gap.toFixed(4)}`}
            sub={`${b.gini_gap_pct >= 0 ? "+" : ""}${b.gini_gap_pct.toFixed(1)}%`} />
        </div>
        <p className="small muted" style={{ marginTop: 4 }}>{b.verdict}</p>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <CardTitle info="oot">Accuracy and calibration on unseen loans</CardTitle>
        <TableWrap>
        <table>
          <thead><tr><th>Metric</th><th className="num">Scorecard</th><th className="num">Challenger</th><th>Gate</th></tr></thead>
          <tbody>
            <Metric label="Gini" info="gini" sc={sc.discrimination.gini} ch={ch.discrimination.gini}
              pass={(x) => x >= t.gini_min} />
            <Metric label="AUC" info="auc" sc={sc.discrimination.auc} ch={ch.discrimination.auc} />
            <Metric label="KS" info="ks" sc={sc.discrimination.ks} ch={ch.discrimination.ks}
              pass={(x) => x >= t.ks_min} />
            <Metric label="Calibration: worst band error" info="calibration" sc={sc.calibration.max_band_error}
              ch={ch.calibration.max_band_error} pass={(x) => x <= t.calibration_max_band_error} />
            <Metric label="ECE" info="ece" sc={sc.calibration.ece} ch={ch.calibration.ece} />
            <Metric label="Hosmer–Lemeshow p (informational)" info="hosmer_lemeshow" sc={sc.calibration.hosmer_lemeshow.p_value}
              ch={ch.calibration.hosmer_lemeshow.p_value} />
          </tbody>
        </table>
        </TableWrap>
        <p className="small muted" style={{ marginTop: 8 }}>
          Calibration is gated on the economically meaningful max band error / ECE; with ~{(data.n_oot/1000).toFixed(0)}k
          loans the Hosmer–Lemeshow test over-rejects on trivially small miscalibration, so it is shown as informational.
        </p>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <CardTitle info="calibration">Predicted vs actual default rate</CardTitle>
          <ChartFrame summary={`${rel.length} score bands plotted as predicted against actual default rate. `
            + `Largest gap: predicted ${pct(worstRel.predicted)}, actual ${pct(worstRel.observed)}.`}>
          <ResponsiveContainer width="100%" height={260}>
            <ScatterChart margin={{ left: 8, right: 12, top: 8 }}>
              <CartesianGrid stroke="var(--border)" />
              <XAxis type="number" dataKey="predicted" name="predicted" stroke="var(--muted-2)"
                domain={[0, maxRel]} tickFormatter={(v) => pct(v, 0)} />
              <YAxis type="number" dataKey="observed" name="observed" stroke="var(--muted-2)"
                domain={[0, maxRel]} tickFormatter={(v) => pct(v, 0)} />
              <Tooltip formatter={(v) => pct(v)} />
              <ReferenceLine segment={[{ x: 0, y: 0 }, { x: maxRel, y: maxRel }]} stroke="var(--border-bright)" strokeDasharray="4 4" />
              <Scatter isAnimationActive={false} data={rel} fill="var(--series)" />
            </ScatterChart>
          </ResponsiveContainer>
          </ChartFrame>
        </div>
        <div className="card">
          <CardTitle info="gains">Defaults caught, riskiest loans first</CardTitle>
          <ChartFrame summary={`Share of defaults caught when loans are ranked riskiest first: `
            + `${pct(gains[0].capture, 0)} in the riskiest tenth, ${pct(gains[2].capture, 0)} in the riskiest three tenths.`}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={gains} margin={{ left: 8, right: 12, top: 8 }}>
              <CartesianGrid stroke="var(--border)" />
              <XAxis dataKey="band" stroke="var(--muted-2)" label={{ value: "risk decile", position: "insideBottom", offset: -2, fill: "var(--muted-2)", fontSize: 11 }} />
              <YAxis stroke="var(--muted-2)" tickFormatter={(v) => pct(v, 0)} />
              <Tooltip formatter={(v) => pct(v)} />
              <Line isAnimationActive={false} type="monotone" dataKey="capture" stroke="var(--green)" strokeWidth={2} dot={false}
                name="cumulative defaults captured" />
            </LineChart>
          </ResponsiveContainer>
          </ChartFrame>
        </div>
      </div>
    </>
  );
}

const Head = () => (
  <PageHead title="Model quality"
    subtitle="How accurate the model is on newer loans it never saw — and whether its percentages can be trusted." />
);
