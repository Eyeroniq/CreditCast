// Plain-language labels (6.1.1) and friendly API errors (6.3.3).
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, pct, money } from "@/lib/api";
import { categoryLabel, featureLabel } from "@/lib/labels";

describe("labels", () => {
  it("translates codes and feature names", () => {
    expect(featureLabel("fico")).toBe("Credit score");
    expect(featureLabel("ltv_dti")).toBe("Combined leverage (LTV × DTI)");
    expect(categoryLabel("occupancy_status", "I")).toBe("Investment property");
    expect(categoryLabel("property_type", "MH")).toBe("Manufactured home");
  });

  it("never shows a raw snake_case name for unknown features", () => {
    expect(featureLabel("some_new_feature")).toBe("Some new feature");
  });
});

describe("formatters", () => {
  it("formats percentages and money", () => {
    expect(pct(0.0625)).toBe("6.25%");
    expect(pct(null)).toBe("—");
    expect(money(272000)).toBe("$272,000");
  });
});

function respond(status, body, headers = {}) {
  return Promise.resolve(new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json", ...headers },
  }));
}

describe("friendly API errors", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("404 becomes 'not generated yet', hiding the developer hint", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(404, { detail: "x.json not found — run the pipeline first" })));
    const err = await api.validation().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.kind).toBe("missing");
    expect(err.message).toBe("This report hasn't been generated yet.");
    expect(err.detail).toContain("run the pipeline");
  });

  it("429 keeps the server's human-readable message", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(429, { detail: "You're sending requests quickly" })));
    const err = await api.portfolio(10).catch((e) => e);
    expect(err.kind).toBe("busy");
    expect(err.message).toContain("sending requests quickly");
  });

  it("422 validation lists become one readable line", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(422, {
      detail: [{ loc: ["body", "fico"], msg: "Input should be greater than or equal to 300" }],
    })));
    const err = await api.score({}).catch((e) => e);
    expect(err.kind).toBe("invalid");
    expect(err.message).toBe("fico: Input should be greater than or equal to 300");
  });

  it("500 carries the request id for support", async () => {
    vi.stubGlobal("fetch", vi.fn(() => respond(500, { detail: "Internal error (request id abc123)" },
      { "x-request-id": "abc123" })));
    const err = await api.governance().catch((e) => e);
    expect(err.kind).toBe("server");
    expect(err.requestId).toBe("abc123");
  });

  it("a network failure becomes 'offline'", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    const err = await api.monitoring().catch((e) => e);
    expect(err.kind).toBe("offline");
    expect(err.message).toMatch(/Can't reach the CreditCast server/);
  });

  it("a cancelled request is not reported as offline", async () => {
    const abort = Object.assign(new Error("aborted"), { name: "AbortError" });
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(abort)));
    await expect(api.score({}, { signal: new AbortController().signal })).rejects.toBe(abort);
  });
});
