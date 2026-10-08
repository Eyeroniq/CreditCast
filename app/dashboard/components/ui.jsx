"use client";
import { useEffect, useId, useState } from "react";
import { GLOSSARY } from "@/lib/glossary";

/** ⓘ explanation for a term (ROADMAP 6.1.2). Hover or keyboard-focus shows
 *  it; tap toggles it on touch screens. `k` is a key of lib/glossary.js. */
export function InfoTip({ k, text }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const g = GLOSSARY[k];
  const content = text || g?.short;
  if (!content) return null;
  return (
    <span className={`infotip ${open ? "open" : ""}`}>
      <button type="button" className="infotip-btn" aria-describedby={id}
        aria-label={`What is ${g ? g.term : "this"}?`}
        onClick={(e) => { e.preventDefault(); setOpen((o) => !o); }}
        onBlur={() => setOpen(false)}>i</button>
      <span role="tooltip" id={id} className="infotip-pop">{content}</span>
    </span>
  );
}

export function Stat({ label, value, sub, tone, info }) {
  return (
    <div className="card stat">
      <div className="label">{label}{info && <InfoTip k={info} />}</div>
      <div className={`value ${tone || ""}`}>{value}</div>
      {sub != null && <div className="sub">{sub}</div>}
    </div>
  );
}

export function Pill({ status, children }) {
  const cls = status === true || status === "stable" || status === "PASS" ? "ok"
    : status === "watch" ? "warn"
    : status === false || status === "unstable" || status === "REVIEW" ? "bad"
    : "neutral";
  return <span className={`pill ${cls}`}>{children}</span>;
}

export function Band({ grade }) {
  return <span className={`band ${grade}`}>{grade}</span>;
}

/** Card heading with an optional ⓘ. */
export function CardTitle({ children, info }) {
  return <h3>{children}{info && <InfoTip k={info} />}</h3>;
}

/** Tables scroll sideways inside their card on narrow screens. */
export function TableWrap({ children }) {
  return <div className="table-wrap">{children}</div>;
}

/** Slider + exact number box (ROADMAP 6.2.1). `zones` colours the track by
 *  risk: [{ to, tone: "ok" | "warn" | "bad" }] in ascending order. */
export function SliderField({ id, label, info, value, onChange, min, max, step = 1,
                              zones = [], format = (v) => v, hint }) {
  const pct = (v) => ((v - min) / (max - min)) * 100;
  const colour = { ok: "var(--green)", warn: "var(--amber)", bad: "var(--red)" };
  let from = 0;
  const stops = zones.map((z) => {
    const to = Math.min(100, Math.max(0, pct(z.to)));
    const seg = `${colour[z.tone]} ${from}% ${to}%`;
    from = to;
    return seg;
  });
  const track = stops.length ? `linear-gradient(90deg, ${stops.join(", ")})` : undefined;
  const num = Number(value);
  return (
    <div className="slider-field">
      <div className="slider-head">
        <label htmlFor={id}>{label}{info && <InfoTip k={info} />}</label>
        <input type="number" className="slider-num" aria-label={`${label} value`}
          min={min} max={max} step={step} value={value}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />
      </div>
      <input id={id} type="range" min={min} max={max} step={step}
        value={Number.isFinite(num) ? num : min}
        aria-valuetext={format(num)}
        style={track ? { "--track": track } : undefined}
        onChange={(e) => onChange(Number(e.target.value))} />
      {hint && <div className="slider-hint">{hint}</div>}
    </div>
  );
}

export function PageHead({ title, subtitle }) {
  return (
    <div className="page-head">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
}

// data-fetching hook with loading / error states
export function useFetch(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let alive = true;
    setState({ data: null, error: null, loading: true });
    fn()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState({ data: null, error: error.message, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function Loading({ what = "data" }) {
  return <div className="loading">loading {what}…</div>;
}

export function ApiError({ error }) {
  return (
    <div className="card" style={{ borderColor: "var(--red)" }}>
      <h3 className="bad">Cannot reach scoring API</h3>
      <p className="small muted">{error}</p>
      <p className="small mono">
        Start it with:&nbsp; uvicorn app.api.main:app --port 8001
        <br />(after running: python -m creditcast.cli all)
      </p>
    </div>
  );
}
