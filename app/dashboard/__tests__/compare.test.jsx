// Compare applicants (6.2.3): differences are highlighted best/worst per row.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Compare, { ROWS, rowTones } from "@/components/Compare";

const pin = (id, label, pd, decision, fico) => ({
  id, label, key: String(id),
  form: { fico, dti: 30, ltv: 80, orig_interest_rate: 4, orig_upb: 300000 },
  res: { decision, pd, credit_score: 600, risk_band: decision === "approve" ? "A" : "B",
    expected_loss: pd * 100000, reason_codes: decision === "approve" ? [] : [{ rank: 1, reason: "Low credit score" }] },
});
const PINS = [pin(1, "Prime", 0.01, "approve", 790), pin(2, "Risky", 0.2, "decline", 640)];
const row = (label) => ROWS.find((r) => r.label === label);

describe("rowTones", () => {
  it("marks the lowest default risk best and the highest worst", () => {
    expect(rowTones(row("Default risk"), PINS)).toEqual(["best", "worst"]);
  });
  it("marks a higher model score as best", () => {
    expect(rowTones(row("Model score"), [PINS[0], { ...PINS[1], res: { ...PINS[1].res, credit_score: 700 } }]))
      .toEqual(["worst", "best"]);
  });
  it("highlights nothing when values match or only one applicant is pinned", () => {
    expect(rowTones(row("Loan amount"), PINS)).toEqual(["", ""]);
    expect(rowTones(row("Default risk"), PINS.slice(0, 1))).toEqual([""]);
  });
});

describe("Compare", () => {
  it("renders nothing with no pins", () => {
    const { container } = render(<Compare pins={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows applicants side by side and unpins on request", async () => {
    const onRemove = vi.fn();
    render(<Compare pins={PINS} onRemove={onRemove} onLoad={() => {}} onClear={() => {}} />);
    expect(screen.getByText("✓ Approved")).toHaveClass("best");
    expect(screen.getByText("✗ Declined")).toHaveClass("worst");
    expect(screen.getByText("Low credit score")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Unpin Risky" }));
    expect(onRemove).toHaveBeenCalledWith(2);
  });
});
