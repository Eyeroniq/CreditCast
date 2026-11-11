"use client";
// Searchable, sortable, filterable loan table with CSV export (ROADMAP 6.2.6).
// Works client-side on the portfolio sample (≤ 1,000 rows), so every filter,
// sort and page change is instant. Filters can also be set from the charts
// above it (6.2.4) through the `filters` / `onFilters` props.
import { useMemo, useState } from "react";
import { pct, money, moneyShort } from "@/lib/api";
import { DECISION_LABELS } from "@/lib/labels";
import { Band, InfoTip, TableWrap } from "@/components/ui";

const GRADES = ["AAA", "AA", "A", "BBB", "BB", "B"];

const COLUMNS = [
  { key: "loan_id", label: "Loan", num: false, fmt: (v) => v },
  { key: "vintage", label: "Originated", num: false, fmt: (v) => v },
  { key: "pd_champion", label: "Default risk", info: "pd", num: true, fmt: (v) => pct(v) },
  { key: "pd_lifetime", label: "Lifetime risk", info: "lifetime_pd", num: true,
    fmt: (v) => (v == null ? "—" : pct(v, 1)), sortValue: (v) => (v == null ? -1 : v) },
  { key: "credit_score", label: "Score", info: "credit_score", num: true, fmt: (v) => v.toFixed(0) },
  { key: "risk_band", label: "Grade", info: "risk_band", num: false,
    fmt: (v) => <Band grade={v} />, sortValue: (v) => GRADES.indexOf(v) },
  { key: "lgd_hat", label: "Loss if default", info: "lgd", num: true, fmt: (v) => pct(v) },
  { key: "ead", label: "Owed", info: "ead", num: true, fmt: (v) => moneyShort(v) },
  { key: "expected_loss", label: "Expected loss", info: "el", num: true, fmt: (v) => money(v) },
  { key: "decision", label: "Decision", num: false,
    fmt: (v) => <span className={v === "approve" ? "ok" : "bad"}>{v === "approve" ? "✓ " : "✗ "}{DECISION_LABELS[v] || v}</span> },
  { key: "ifrs9_stage", label: "IFRS 9 stage", info: "ifrs9", num: false,
    fmt: (v) => (v == null ? <span className="muted">Off book</span> : <span className={v === 3 ? "bad" : v === 2 ? "warn" : ""}>Stage {v}</span>),
    sortValue: (v) => (v == null ? 0 : v) },
  { key: "default_12m", label: "Actually defaulted?", num: false,
    fmt: (v) => (v ? <span className="bad">Yes</span> : <span className="muted">No</span>) },
];

export const EMPTY_FILTERS = { q: "", band: "", vintage: "", decision: "", defaulted: "", pdRange: null };

export function activeFilterChips(f) {
  const chips = [];
  if (f.q) chips.push(["q", `Loan ID contains “${f.q}”`]);
  if (f.band) chips.push(["band", `Grade ${f.band}`]);
  if (f.vintage) chips.push(["vintage", `Originated ${f.vintage}`]);
  if (f.decision) chips.push(["decision", DECISION_LABELS[f.decision]]);
  if (f.defaulted) chips.push(["defaulted", f.defaulted === "1" ? "Defaulted" : "Did not default"]);
  if (f.pdRange) chips.push(["pdRange", `Default risk ${pct(f.pdRange[0], 1)}–${pct(f.pdRange[1], 1)}`]);
  return chips;
}

function applyFilters(rows, f) {
  const q = f.q.trim();
  return rows.filter((r) =>
    (!q || String(r.loan_id).includes(q)) &&
    (!f.band || r.risk_band === f.band) &&
    (!f.vintage || r.vintage === f.vintage) &&
    (!f.decision || r.decision === f.decision) &&
    (!f.defaulted || String(r.default_12m) === f.defaulted) &&
    (!f.pdRange || (r.pd_champion >= f.pdRange[0] && r.pd_champion < f.pdRange[1])));
}

function toCsv(rows) {
  const keys = COLUMNS.map((c) => c.key);
  const esc = (v) => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  return [COLUMNS.map((c) => esc(c.label)).join(","),
          ...rows.map((r) => keys.map((k) => esc(r[k] ?? "")).join(","))].join("\n");
}

