"use client";
// Compare applicants side by side (ROADMAP 6.2.3). The Score page pins a
// snapshot of the form and its result; up to MAX_PINS sit in this card.
// Where pinned applicants differ, the best value in a row is green and the
// worst red, so the deciding differences stand out at a glance.
import { pct, money } from "@/lib/api";
import { featureLabel } from "@/lib/labels";
import { Band, CardTitle, TableWrap } from "@/components/ui";

export const MAX_PINS = 3;
const GRADES = ["AAA", "AA", "A", "BBB", "BB", "B"];

// better: "low" | "high" picks which end of the row is green.
export const ROWS = [
  { label: "Decision", get: (p) => (p.res.decision === "approve" ? 0 : 1), better: "low",
    show: (p) => (p.res.decision === "approve" ? "✓ Approved" : "✗ Declined") },
  { label: "Default risk", get: (p) => p.res.pd, better: "low", show: (p) => pct(p.res.pd), num: true },
  { label: "Model score", get: (p) => Math.round(p.res.credit_score), better: "high",
    show: (p) => Math.round(p.res.credit_score), num: true },
  { label: "Risk grade", get: (p) => GRADES.indexOf(p.res.risk_band), better: "low",
    show: (p) => <Band grade={p.res.risk_band} /> },
  { label: "Expected loss", get: (p) => p.res.expected_loss, better: "low",
    show: (p) => money(p.res.expected_loss), num: true },
  { label: "Credit score (FICO)", get: (p) => p.form.fico, better: "high", show: (p) => p.form.fico, num: true },
  { label: featureLabel("dti"), get: (p) => p.form.dti, better: "low", show: (p) => `${p.form.dti}%`, num: true },
  { label: featureLabel("ltv"), get: (p) => p.form.ltv, better: "low", show: (p) => `${p.form.ltv}%`, num: true },
  { label: featureLabel("orig_interest_rate"), get: (p) => p.form.orig_interest_rate, better: "low",
    show: (p) => `${p.form.orig_interest_rate}%`, num: true },
  { label: featureLabel("orig_upb"), get: (p) => p.form.orig_upb, show: (p) => money(p.form.orig_upb), num: true },
];

/** "best" / "worst" / "" for each pin in a row; empty when all values match. */
export function rowTones(row, pins) {
  const vals = pins.map(row.get);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  if (pins.length < 2 || lo === hi || !row.better) return vals.map(() => "");
  const [best, worst] = row.better === "low" ? [lo, hi] : [hi, lo];
  return vals.map((v) => (v === best ? "best" : v === worst ? "worst" : ""));
}

export default function Compare({ pins, onRemove, onLoad, onClear }) {
  if (!pins.length) return null;
  return (
    <div className="card compare" data-tour="compare">
      <div className="compare-head">
        <CardTitle>Compare applicants</CardTitle>
        <button type="button" className="chip" onClick={onClear}>Clear all</button>
      </div>
      {pins.length < 2 && (
        <p className="small muted" style={{ marginTop: 0 }}>
          Change the applicant and pin again to see them side by side (up to {MAX_PINS}).
        </p>
      )}
      <TableWrap>
        <table>
          <thead>
            <tr>
              <th scope="col"><span className="sr-only">Measure</span></th>
              {pins.map((p) => (
                <th key={p.id} scope="col" className="num">
                  <div className="compare-name">{p.label}</div>
                  <div className="compare-actions">
                    <button type="button" className="link-btn" onClick={() => onLoad(p)}
                      aria-label={`Load ${p.label} into the form`}>Load</button>
                    <button type="button" className="link-btn" onClick={() => onRemove(p.id)}
                      aria-label={`Unpin ${p.label}`}>Unpin</button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const tones = rowTones(row, pins);
              return (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  {pins.map((p, i) => (
                    <td key={p.id} className={`num ${tones[i]}`}>{row.show(p)}</td>
                  ))}
                </tr>
              );
            })}
            <tr>
              <th scope="row">Top reasons</th>
              {pins.map((p) => (
                <td key={p.id} className="compare-reasons">
                  {(p.res.reason_codes || []).length ? (
                    <ul>{p.res.reason_codes.slice(0, 3).map((c) => <li key={c.rank}>{c.reason}</li>)}</ul>
                  ) : <span className="muted">None — approved</span>}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </TableWrap>
    </div>
  );
}
