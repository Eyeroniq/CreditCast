"use client";
// Stress-test playground (ROADMAP 6.2.7, on the 5.2 engine): shock the economy
// and watch expected loss, approvals and PD by risk band move against baseline.
import { useEffect, useRef, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { api, pct, moneyShort } from "@/lib/api";
import {
  PageHead, Stat, VerdictBanner, useFetch, PageSkeleton, ErrorState, CardTitle, SliderField,
  ChartFrame,
} from "@/components/ui";
import { stressVerdict } from "@/lib/verdicts";

const SLIDERS = [
  { key: "unemployment_pts", label: "Unemployment change", min: -2, max: 10, step: 0.5,
    format: (v) => `${v > 0 ? "+" : ""}${v} pts`,
    zones: [{ to: 1, tone: "ok" }, { to: 4, tone: "warn" }, { to: 10, tone: "bad" }],
    hint: "Added to each loan's local unemployment rate and to its 12-month change." },
  { key: "hpi_change_pct", label: "House-price change", min: -40, max: 20, step: 1,
    format: (v) => `${v > 0 ? "+" : ""}${v}%`,
    zones: [{ to: -20, tone: "bad" }, { to: -5, tone: "warn" }, { to: 20, tone: "ok" }],
    hint: "Moves local house prices; a fall also raises loan-to-value, so losses on default grow." },
];

const delta = (v, base) => (base ? `${v >= base ? "+" : ""}${((v / base - 1) * 100).toFixed(0)}% vs baseline` : "");

export default function StressPage() {
  const { data, error, loading, retry } = useFetch(() => api.stressScenarios(), []);
  const [shock, setShock] = useState({ unemployment_pts: 3, hpi_change_pct: -10 });
  const [preset, setPreset] = useState("adverse");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const inflight = useRef(null);

  // Re-run ~0.3 s after the last change; a newer change cancels the older call.
  useEffect(() => {
    if (!data) return;
    const ok = SLIDERS.every((s) => Number.isFinite(shock[s.key]) && shock[s.key] >= s.min && shock[s.key] <= s.max);
    if (!ok) return;
    const t = setTimeout(async () => {
      inflight.current?.abort();
      const ctrl = new AbortController();
      inflight.current = ctrl;
      setBusy(true);
      try {
        setRes(await api.stressRun(shock, { signal: ctrl.signal }));
        setErr(null);
      } catch (e) {
        if (e.name !== "AbortError") setErr(e.message);
      } finally {
        if (inflight.current === ctrl) setBusy(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [shock, data]);

  if (loading) return (<><Head /><PageSkeleton stats={4} charts={1} label="Loading stress scenarios" /></>);
  if (error) return (<><Head /><ErrorState error={error} onRetry={retry} /></>);

  const scenarios = data.scenarios;
  const base = scenarios.baseline;
  const choosePreset = (name) => {
    setPreset(name);
    setShock({ unemployment_pts: scenarios[name].unemployment_pts, hpi_change_pct: scenarios[name].hpi_change_pct });
  };
  const set = (k, v) => { setPreset(null); setShock((s) => ({ ...s, [k]: v })); };
  const cur = res || scenarios[preset] || null;
  const bands = base.pd_by_band.map((b, i) => ({
    band: b.band, baseline: b.mean_pd, scenario: cur?.pd_by_band[i]?.mean_pd ?? null,
  }));
  const worst = bands[bands.length - 1];

  return (
    <>
      <Head />
      <VerdictBanner verdict={stressVerdict(data)} />

      <div className="grid cols-2 items-start">
        <div className="card">
          <h3>Scenario</h3>
          <div className="chips mb-16" role="group" aria-label="Preset scenarios">
            {Object.entries(scenarios).map(([name, s]) => (
              <button key={name} type="button" className={`chip ${preset === name ? "active" : ""}`}
                aria-pressed={preset === name} onClick={() => choosePreset(name)}>{s.label}</button>
            ))}
          </div>
          <div className="stack">
            {SLIDERS.map((s) => (
              <SliderField key={s.key} id={`s-${s.key}`} label={s.label} value={shock[s.key]}
                onChange={(v) => set(s.key, v)} min={s.min} max={s.max} step={s.step}
                zones={s.zones} format={s.format} hint={s.hint} />
            ))}
          </div>
          <details className="more">
            <summary>How the stress test works</summary>
            <p className="small muted">
              The {base.n_loans.toLocaleString()} out-of-time loans are re-scored with the shocked economy. Because the
              model was trained in calm years, a separate sensitivity fitted on every vintage (including 2020) adds
              the extra risk a downturn brings: +{data.satellite.used.unemp_rate.toFixed(3)} log-odds per point of
              unemployment, +{data.satellite.used.unemp_chg_12m.toFixed(3)} per point of rise, and{" "}
              {data.satellite.used.hpi_chg_12m.toFixed(3)} per % of house-price growth. Loss on default comes from the
              loss model re-run at the new loan-to-value.
            </p>
          </details>
        </div>

        <div className="stack" aria-live="polite">
          {err && <div className="card" role="alert"><p className="small warn m-0">{err}</p></div>}
          <div className="small muted">{busy ? <span className="updating">Updating…</span> : " "}</div>
          {cur && (
            <div className="grid cols-2">
              <Stat label="Expected loss" info="el" value={moneyShort(cur.expected_loss)}
                tone={cur.expected_loss > base.expected_loss * 1.5 ? "bad" : cur.expected_loss > base.expected_loss ? "warn" : "ok"}
                sub={`${delta(cur.expected_loss, base.expected_loss)} · baseline ${moneyShort(base.expected_loss)}`} />
              <Stat label="Loss rate" value={`${cur.el_bps.toFixed(0)} bps`}
                sub={`baseline ${base.el_bps.toFixed(0)} bps of the amount lent`} />
              <Stat label="Average default risk" info="pd" value={pct(cur.mean_pd)}
                sub={`baseline ${pct(base.mean_pd)}`} />
              <Stat label="Loss if default" info="lgd" value={pct(cur.mean_lgd, 1)}
                sub={`baseline ${pct(base.mean_lgd, 1)} · falls in house prices raise it`} />
              <Stat label="Capital required (Basel)" info="capital" value={moneyShort(cur.capital)}
                sub={`${delta(cur.capital, base.capital)} · ${pct(cur.risk_weight, 0)} risk weight`} />
              <Stat label="Would be approved" info="threshold" value={pct(cur.approval_rate, 0)}
                tone={cur.approval_rate < base.approval_rate - 0.2 ? "bad" : cur.approval_rate < base.approval_rate ? "warn" : "ok"}
                sub={`baseline ${pct(base.approval_rate, 0)} at the same limit`} />
            </div>
          )}
        </div>
      </div>

      <div className="card mt-16">
        <CardTitle info="risk_band">Default risk by risk grade: baseline vs scenario</CardTitle>
        <ChartFrame summary={`Average default risk per grade. In the riskiest grade (${worst.band}) it moves from `
          + `${pct(worst.baseline)} at baseline to ${worst.scenario == null ? "…" : pct(worst.scenario)} in this scenario.`}>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={bands} margin={{ left: 4, right: 8, top: 8 }}>
              <XAxis dataKey="band" stroke="var(--muted-2)" />
              <YAxis stroke="var(--muted-2)" tickFormatter={(v) => pct(v, 0)} />
              <Tooltip formatter={(v) => pct(v)} />
              <Legend />
              <Bar isAnimationActive={false} dataKey="baseline" name="Baseline" fill="var(--muted-2)" radius={3} />
              <Bar isAnimationActive={false} dataKey="scenario" name="Scenario" fill="var(--red)" radius={3} />
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>
        <p className="small muted mb-0">
          Grades come from the scorecard, which doesn&apos;t use economic inputs, so loans keep their grade; the
          scenario changes how likely each grade is to default.
        </p>
      </div>
    </>
  );
}

const Head = () => (
  <PageHead title="Stress test"
    subtitle="Push the economy into a downturn and see what happens to losses, approvals and default risk across the book." />
);
