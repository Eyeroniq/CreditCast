"use client";
import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell,
} from "recharts";
import { api, pct, money, moneyShort, num } from "@/lib/api";
import { PageHead, Stat, useFetch, PageSkeleton, ErrorState, CardTitle } from "@/components/ui";
import LoanTable, { EMPTY_FILTERS } from "@/components/LoanTable";

const BAND_COLOR = { AAA: "var(--green)", AA: "var(--green)", A: "var(--green)", BBB: "var(--series)", BB: "var(--amber)", B: "var(--red)" };
const SAMPLE = 1000;   // API cap (config api.portfolio_max_rows)

export default function PortfolioPage() {
  const { data, error, loading, retry } = useFetch(() => api.portfolio(SAMPLE), []);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  if (loading) return (<><Head /><PageSkeleton stats={4} charts={2} table label="Loading portfolio" /></>);
  if (error) return (<><Head /><ErrorState error={error} onRetry={retry} /></>);

  const bandData = Object.entries(data.band_distribution).map(([k, v]) => ({
    band: k, count: v, el: data.el_by_band[k] || 0,
  }));
  const step = data.pd_histogram.length > 1 ? data.pd_histogram[1].x - data.pd_histogram[0].x : 0.01;
  const hist = data.pd_histogram.map((h) => ({ pd: (h.x * 100).toFixed(1), lo: h.x, hi: h.x + step, count: h.count }));

  // Clicking a chart filters the table below (6.2.4); clicking again clears it.
  const pickBand = (band) => setFilters((f) => ({ ...f, band: f.band === band ? "" : band }));
  const pickPd = (bin) => setFilters((f) => ({
    ...f, pdRange: f.pdRange && f.pdRange[0] === bin.lo ? null : [bin.lo, bin.hi],
  }));
  const dim = (on) => (on ? 1 : 0.35);
  const scrollToTable = () => document.getElementById("loan-table")?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <>
      <Head />
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <Stat label="Loans in the test book" info="oot" value={num(data.n_loans)} />
        <Stat label="Expected loss" info="el" value={moneyShort(data.portfolio_el)}
          sub={`${data.el_rate_bps.toFixed(0)} bps of the amount owed`} tone="warn" />
        <Stat label="Amount owed (EAD)" info="ead" value={moneyShort(data.total_ead)} />
        <Stat label="Approval rate" info="threshold" value={pct(data.approval_rate, 1)}
          sub={`average default risk ${pct(data.mean_pd)}`} />
      </div>

      <p className="small muted" style={{ margin: "0 0 10px" }}>
        Tip: click a bar to filter the loan table below; click it again to clear.
      </p>
      <div className="grid cols-2" style={{ marginBottom: 16 }} data-tour="charts">
        <div className="card">
          <CardTitle info="risk_band">Loans per risk grade</CardTitle>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={bandData} margin={{ left: 4, right: 8 }}>
              <XAxis dataKey="band" stroke="var(--muted-2)" />
              <YAxis stroke="var(--muted-2)" />
              <Tooltip formatter={(v) => [num(v), "loans"]} labelFormatter={(l) => `Grade ${l} — click to filter`} />
              <Bar isAnimationActive={false} dataKey="count" radius={4} cursor="pointer"
                onClick={(d) => { pickBand(d.band); scrollToTable(); }}>
                {bandData.map((d, i) => (
                  <Cell key={i} fill={BAND_COLOR[d.band] || "var(--series)"}
                    fillOpacity={dim(!filters.band || filters.band === d.band)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <CardTitle info="el">Expected loss per risk grade</CardTitle>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={bandData} margin={{ left: 14, right: 8 }}>
              <XAxis dataKey="band" stroke="var(--muted-2)" />
              <YAxis stroke="var(--muted-2)" tickFormatter={moneyShort} />
              <Tooltip formatter={(v) => [money(v), "expected loss"]} labelFormatter={(l) => `Grade ${l} — click to filter`} />
              <Bar isAnimationActive={false} dataKey="el" radius={4} cursor="pointer"
                onClick={(d) => { pickBand(d.band); scrollToTable(); }}>
                {bandData.map((d, i) => (
                  <Cell key={i} fill={BAND_COLOR[d.band] || "var(--series)"}
                    fillOpacity={dim(!filters.band || filters.band === d.band)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <CardTitle info="pd">How default risk is spread across the book</CardTitle>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={hist} margin={{ left: 4, right: 8 }}>
            <XAxis dataKey="pd" stroke="var(--muted-2)" tickFormatter={(v) => `${v}%`} interval={3} />
            <YAxis stroke="var(--muted-2)" />
            <Tooltip formatter={(v) => [num(v), "loans"]}
              labelFormatter={(l) => `Default risk ≈ ${l}% — click to filter`} />
            <Bar isAnimationActive={false} dataKey="count" radius={2} cursor="pointer"
              onClick={(d) => { pickPd(d); scrollToTable(); }}>
              {hist.map((h, i) => (
                <Cell key={i} fill="var(--series)"
                  fillOpacity={dim(!filters.pdRange || filters.pdRange[0] === h.lo)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card" id="loan-table" data-tour="loan-table">
        <CardTitle info="el">Loans with the highest expected loss</CardTitle>
        <p className="small muted" style={{ marginTop: -6 }}>
          The {num(data.sample.length)} loans with the largest expected loss in the book of {num(data.n_loans)}.
          Search, sort any column, filter, and export what you see.
        </p>
        <LoanTable rows={data.sample} filters={filters} onFilters={setFilters} />
      </div>
    </>
  );
}

const Head = () => (
  <PageHead title="Portfolio risk"
    subtitle="The whole book at a glance: how much loss to expect, which risk grades it sits in, and which loans matter most." />
);
