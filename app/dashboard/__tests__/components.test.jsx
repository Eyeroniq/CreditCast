// Component behaviour: loan table (6.2.6), theme toggle (6.3.2), tooltips
// (6.1.2), error states (6.3.3) and the decision letter (6.3.6).
import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import LoanTable, { EMPTY_FILTERS } from "@/components/LoanTable";
import ThemeToggle from "@/components/ThemeToggle";
import DecisionLetter from "@/components/DecisionLetter";
import { ErrorState, InfoTip } from "@/components/ui";
import { ApiError } from "@/lib/api";

const ROWS = [
  { loan_id: 101, vintage: "2020-01", pd_champion: 0.02, credit_score: 640, risk_band: "AAA",
    lgd_hat: 0.2, ead: 200000, expected_loss: 800, decision: "approve", default_12m: 0 },
  { loan_id: 202, vintage: "2020-02", pd_champion: 0.15, credit_score: 520, risk_band: "B",
    lgd_hat: 0.4, ead: 300000, expected_loss: 18000, decision: "decline", default_12m: 1 },
  { loan_id: 303, vintage: "2020-02", pd_champion: 0.08, credit_score: 560, risk_band: "BB",
    lgd_hat: 0.3, ead: 250000, expected_loss: 6000, decision: "decline", default_12m: 0 },
];

function Table() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  return <LoanTable rows={ROWS} filters={filters} onFilters={setFilters} />;
}
const bodyRows = () => screen.getAllByRole("row").slice(1);

describe("LoanTable", () => {
  it("sorts by expected loss (highest first) by default, and re-sorts on click", async () => {
    render(<Table />);
    expect(within(bodyRows()[0]).getByText("202")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Default risk/ }));   // desc
    await userEvent.click(screen.getByRole("button", { name: /Default risk/ }));   // asc
    expect(within(bodyRows()[0]).getByText("101")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Default risk/ })).toHaveAttribute("aria-sort", "ascending");
  });

  it("filters by search and by decision, with removable chips", async () => {
    render(<Table />);
    await userEvent.selectOptions(screen.getByLabelText("Filter by decision"), "decline");
    expect(bodyRows()).toHaveLength(2);
    expect(screen.getByText(/filtered from 3/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search by loan ID"), "303");
    expect(bodyRows()).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(bodyRows()).toHaveLength(3);
  });

  it("exports exactly the filtered rows to CSV", async () => {
    let csv = "";
    const create = vi.fn((blob) => { blob.text().then((t) => { csv = t; }); return "blob:x"; });
    URL.createObjectURL = create;
    URL.revokeObjectURL = vi.fn();
    render(<Table />);
    await userEvent.selectOptions(screen.getByLabelText("Filter by grade"), "B");
    await userEvent.click(screen.getByRole("button", { name: /Export CSV \(1\)/ }));
    await vi.waitFor(() => expect(csv).not.toBe(""));
    const lines = csv.trim().split("\n");
    expect(lines[0]).toContain("Loan,Originated,Default risk");
    expect(lines).toHaveLength(2);
    expect(lines[1].startsWith("202,")).toBe(true);
  });

  it("says so when nothing matches", async () => {
    render(<Table />);
    await userEvent.type(screen.getByLabelText("Search by loan ID"), "999");
    expect(screen.getByText("No loans match these filters.")).toBeInTheDocument();
  });
});

describe("ThemeToggle", () => {
  it("cycles System -> Light -> Dark -> System and remembers the choice", async () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("button", { name: /Colour theme/ });
    expect(btn).toHaveTextContent("System");
    await userEvent.click(btn);
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("cc-theme")).toBe("light");
    await userEvent.click(btn);
    expect(document.documentElement.dataset.theme).toBe("dark");
    await userEvent.click(btn);
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem("cc-theme")).toBeNull();
  });
});

describe("InfoTip", () => {
  it("explains a glossary term and is wired for screen readers", async () => {
    render(<InfoTip k="pd" />);
    const btn = screen.getByRole("button", { name: /What is PD/ });
    const tip = screen.getByRole("tooltip", { hidden: true });
    expect(btn).toHaveAttribute("aria-describedby", tip.id);
    expect(tip).toHaveTextContent(/falls 90\+ days behind/);
    await userEvent.click(btn);
    expect(btn.parentElement).toHaveClass("open");
  });
});

describe("ErrorState", () => {
  it.each([
    ["offline", "Can't reach CreditCast"],
    ["missing", "Not available yet"],
    ["busy", "Slow down a moment"],
    ["server", "Something went wrong on our side"],
  ])("shows a friendly title for %s errors and retries", async (kind, title) => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError("msg", { kind, status: 500, requestId: "r1" })} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(title);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

describe("DecisionLetter", () => {
  const form = { fico: 690, dti: 38, ltv: 82, orig_interest_rate: 4.3, orig_upb: 300000,
                 orig_loan_term: 360, occupancy_status: "P", loan_purpose: "N",
                 property_type: "CO", first_time_homebuyer: "Y" };
  const base = { pd: 0.0689, threshold: 0.0625, risk_band: "BB", expected_loss: 6115,
                 request_id: "abc123", model_fingerprint: "7bed00881754" };

  it("a decline lists the reasons and the changes that could help", () => {
    const { container } = render(<DecisionLetter form={form}
      res={{ ...base, decision: "decline", reason_codes: [{ rank: 1, reason: "Credit score is low (690)" }] }}
      whatif={{ options: [{ feature: "fico", text: "Raise credit score from 690 to 708" }] }} />);
    const letter = container.querySelector(".letter");
    expect(letter).toHaveTextContent("Mortgage application — not approved");
    expect(letter).toHaveTextContent("Credit score is low (690)");
    expect(letter).toHaveTextContent("Raise credit score from 690 to 708.");
    expect(letter).toHaveTextContent("Reference abc123");
    expect(letter).toHaveTextContent("Rate/term refinance");        // plain labels, not codes
    expect(letter).toHaveTextContent("not an offer or refusal of credit");
  });

  it("an approval has no reasons section", () => {
    const { container } = render(<DecisionLetter form={form}
      res={{ ...base, pd: 0.03, decision: "approve", reason_codes: [] }} whatif={null} />);
    const letter = container.querySelector(".letter");
    expect(letter).toHaveTextContent("Mortgage application — approved");
    expect(letter).not.toHaveTextContent("Principal reasons");
  });
});
