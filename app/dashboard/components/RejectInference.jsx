"use client";
// Reject inference study (ROADMAP 5.4): what a model trained only on booked
// loans gets wrong about the applicants the old policy turned away.
import { api, pct, num } from "@/lib/api";
import { CardTitle, TableWrap, useFetch } from "@/components/ui";

const METHODS = {
  ignore: "Ignore rejects (booked loans only)",
  parceling: "Parceling",
  fuzzy: "Fuzzy augmentation",
  oracle: "Oracle: every outcome known (not possible in practice)",
};
const SCENARIOS = {
  rules_only: "Old policy: rules only",
  rules_and_judgment: "Old policy: rules + underwriter judgment",
};
const signed = (v) => `${v > 0 ? "+" : ""}${v.toFixed(1)} pts`;

export default function RejectInference() {
  const { data } = useFetch(() => api.rejectInference(), []);
  if (!data) return null;
  const first = Object.values(data.scenarios)[0];
  return (
    <div className="card" style={{ marginTop: 16 }}>
      <CardTitle info="reject_inference">Reject inference: what booked-loan data hides</CardTitle>
      <p className="small muted" style={{ marginTop: -6 }}>
        A lender only sees outcomes for loans it approved. Here an old policy turns away applicants below a credit
        score of {first.policy.min_fico}, above {first.policy.max_dti}% debt-to-income or above {first.policy.max_ltv}%
        loan-to-value, and each method is judged on the {num(first.test.old_rejects)} later applicants that policy
        would have rejected (actual default rate {pct(first.test.actual_rate_old_rejects, 1)}).
      </p>
      <div className="grid cols-2">
        {Object.entries(data.scenarios).map(([key, sc]) => (
          <div key={key}>
            <h4 className="small" style={{ margin: "0 0 8px" }}>
              {SCENARIOS[key]} · {pct(sc.train.reject_rate, 0)} rejected
            </h4>
            <TableWrap>
              <table>
                <thead>
                  <tr><th>Method</th><th className="num">Gini</th><th className="num">Miss on rejects</th></tr>
                </thead>
                <tbody>
                  {Object.entries(sc.methods).map(([m, v]) => (
                    <tr key={m}>
                      <td className="small">
                        {METHODS[m]}{m === sc.chosen && <b className="ok"> ✓ best</b>}
                      </td>
                      <td className="num">{v.gini_all.toFixed(3)}</td>
                      <td className="num">{signed(v.miss_old_rejects_pts)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </div>
        ))}
      </div>
      <p className="small muted" style={{ marginBottom: 0 }}>
        &quot;Miss&quot; is predicted minus actual default rate among those applicants; negative means the model thinks
        they&apos;re safer than they are. When the old decisions used only what the model sees, ignoring rejects is
        fine and filling them in over-corrects. When underwriters also turned people down on information the model
        never sees, booked loans look too safe and {METHODS[data.chosen].toLowerCase()} corrects most of it. Study
        only: the live model trains on every loan, because this synthetic book knows every outcome.
      </p>
    </div>
  );
}