function download(rows) {
  const blob = new Blob([toCsv(rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: "creditcast-loans.csv" });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function LoanTable({ rows, filters, onFilters }) {
  const [sort, setSort] = useState({ key: "expected_loss", dir: "desc" });
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(0);
  const set = (patch) => { onFilters({ ...filters, ...patch }); setPage(0); };

  const vintages = useMemo(() => [...new Set(rows.map((r) => r.vintage))].sort(), [rows]);
  const filtered = useMemo(() => applyFilters(rows, filters), [rows, filters]);
  const sorted = useMemo(() => {
    const col = COLUMNS.find((c) => c.key === sort.key);
    const val = (r) => (col.sortValue ? col.sortValue(r[col.key]) : r[col.key]);
    const out = [...filtered].sort((a, b) => (val(a) < val(b) ? -1 : val(a) > val(b) ? 1 : 0));
    return sort.dir === "desc" ? out.reverse() : out;
  }, [filtered, sort]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const cur = Math.min(page, pages - 1);
  const shown = sorted.slice(cur * pageSize, (cur + 1) * pageSize);
  const toggleSort = (key) => setSort((s) => ({ key, dir: s.key === key && s.dir === "desc" ? "asc" : "desc" }));
  const chips = activeFilterChips(filters);

  return (
    <div>
      <div className="table-tools">
        <input type="search" placeholder="Search loan ID…" aria-label="Search by loan ID"
          value={filters.q} onChange={(e) => set({ q: e.target.value })} />
        <select aria-label="Filter by grade" value={filters.band} onChange={(e) => set({ band: e.target.value })}>
          <option value="">All grades</option>
          {GRADES.map((g) => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <select aria-label="Filter by origination month" value={filters.vintage} onChange={(e) => set({ vintage: e.target.value })}>
          <option value="">All months</option>
          {vintages.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        <select aria-label="Filter by decision" value={filters.decision} onChange={(e) => set({ decision: e.target.value })}>
          <option value="">All decisions</option>
          <option value="approve">Approved</option>
          <option value="decline">Declined</option>
        </select>
        <select aria-label="Filter by actual outcome" value={filters.defaulted} onChange={(e) => set({ defaulted: e.target.value })}>
          <option value="">Any outcome</option>
          <option value="1">Defaulted</option>
          <option value="0">Did not default</option>
        </select>
        <button type="button" className="chip" onClick={() => download(sorted)} disabled={!sorted.length}>
          ⤓ Export CSV ({sorted.length.toLocaleString()})
        </button>
      </div>

      {chips.length > 0 && (
        <div className="chips m-0 mt-10 mb-10" aria-label="Active filters">
          {chips.map(([key, text]) => (
            <button key={key} type="button" className="chip active" aria-label={`Remove filter: ${text}`}
              onClick={() => set({ [key]: key === "pdRange" ? null : "" })}>{text} ✕</button>
          ))}
          <button type="button" className="chip" onClick={() => { onFilters(EMPTY_FILTERS); setPage(0); }}>Clear all</button>
        </div>
      )}

      <p className="small muted m-0 mt-8 mb-8" aria-live="polite">
        Showing {shown.length ? cur * pageSize + 1 : 0}–{cur * pageSize + shown.length} of{" "}
        {sorted.length.toLocaleString()} loans{sorted.length !== rows.length ? ` (filtered from ${rows.length.toLocaleString()})` : ""}.
      </p>

      <TableWrap>
        <table className="loan-table">
          <thead><tr>
            {COLUMNS.map((c) => {
              const active = sort.key === c.key;
              return (
                <th key={c.key} className={c.num ? "num" : ""}
                  aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}>
                  <button type="button" className="th-sort" onClick={() => toggleSort(c.key)}>
                    {c.label}<span aria-hidden="true">{active ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}</span>
                  </button>
                  {c.info && <InfoTip k={c.info} />}
                </th>
              );
            })}
          </tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.loan_id}>
                {COLUMNS.map((c) => (
                  <td key={c.key} className={c.num ? "num" : c.key === "loan_id" || c.key === "vintage" ? "mono" : ""}>
                    {c.fmt(r[c.key])}
                  </td>
                ))}
              </tr>
            ))}
            {!shown.length && (
              <tr><td colSpan={COLUMNS.length} className="muted empty-cell">
                No loans match these filters.
              </td></tr>
            )}
          </tbody>
        </table>
      </TableWrap>

      <div className="pager">
        <label className="small muted">Rows per page{" "}
          <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}>
            {[25, 50, 100].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <div className="row gap-6 items-center">
          <button type="button" className="chip" onClick={() => setPage(cur - 1)} disabled={cur === 0}>‹ Prev</button>
          <span className="small muted">Page {cur + 1} of {pages}</span>
          <button type="button" className="chip" onClick={() => setPage(cur + 1)} disabled={cur >= pages - 1}>Next ›</button>
        </div>
      </div>
    </div>
  );
}
