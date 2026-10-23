"use client";
import { useEffect, useRef, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer, ReferenceLine, Tooltip,
} from "recharts";
import { api, pct, money } from "@/lib/api";
import { CATEGORY_LABELS, featureLabel } from "@/lib/labels";
import { PageHead, Stat, Band, InfoTip, SliderField, CardTitle } from "@/components/ui";
import { PrintButton } from "@/components/Print";
import DecisionLetter from "@/components/DecisionLetter";
import Compare, { MAX_PINS } from "@/components/Compare";

const PRESETS = {
  "Prime borrower": { fico: 790, dti: 22, ltv: 60, orig_interest_rate: 3.1, orig_upb: 250000, orig_loan_term: 360, occupancy_status: "P", loan_purpose: "P", property_type: "SF", first_time_homebuyer: "N", vintage: "2021-06" },
  "Marginal borrower": { fico: 690, dti: 38, ltv: 82, orig_interest_rate: 4.3, orig_upb: 300000, orig_loan_term: 360, occupancy_status: "P", loan_purpose: "N", property_type: "CO", first_time_homebuyer: "Y", vintage: "2021-06" },
  "High-risk borrower": { fico: 645, dti: 47, ltv: 94, orig_interest_rate: 5.6, orig_upb: 360000, orig_loan_term: 360, occupancy_status: "I", loan_purpose: "C", property_type: "MH", first_time_homebuyer: "Y", vintage: "2021-06" },
};

// Typical mortgage risk ranges, used only to colour the slider tracks.
const SLIDERS = [
  { key: "fico", min: 300, max: 850, step: 1, label: "Credit score (FICO)",
    zones: [{ to: 620, tone: "bad" }, { to: 700, tone: "warn" }, { to: 850, tone: "ok" }],
    hint: "Bureau credit score. Below 620 is subprime." },
  { key: "dti", min: 0, max: 70, step: 0.5, format: (v) => `${v}%`,
    zones: [{ to: 36, tone: "ok" }, { to: 43, tone: "warn" }, { to: 70, tone: "bad" }],
    hint: "Monthly debt payments ÷ monthly income. Above 43% is stretched." },
  { key: "ltv", min: 1, max: 125, step: 1, format: (v) => `${v}%`,
    zones: [{ to: 80, tone: "ok" }, { to: 95, tone: "warn" }, { to: 125, tone: "bad" }],
    hint: "Loan ÷ home value. Above 80% means a thin equity cushion." },
  { key: "orig_interest_rate", min: 0, max: 12, step: 0.05, format: (v) => `${v}%`,
    hint: "Note rate. Riskier borrowers are usually charged more." },
  { key: "orig_upb", min: 40000, max: 1200000, step: 5000, format: money,
    hint: "Original loan amount." },
];

const SELECTS = ["occupancy_status", "loan_purpose", "property_type", "first_time_homebuyer"];
const INTEGER_FIELDS = ["fico", "ltv", "orig_upb", "orig_loan_term"];
const GRADES = ["AAA", "AA", "A", "BBB", "BB", "B"];
// "Combined leverage (LTV × DTI)" -> "combined leverage (LTV × DTI)"
const lowerFirst = (s) => s.charAt(0).toLowerCase() + s.slice(1);

function isComplete(form) {
  return SLIDERS.every((s) => Number.isFinite(form[s.key]) && form[s.key] >= s.min && form[s.key] <= s.max);
}

