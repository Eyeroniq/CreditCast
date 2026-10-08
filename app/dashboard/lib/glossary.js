// Every term the cockpit uses, explained simply (ROADMAP 6.1.2). `short` feeds
// the ⓘ tooltips; `long` and `good` appear on the Glossary page.

export const GLOSSARY = {
  // ---- Loss maths
  pd: {
    term: "PD — Probability of Default", group: "Loss maths",
    short: "Chance the borrower falls 90+ days behind on payments within 12 months.",
    long: "The model's estimate that this loan will default in the next 12 months. A PD of 5% means about 5 in 100 similar borrowers are expected to default.",
    good: "Lower is safer. Loans above the approval threshold are declined.",
  },
  lgd: {
    term: "LGD — Loss Given Default", group: "Loss maths",
    short: "If the borrower defaults, the share of the money the bank loses after selling the home.",
    long: "After a default the bank recovers money, mostly by selling the house. LGD is what is not recovered, as a share of the amount owed. Many defaults cure (the borrower catches up) and lose nothing.",
    good: "Lower is better. A 30% LGD on $200k owed means a $60k loss.",
  },
  ead: {
    term: "EAD — Exposure at Default", group: "Loss maths",
    short: "How much is still owed when the borrower defaults.",
    long: "For a mortgage, the remaining balance at the expected time of default — a little less than the original loan because some has been repaid.",
    good: "Close to the loan amount for new mortgages.",
  },
  el: {
    term: "Expected Loss", group: "Loss maths",
    short: "PD × LGD × EAD — the average loss to budget for, per loan or for the whole book.",
    long: "Combines the chance of default, the share lost and the amount owed into one money figure. Summed over the portfolio it is what a bank provisions for.",
    good: "Shown in money and in bps (basis points) of exposure: 100 bps = 1%.",
  },
  bps: {
    term: "bps — basis points", group: "Loss maths",
    short: "Hundredths of a percent: 100 bps = 1%.",
    long: "Used for small rates. A portfolio Expected Loss of 120 bps means losses of about 1.2% of the money lent.",
    good: "",
  },
  // ---- Decisions
  credit_score: {
    term: "Credit score (scorecard points)", group: "Decisions",
    short: "Points from the bank's scorecard model: higher means lower risk.",
    long: "The regulatory scorecard turns each characteristic into points and adds them up. Every 20 points halves the odds of default.",
    good: "Higher is better; it sets the risk grade.",
  },
  risk_band: {
    term: "Risk grade (AAA → B)", group: "Decisions",
    short: "A rating from AAA (lowest risk) to B (highest risk), based on the credit score.",
    long: "Groups borrowers into six grades so portfolios can be compared and priced. Each lower grade has a higher observed default rate.",
    good: "AAA–A are low risk, BBB moderate, BB–B high.",
  },
  threshold: {
    term: "Approval threshold", group: "Decisions",
    short: "Applications are approved when their PD is at or below this cut-off.",
    long: "Approving someone who later defaults is assumed to cost 15× more than turning away a good borrower, so the cut-off is 1 / (1 + 15) ≈ 6.25%. It is never tuned on the test data.",
    good: "",
  },
  reason_codes: {
    term: "Reason codes", group: "Decisions",
    short: "The main factors behind a decline, given to the applicant in plain words.",
    long: "Lending law (e.g. US ECOA/Reg B) requires telling declined applicants why. CreditCast takes them from the factors that raised this applicant's risk the most.",
    good: "",
  },
  // ---- Model quality
  gini: {
    term: "Gini", group: "Model quality",
    short: "How well the model separates borrowers who repay from those who default. 0 = guessing, 1 = perfect.",
    long: "Measured on newer loans the model never saw (out-of-time). Mortgage models typically score 0.4–0.6.",
    good: "Must be at least 0.35 to pass the quality gate.",
  },
  ks: {
    term: "KS statistic", group: "Model quality",
    short: "The biggest gap between how the model scores good and bad borrowers.",
    long: "Another separation measure: the largest difference between the score distributions of defaulters and non-defaulters.",
    good: "Must be at least 0.25 to pass.",
  },
  auc: {
    term: "AUC", group: "Model quality",
    short: "Chance a random defaulter is ranked riskier than a random good borrower.",
    long: "0.5 is a coin flip, 1.0 is perfect. Gini = 2 × AUC − 1.",
    good: "Higher is better.",
  },
  calibration: {
    term: "Calibration", group: "Model quality",
    short: "Whether predicted PDs match what really happens (5% predicted ≈ 5% default).",
    long: "A model can rank well but still say 10% when the truth is 5%. CreditCast calibrates on a separate slice of data so its percentages can be trusted for money calculations.",
    good: "The worst band may be off by at most 3 percentage points.",
  },
  ece: {
    term: "ECE — Expected Calibration Error", group: "Model quality",
    short: "The average gap between predicted and actual default rates.",
    long: "Averaged across score bands, weighted by how many loans are in each.",
    good: "Lower is better; below 0.01 is very good.",
  },
  hosmer_lemeshow: {
    term: "Hosmer–Lemeshow test", group: "Model quality",
    short: "A statistical test of calibration, shown for information only.",
    long: "With thousands of loans it flags even tiny, harmless differences, so CreditCast gates on the band error and ECE instead.",
    good: "",
  },
  oot: {
    term: "Out-of-time (OOT) testing", group: "Model quality",
    short: "Train on older loans, test on newer ones — never a random split.",
    long: "In real life a model always predicts the future from the past. Testing on later origination months is the honest way to measure it.",
    good: "",
  },
  scorecard_vs_challenger: {
    term: "Scorecard vs challenger", group: "Model quality",
    short: "The simple, regulator-friendly scorecard compared with a more complex machine-learning model.",
    long: "Banks keep a 'challenger' (here LightGBM) to measure how much accuracy the interpretable scorecard gives up. A small gap favours the scorecard.",
    good: "",
  },
  gains: {
    term: "Cumulative gains", group: "Model quality",
    short: "Share of all defaults found when you review the riskiest X% of loans first.",
    long: "A steep early curve means the model puts most defaults at the top of the risk ranking.",
    good: "Steeper is better.",
  },
  // ---- Stability
  psi: {
    term: "PSI — Population Stability Index", group: "Stability",
    short: "How much the mix of borrowers' scores has shifted since the model was trained.",
    long: "Compares today's score distribution with the training one. Big shifts mean the model is seeing a different population and may need review.",
    good: "Below 0.10 stable · 0.10–0.25 watch · above 0.25 unstable.",
  },
  csi: {
    term: "CSI — Characteristic Stability Index", group: "Stability",
    short: "PSI for a single input (for example, debt-to-income).",
    long: "Shows which borrower characteristics are drifting.",
    good: "Same bands as PSI.",
  },
  drift: {
    term: "Drift monitoring", group: "Stability",
    short: "A weekly check that the borrowers being scored still look like the training data.",
    long: "Runs automatically and opens an alert when PSI or CSI leaves the stable band.",
    good: "",
  },
  // ---- Fairness
  disparate_impact: {
    term: "Disparate impact (4/5ths rule)", group: "Fairness",
    short: "Each group's approval rate divided by the reference group's. Below 0.80 needs review.",
    long: "Race is never given to the model, but neutral inputs like credit score can still mirror historical disparities. This ratio checks the outcome.",
    good: "0.80 or higher passes the four-fifths rule.",
  },
  equal_opportunity: {
    term: "Equal-opportunity difference", group: "Fairness",
    short: "Gap in approval rates among borrowers who actually repaid.",
    long: "Of the people who turned out to be good borrowers, were some groups approved less often?",
    good: "Closer to 0 is fairer.",
  },
  // ---- Explainability
  shap: {
    term: "SHAP", group: "Explainability",
    short: "How much each factor pushed this applicant's risk up (red) or down (green).",
    long: "A standard method that splits a prediction into contributions from each input. Global SHAP ranks which factors matter most across all loans.",
    good: "",
  },
  woe_iv: {
    term: "WoE / IV", group: "Explainability",
    short: "Weight of Evidence (risk of each bucket) and Information Value (how useful a feature is).",
    long: "The scorecard splits each input into buckets (e.g. credit score 650–700) and scores each bucket's risk. Features with very low IV are dropped.",
    good: "",
  },
};

export const GLOSSARY_GROUPS = [
  "Loss maths", "Decisions", "Model quality", "Stability", "Fairness", "Explainability",
];
