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

const VERDICT_ICONS = { ok: "✓", warn: "⚠", bad: "✗", info: "ℹ" };

/** One-sentence page verdict (6.1.3): icon + text, never colour alone. */
export function VerdictBanner({ verdict }) {
  if (!verdict) return null;
  return (
    <p className={`verdict-banner ${verdict.tone}`} role="status">
      <span className="verdict-icon" aria-hidden="true">{VERDICT_ICONS[verdict.tone]}</span>
      <span>{verdict.text}</span>
    </p>
  );
}

export function Band({ grade }) {
  return <span className={`band ${grade}`}>{grade}</span>;
}

/** Card heading with an optional ⓘ. */
export function CardTitle({ children, info }) {
  return <h3>{children}{info && <InfoTip k={info} />}</h3>;
}

/** A chart with a one-sentence text equivalent (6.3.4). Screen readers get the
 *  summary; the SVG internals (hundreds of unlabeled shapes) are hidden. */
export function ChartFrame({ summary, children }) {
  return (
    <figure className="chart-frame">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden="true">{children}</div>
    </figure>
  );
}

/** Tables scroll sideways inside their card on narrow screens; tabIndex lets
 *  keyboard users focus the region and scroll it with the arrow keys. */
export function TableWrap({ children }) {
  return <div className="table-wrap" tabIndex={0}>{children}</div>;
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

// Small mono "eyebrow" shown above each page title.
const EYEBROWS = {
  "Score an applicant": "Live decisioning",
  "Portfolio risk": "Out-of-time book",
  "Stress test": "Scenario analysis",
  "Model quality": "Validation",
  "Stability & drift": "Monitoring",
  "Fairness & explanations": "Governance",
  "Risk Copilot": "AI agent team",
  "Glossary": "Plain language",
};

/** Hero page heading: eyebrow pill, display title with the brand's mint dot,
 *  and a ruled subtitle. The dot is decorative (not part of the heading name). */
export function PageHead({ title, subtitle, eyebrow }) {
  const kicker = eyebrow || EYEBROWS[title];
  return (
    <div className="page-head">
      {kicker && <div className="eyebrow"><span className="dot" aria-hidden="true" />{kicker}</div>}
      <h1>{title}<span className="title-dot" aria-hidden="true" /></h1>
      {subtitle && <p className="lede"><span className="rule" aria-hidden="true" />{subtitle}</p>}
    </div>
  );
}

// data-fetching hook with loading / error states and a retry (6.3.3)
export function useFetch(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let alive = true;
    setState({ data: null, error: null, loading: true });
    fn()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState({ data: null, error, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);
  return { ...state, retry: () => setAttempt((a) => a + 1) };
}

/** Grey placeholder blocks shaped like the page that is loading. */
export function Skeleton({ height = 14, width = "100%", style }) {
  return <div className="skeleton" style={{ height, width, ...style }} aria-hidden="true" />;
}

export function PageSkeleton({ stats = 4, charts = 2, table = false, label = "Loading" }) {
  return (
    <div role="status" aria-live="polite" aria-label={label}>
      <span className="sr-only">{label}…</span>
      <div className={`grid cols-${Math.min(stats, 4)}`} style={{ marginBottom: 16 }}>
        {Array.from({ length: stats }, (_, i) => (
          <div key={i} className="card">
            <Skeleton width="55%" height={11} />
            <Skeleton width="40%" height={26} style={{ marginTop: 12 }} />
          </div>
        ))}
      </div>
      {charts > 0 && (
        <div className={`grid cols-${Math.min(charts, 2)}`} style={{ marginBottom: 16 }}>
          {Array.from({ length: charts }, (_, i) => (
            <div key={i} className="card">
              <Skeleton width="45%" height={11} />
              <Skeleton height={200} style={{ marginTop: 16 }} />
            </div>
          ))}
        </div>
      )}
      {table && (
        <div className="card">
          <Skeleton width="35%" height={11} />
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} height={18} style={{ marginTop: 12 }} />)}
        </div>
      )}
    </div>
  );
}

// Kept for small inline waits.
export function Loading({ what = "data" }) {
  return <div className="loading" role="status">Loading {what}…</div>;
}

const ERROR_TITLES = {
  offline: "Can't reach CreditCast",
  missing: "Not available yet",
  busy: "Slow down a moment",
  server: "Something went wrong on our side",
  unavailable: "Not switched on",
  auth: "Access key needed",
  invalid: "Some values aren't valid",
};

/** Friendly error card with a Retry button (6.3.3). Accepts an ApiError, an
 *  Error, or a string. Technical details stay folded away. */
export function ErrorState({ error, onRetry }) {
  const kind = error?.kind || "error";
  const message = typeof error === "string" ? error : error?.message;
  const tech = [error?.status ? `HTTP ${error.status}` : null, error?.requestId && `request ${error.requestId}`,
                error?.detail && error.detail !== message ? error.detail : null].filter(Boolean);
  return (
    <div className="card error-state" role="alert">
      <h3 className={kind === "busy" || kind === "missing" ? "warn" : "bad"}>
        {ERROR_TITLES[kind] || "Couldn't load this page"}
      </h3>
      <p style={{ margin: "0 0 12px" }}>{message || "Something went wrong."}</p>
      {kind === "missing" && (
        <p className="small muted" style={{ marginTop: -4 }}>
          The model reports are produced by the training pipeline; once it has run, this page fills in.
        </p>
      )}
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        {onRetry && <button type="button" className="primary" onClick={onRetry}>Try again</button>}
        <a href="/" className="small muted">Go to the start page</a>
      </div>
      {tech.length > 0 && (
        <details className="more">
          <summary>Technical details</summary>
          <p className="small mono muted" style={{ whiteSpace: "pre-wrap" }}>{tech.join(" · ")}</p>
        </details>
      )}
    </div>
  );
}

// Backwards-compatible name used by older pages.
export const ApiError = ErrorState;
