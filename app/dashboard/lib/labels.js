// Plain-language labels (ROADMAP 6.1.1). The API and models keep their short
// codes; only the UI translates them. One dictionary for the whole cockpit.

export const CATEGORY_LABELS = {
  occupancy_status: { P: "Primary home", I: "Investment property", S: "Second home" },
  loan_purpose: { P: "Purchase", C: "Cash-out refinance", N: "Rate/term refinance" },
  property_type: { SF: "Single-family house", CO: "Condo", PU: "Planned community (PUD)", MH: "Manufactured home" },
  first_time_homebuyer: { Y: "Yes", N: "No" },
  // Used only to look up local economic conditions; "" = national average.
  property_state: {
    "": "Not specified (national)", CA: "California", TX: "Texas", FL: "Florida", NY: "New York",
    IL: "Illinois", PA: "Pennsylvania", OH: "Ohio", GA: "Georgia", NC: "North Carolina", MI: "Michigan",
  },
};

export const FEATURE_LABELS = {
  fico: "Credit score",
  dti: "Debt-to-income",
  ltv: "Loan-to-value",
  orig_interest_rate: "Interest rate",
  orig_upb: "Loan amount",
  orig_loan_term: "Loan term",
  occupancy_status: "Occupancy",
  loan_purpose: "Loan purpose",
  property_type: "Property type",
  first_time_homebuyer: "First-time buyer",
  ltv_dti: "Combined leverage (LTV × DTI)",
  rate_spread: "Rate vs market",
  high_ltv: "Loan-to-value above 80%",
  property_state: "Property state",
  unemp_rate: "Local unemployment rate",
  unemp_chg_12m: "Change in local unemployment (12 mo)",
  hpi_chg_12m: "Local house-price growth (12 mo)",
  vintage: "Origination month",
};

/** "fico" -> "Credit score"; unknown names are prettified, never shown raw. */
export function featureLabel(name) {
  if (FEATURE_LABELS[name]) return FEATURE_LABELS[name];
  return String(name).replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

/** ("occupancy_status", "I") -> "Investment property". */
export function categoryLabel(feature, code) {
  return CATEGORY_LABELS[feature]?.[code] ?? code;
}

export const DECISION_LABELS = { approve: "Approved", decline: "Declined" };
