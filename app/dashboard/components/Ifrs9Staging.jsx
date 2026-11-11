"use client";
// IFRS 9 staging and lifetime PD of the out-of-time book (ROADMAP 5.3).
// Fetches on its own, so the Portfolio page still works if the lifetime step
// hasn't been run (the card just doesn't appear).
import { api, pct, moneyShort, num } from "@/lib/api";
import { CardTitle, TableWrap, useFetch } from "@/components/ui";

const STAGE_TEXT = {
  1: "Performing: 12 months of expected loss",
  2: "Risk up a lot since the loan was made: lifetime expected loss",
  3: "In default (90+ days late): loss on default",
};

export default function Ifrs9Staging() {
  const { data } = useFetch(() => api.lifetime(), []);
  if (!data) return null;
  const st = data.staging;
  const life = data.lifetime_pd;
  const bt = data.backtest;
  return (
    <div className="card mb-16">
      <CardTitle info="ifrs9">IFRS 9 staging at {data.reporting_date}</CardTitle>
      <p className="small muted mt-n6">
        {num(st.on_book)} test-book loans still open at the reporting date ({num(st.off_book)} already repaid or
        written off). Average default risk is {pct(life.mean_12m)} over 12 months and{" "}
        {pct(life.mean_lifetime, 1)} over the loan&apos;s whole life.
      </p>
      <TableWrap>
        <table>
          <thead>
            <tr>
              <th>Stage</th><th className="num">Loans</th><th className="num">Owed</th>
              <th className="num">Loss allowance</th><th className="num">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {st.stages.map((s) => (
              <tr key={s.stage}>
                <td>
                  <b className={s.stage === 3 ? "bad" : s.stage === 2 ? "warn" : ""}>Stage {s.stage}</b>
                  <div className="small muted">{STAGE_TEXT[s.stage]}</div>
                </td>
                <td className="num">{num(s.loans)}</td>
                <td className="num">{moneyShort(s.exposure)}</td>
                <td className="num">{moneyShort(s.ecl)}</td>
                <td className="num">{pct(s.coverage, 1)}</td>
              </tr>
            ))}
            <tr>
              <td><b>Total</b></td>
              <td className="num">{num(st.on_book)}</td>
              <td className="num">{moneyShort(st.stages.reduce((a, s) => a + s.exposure, 0))}</td>
              <td className="num"><b>{moneyShort(st.total_ecl)}</b></td>
              <td />
            </tr>
          </tbody>
        </table>
      </TableWrap>
      <details className="more">
        <summary>How lifetime risk is estimated</summary>
        <p className="small muted">
          A survival model fitted on {num(data.hazard.n_loan_months)} loan-months gives the chance of a first
          default in each month of a loan&apos;s life, tied to its 12-month risk; early repayment
          ({pct(data.hazard.prepay_monthly, 2)} a month) is the other way a loan ends. Check over 24 months: on the
          training years it predicted {pct(bt.in_time.predicted_24m, 1)} vs {pct(bt.in_time.observed_24m, 1)}{" "}
          actual; on the {bt.out_of_time.vintages} loans, which met the 2020 shock, {pct(bt.out_of_time.predicted_24m, 1)}{" "}
          vs {pct(bt.out_of_time.observed_24m, 1)}. Stage 2 = 30+ days late, or 12-month risk at least{" "}
          {st.sicr_rule.relative}× its value at origination and {pct(st.sicr_rule.absolute, 1)} higher.
        </p>
      </details>
    </div>
  );
}
