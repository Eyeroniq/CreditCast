"use client";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell, ReferenceLine,
} from "recharts";
import { api } from "@/lib/api";
import { PageHead, Stat, Pill, useFetch, PageSkeleton, ErrorState, CardTitle, TableWrap, InfoTip } from "@/components/ui";
import { featureLabel } from "@/lib/labels";

const psiColor = (s) => (s === "stable" ? "var(--green)" : s === "watch" ? "var(--amber)" : "var(--red)");

export default function MonitoringPage() {
  const v = useFetch(() => api.validation(), []);
  const m = useFetch(() => api.monitoring(), []);
  if (v.loading || m.loading) return (<><Head /><PageSkeleton stats={4} charts={1} table label="Loading stability metrics" /></>);
  if (v.error) return (<><Head /><ErrorState error={v.error} onRetry={v.retry} /></>);
  if (m.error) return (<><Head /><ErrorState error={m.error} onRetry={m.retry} /></>);

  const t = v.data.thresholds;
  const psiByVintage = v.data.stability.score_psi_by_vintage.map((r) => ({
    vintage: r.vintage, psi: r.psi, status: r.status,
  }));
  const csi = v.data.stability.feature_csi.map((r) => ({ feature: r.feature, csi: r.csi, status: r.status }));
  const mon = m.data;

  return (
    <>
      <Head />
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Stat label="Largest score shift (PSI)" info="psi" value={v.data.stability.max_score_psi.toFixed(4)}
          tone={v.data.stability.max_score_psi <= t.psi_watch ? "ok" : v.data.stability.max_score_psi <= t.psi_unstable ? "warn" : "bad"}
          sub={`watch ${t.psi_watch} · unstable ${t.psi_unstable}`} />
        <Stat label="Largest input shift (CSI)" info="csi" value={v.data.stability.max_feature_csi.toFixed(4)}
          tone={v.data.stability.max_feature_csi <= t.psi_watch ? "ok" : "warn"} />
        <Stat label="Latest batch shift (PSI)" info="psi" value={mon.score_psi?.toFixed(4) ?? "—"}
          tone={mon.score_status === "stable" ? "ok" : mon.score_status === "watch" ? "warn" : "bad"}
          sub={`vs training baseline`} />
        <div className="card stat">
          <div className="label">Drift monitor<InfoTip k="drift" /></div>
          <div style={{ marginTop: 10 }}>
            <Pill status={mon.healthy}>{mon.healthy ? "healthy" : `${mon.alerts.length} alert(s)`}</Pill>
          </div>
          <div className="sub">{mon.n_batch.toLocaleString()} loans monitored</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <CardTitle info="psi">Score shift by origination month</CardTitle>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={psiByVintage} margin={{ left: 4, right: 8 }}>
            <XAxis dataKey="vintage" stroke="var(--muted-2)" interval={2} angle={-30} textAnchor="end" height={50} />
            <YAxis stroke="var(--muted-2)" />
            <Tooltip formatter={(val) => val.toFixed(4)} />
            <ReferenceLine y={t.psi_watch} stroke="var(--amber)" strokeDasharray="4 4" label={{ value: "watch", fill: "var(--amber)", fontSize: 10, position: "right" }} />
            <ReferenceLine y={t.psi_unstable} stroke="var(--red)" strokeDasharray="4 4" label={{ value: "unstable", fill: "var(--red)", fontSize: 10, position: "right" }} />
            <Bar isAnimationActive={false} dataKey="psi" radius={3}>
              {psiByVintage.map((d, i) => <Cell key={i} fill={psiColor(d.status)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <CardTitle info="csi">Which inputs shifted since training</CardTitle>
          <TableWrap>
          <table>
            <thead><tr><th>Feature</th><th className="num">CSI</th><th>Status</th></tr></thead>
            <tbody>
              {csi.slice(0, 10).map((r) => (
                <tr key={r.feature}>
                  <td className="small">{featureLabel(r.feature)}</td>
                  <td className="num">{r.csi.toFixed(4)}</td>
                  <td><Pill status={r.status}>{r.status}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
          </TableWrap>
        </div>
        <div className="card">
          <CardTitle info="drift">Drift alerts</CardTitle>
          {mon.alerts.length === 0 ? (
            <p className="ok small">No drift alerts — all signals within stable thresholds. The model is healthy on the monitored batch.</p>
          ) : (
            <table>
              <thead><tr><th>Signal</th><th className="num">PSI</th><th>Status</th></tr></thead>
              <tbody>
                {mon.alerts.map((a, i) => (
                  <tr key={i}><td className="small">{a.signal === "score" ? "Credit score" : featureLabel(a.signal)}</td>
                    <td className="num">{a.psi}</td><td><Pill status={a.status}>{a.status}</Pill></td></tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="small muted" style={{ marginTop: 12 }}>
            PSI/CSI re-computed against the training-time baseline. Thresholds: &lt; {t.psi_watch} stable,
            {t.psi_watch}–{t.psi_unstable} watch, &gt; {t.psi_unstable} unstable. Runs on a schedule (GitHub Actions cron).
          </p>
        </div>
      </div>
    </>
  );
}

const Head = () => (
  <PageHead title="Stability & drift"
    subtitle="Do today's borrowers still look like the ones the model learned from? Shifts here mean the model may need review." />
);