export default function ScorePage() {
  const [preset, setPreset] = useState("Marginal borrower");
  const [form, setForm] = useState(PRESETS["Marginal borrower"]);
  const [res, setRes] = useState(null);
  const [scored, setScored] = useState(null);   // the exact inputs behind `res`
  const [whatif, setWhatif] = useState(null);   // paths to approval (6.2.2)
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const inflight = useRef(null);
  const [pins, setPins] = useState([]);         // compare applicants (6.2.3)
  const pinCount = useRef(0);

  // A pin snapshots the inputs that produced the shown result; the same
  // applicant can't be pinned twice.
  const key = scored && JSON.stringify(scored);
  const pinned = key && pins.some((p) => p.key === key);
  const pin = () => {
    if (!res || pinned || pins.length >= MAX_PINS) return;
    pinCount.current += 1;
    const label = Object.keys(PRESETS).find((n) => JSON.stringify(PRESETS[n]) === key)
      || `Applicant ${pinCount.current}`;
    setPins((ps) => [...ps, { id: pinCount.current, key, label, form: scored, res }]);
  };

  const set = (k, v) => { setPreset(null); setForm((f) => ({ ...f, [k]: v })); };

  // Live scoring: re-score ~0.4 s after the last change; a newer change
  // cancels the older request so results never arrive out of order.
  useEffect(() => {
    if (!isComplete(form)) return;
    const timer = setTimeout(async () => {
      inflight.current?.abort();
      const ctrl = new AbortController();
      inflight.current = ctrl;
      setBusy(true);
      try {
        const payload = { ...form };
        INTEGER_FIELDS.forEach((k) => (payload[k] = Math.round(Number(payload[k]))));
        const r = await api.score(payload, { signal: ctrl.signal });
        setRes(r);
        setScored(payload);
        setErr(null);
        // For a decline, also ask: what single change would get it approved?
        setWhatif(r.decision === "decline"
          ? await api.whatif(payload, { signal: ctrl.signal }).catch((e) =>
              e.name === "AbortError" ? null : { error: e.message })
          : null);
      } catch (e) {
        if (e.name !== "AbortError") setErr(e.message);
      } finally {
        if (inflight.current === ctrl) setBusy(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [form]);

  return (
    <>
      {/* On paper this page is the decision letter only (6.3.6). */}
      {res && <DecisionLetter res={res} form={form} whatif={whatif} />}
      <div className="screen-only">
      <PageHead title="Score an applicant"
        subtitle="Move the sliders and the decision updates instantly — probability of default, expected loss, and the reasons behind it." />

      <div className="grid cols-2" style={{ alignItems: "start" }}>
        <div className="card">
          <h3>Applicant</h3>
          <div className="chips" style={{ marginBottom: 16 }} role="group" aria-label="Example applicants">
            {Object.keys(PRESETS).map((p) => (
              <button key={p} type="button" className={`chip ${preset === p ? "active" : ""}`}
                aria-pressed={preset === p}
                onClick={() => { setPreset(p); setForm(PRESETS[p]); }}>{p}</button>
            ))}
          </div>

          <div data-tour="sliders" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {SLIDERS.map((s) => (
              <SliderField key={s.key} id={`f-${s.key}`} label={s.label || featureLabel(s.key)}
                value={form[s.key]} onChange={(v) => set(s.key, v)}
                min={s.min} max={s.max} step={s.step} zones={s.zones}
                format={s.format} hint={s.hint} />
            ))}
          </div>

          <div className="form-grid" style={{ marginTop: 18 }}>
            <label className="field">
              {featureLabel("orig_loan_term")}
              <select value={form.orig_loan_term} onChange={(e) => set("orig_loan_term", Number(e.target.value))}>
                {[180, 240, 360].map((t) => <option key={t} value={t}>{t / 12} years</option>)}
              </select>
            </label>
            {SELECTS.map((k) => (
              <label key={k} className="field">
                {featureLabel(k)}
                <select value={form[k]} onChange={(e) => set(k, e.target.value)}>
                  {Object.entries(CATEGORY_LABELS[k]).map(([code, text]) => (
                    <option key={code} value={code}>{text}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          {!isComplete(form) && (
            <p className="small warn" style={{ marginTop: 12 }}>Fill in every number within its range to score.</p>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }} aria-live="polite">
          {err && (
            <div className="card" style={{ borderColor: "var(--amber)" }} role="alert">
              <p className="small warn" style={{ margin: 0 }}>{err}</p>
            </div>
          )}
          {!res ? (
            <div className="card"><p className="muted">{busy ? "Scoring…" : "Adjust the applicant to see a decision."}</p></div>
          ) : (
            <Result res={res} busy={busy} whatif={whatif}
              pinState={pinned ? "pinned" : pins.length >= MAX_PINS ? "full" : busy ? "busy" : "ready"}
              onPin={pin}
              onApply={(app) => { setPreset(null); setForm({ ...form, ...app }); }} />
          )}
        </div>
      </div>

      <Compare pins={pins}
        onRemove={(id) => setPins((ps) => ps.filter((p) => p.id !== id))}
        onLoad={(p) => { setPreset(PRESETS[p.label] ? p.label : null); setForm(p.form); }}
        onClear={() => setPins([])} />
      </div>
    </>
  );
}

const PIN_LABELS = {
  ready: "⊕ Pin to compare", busy: "⊕ Pin to compare", pinned: "✓ Pinned", full: `Compare is full (${MAX_PINS})`,
};

function Result({ res, busy, whatif, pinState, onPin, onApply }) {
  const approved = res.decision === "approve";
  const reasons = res.reason_codes || [];
  const why = approved
    ? `Default risk ${pct(res.pd)} is within the ${pct(res.threshold)} approval limit.`
    : reasons.length
      ? `Main reasons: ${reasons.slice(0, 2).map((r) => lowerFirst(featureLabel(r.feature))).join(" and ")}.`
      : `Default risk ${pct(res.pd)} is above the ${pct(res.threshold)} approval limit.`;
  const drivers = (res.explanation || []).slice(0, 8).map((e) => ({
    name: featureLabel(e.feature), shap: e.shap,
  }));

  return (
    <>
      <div data-tour="decision" className="card" style={{ borderColor: approved ? "var(--green)" : "var(--red)" }}>
        <div className="decision">
          <div>
            <div className="small muted" style={{ textTransform: "uppercase", letterSpacing: ".6px" }}>
              Decision {busy && <span className="updating">· updating…</span>}
            </div>
            <div className={`verdict ${approved ? "ok" : "bad"}`}>
              <span aria-hidden="true">{approved ? "✓" : "✗"}</span>{approved ? "Approved" : "Declined"}
            </div>
            <div className="why">{why}</div>
          </div>
          <GradeScale grade={res.risk_band} />
        </div>
        <RiskMeter pd={res.pd} threshold={res.threshold} />
        <div className="chips" style={{ marginTop: 14 }}>
          <button type="button" className="chip" onClick={onPin} disabled={pinState !== "ready"}
            title={pinState === "full" ? "Unpin an applicant to add another" : undefined}>
            {PIN_LABELS[pinState]}
          </button>
          <PrintButton label="⤓ Download decision letter (PDF)"
            filename={`CreditCast decision ${res.request_id || ""}`.trim()} />
        </div>
      </div>

      {!approved && <WhatIf data={whatif} onApply={onApply} />}

      <div className="grid cols-3">
        <Stat label="Probability of default" info="pd" value={pct(res.pd)}
          tone={res.pd > res.threshold ? "bad" : "ok"} sub={`limit ${pct(res.threshold)}`} />
        <Stat label="Credit score" info="credit_score" value={Math.round(res.credit_score)}
          sub={`grade ${res.risk_band}`} />
        <Stat label="Expected loss" info="el" value={money(res.expected_loss)}
          sub={`${pct(res.lgd, 0)} loss if default · ${money(res.ead)} owed`} />
      </div>

      <div className="card">
        <CardTitle info="reason_codes">{approved ? "What helped and hurt" : "Why it was declined"}</CardTitle>
        {reasons.length > 0 ? (
          <ul className="reasons">{reasons.map((c) => <li key={c.rank}>{c.reason}</li>)}</ul>
        ) : (
          <p className="small muted" style={{ margin: 0 }}>
            No adverse factors to report — the application was approved.
          </p>
        )}
        <details className="more">
          <summary>Show detailed breakdown (SHAP)<InfoTip k="shap" /></summary>
          <p className="small muted">Red bars raised the default risk; green bars lowered it.</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={drivers} layout="vertical" margin={{ left: 10, right: 16 }}>
              <XAxis type="number" stroke="var(--muted-2)" />
              <YAxis type="category" dataKey="name" width={150} stroke="var(--muted-2)" tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => v.toFixed(4)} />
              <ReferenceLine x={0} stroke="var(--border-bright)" />
              <Bar dataKey="shap" radius={3}>
                {drivers.map((d, i) => <Cell key={i} fill={d.shap > 0 ? "var(--red)" : "var(--green)"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </details>
      </div>
    </>
  );
}

/** Smallest single changes that would turn this decline into an approval. */
function WhatIf({ data, onApply }) {
  return (
    <div className="card whatif">
      <h3>How this applicant could be approved</h3>
      {!data ? (
        <p className="small muted" style={{ margin: 0 }}>Looking for changes…</p>
      ) : data.error ? (
        <p className="small warn" style={{ margin: 0 }}>{data.error}</p>
      ) : data.options.length === 0 ? (
        <p className="small muted" style={{ margin: 0 }}>{data.message}</p>
      ) : (
        <>
          <p className="small muted" style={{ marginTop: 0 }}>
            Any <b>one</b> of these changes alone would bring default risk under the {pct(data.threshold)} limit:
          </p>
          <ul className="whatif-list">
            {data.options.map((o) => (
              <li key={o.feature}>
                <div>
                  <div className="whatif-lever">{o.lever}</div>
                  <div className="small">{o.text}</div>
                  <div className="small muted">default risk would be {pct(o.pd_after)}</div>
                </div>
                <button type="button" className="chip" onClick={() => onApply(o.applicant)}
                  aria-label={`Apply: ${o.text}`}>Apply</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** Horizontal PD meter, 0–20 %, with the approval limit marked. */
function RiskMeter({ pd, threshold }) {
  const scale = 0.2;
  const at = (v) => `${Math.min(100, (v / scale) * 100)}%`;
  return (
    <div style={{ marginTop: 16 }} aria-label={`Default risk ${pct(pd)}, approval limit ${pct(threshold)}`}>
      <div style={{ position: "relative", height: 10, borderRadius: 999,
        background: "linear-gradient(90deg, var(--green), var(--amber) 45%, var(--red))", opacity: .85 }}>
        <div title="approval limit" style={{ position: "absolute", left: at(threshold), top: -4, bottom: -4,
          width: 2, background: "var(--text)" }} />
        <div style={{ position: "absolute", left: at(pd), top: "50%", width: 16, height: 16,
          transform: "translate(-50%, -50%)", borderRadius: "50%", background: "var(--text)",
          border: "3px solid var(--bg)" }} />
      </div>
      <div className="small muted" style={{ display: "flex", justifyContent: "space-between", marginTop: 6 }}>
        <span>0%</span><span>approval limit {pct(threshold)}</span><span>20%+</span>
      </div>
    </div>
  );
}

function GradeScale({ grade }) {
  return (
    <div aria-label={`Risk grade ${grade}`}>
      <div className="small muted" style={{ marginBottom: 6, textAlign: "right" }}>
        Risk grade<InfoTip k="risk_band" />
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {GRADES.map((g) => (
          <span key={g} className={g === grade ? `band ${g}` : "band"}
            style={g === grade ? { outline: "1px solid currentColor" }
              : { color: "var(--muted-2)", background: "var(--panel-2)" }}>{g}</span>
        ))}
      </div>
    </div>
  );
}
