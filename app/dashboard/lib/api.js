// Thin client for the CreditCast FastAPI scoring service.
// Same-origin in the container (base = "/api"); in split local dev set
// NEXT_PUBLIC_API_URL=http://localhost:8001 and it becomes that host + "/api".
export const API = `${process.env.NEXT_PUBLIC_API_URL || ""}/api`;

/** An API failure the UI can explain (ROADMAP 6.3.3). `kind` drives the
 *  friendly title; `message` is safe to show; `detail` is the raw server text. */
export class ApiError extends Error {
  constructor(message, { status = 0, kind = "error", detail = null, requestId = null } = {}) {
    super(message);
    this.name = "ApiError";
    Object.assign(this, { status, kind, detail, requestId });
  }
}

const KIND = (status) =>
  status === 0 ? "offline" : status === 404 ? "missing" : status === 422 ? "invalid"
    : status === 429 ? "busy" : status === 401 ? "auth" : status === 503 ? "unavailable"
    : status >= 500 ? "server" : "error";

const FALLBACK = {
  offline: "Can't reach the CreditCast server. Check your connection and try again.",
  missing: "This report hasn't been generated yet.",
  invalid: "Some values aren't valid.",
  busy: "Too many requests in a short time — please wait a minute and try again.",
  auth: "This API requires a key.",
  unavailable: "This feature isn't switched on right now.",
  server: "Something went wrong on our side. Please try again.",
  error: "Something went wrong.",
};

// Prefer the API's own message (`detail`): rate limits (429), validation
// errors (422) and request IDs on 500s are written for people to read. 404s
// carry developer hints ("run the pipeline"), so they get a plain message.
async function errorFrom(r) {
  const body = await r.json().catch(() => ({}));
  const d = body.detail;
  const detail = Array.isArray(d)                 // pydantic 422 list
    ? d.map((e) => `${(e.loc || []).slice(-1)[0]}: ${e.msg}`).join("; ")
    : d || null;
  const kind = KIND(r.status);
  const message = kind === "missing" || !detail ? FALLBACK[kind] : detail;
  return new ApiError(message, { status: r.status, kind, detail,
                                 requestId: r.headers.get("x-request-id") });
}

/** fetch() that turns network failures into a friendly "offline" ApiError. */
async function request(url, opts) {
  try {
    return await fetch(url, opts);
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new ApiError(FALLBACK.offline, { status: 0, kind: "offline", detail: e.message });
  }
}

async function get(path) {
  const r = await request(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw await errorFrom(r);
  return r.json();
}

export const api = {
  health: () => get("/health"),
  validation: () => get("/validation"),
  governance: () => get("/governance"),
  monitoring: () => get("/monitoring"),
  thresholdCurve: () => get("/threshold-curve"),
  shapGlobal: () => get("/shap/global"),
  portfolio: (n = 400) => get(`/portfolio?n=${n}`),
  agentTeam: () => get("/agent/team"),
  agentChat: async (question) => {
    const r = await request(`${API}/agent/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
  // `signal` lets live scoring cancel a request that a newer slider move replaced.
  whatif: async (applicant, { signal } = {}) => {
    const r = await request(`${API}/whatif`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(applicant),
      signal,
    });
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
  score: async (applicant, { signal } = {}) => {
    const r = await request(`${API}/score`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(applicant),
      signal,
    });
    if (!r.ok) throw await errorFrom(r);
    return r.json();
  },
};

// formatters
export const pct = (x, d = 2) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
export const num = (x, d = 0) =>
  x == null ? "—" : x.toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
export const money = (x) =>
  x == null ? "—" : `$${Number(x).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
export const moneyShort = (x) => {
  if (x == null) return "—";
  const a = Math.abs(x);
  if (a >= 1e9) return `$${(x / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(x / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `$${(x / 1e3).toFixed(1)}K`;
  return `$${x.toFixed(0)}`;
};

// PSI / generic status -> semantic class
export function statusClass(status) {
  return status === "stable" || status === true ? "ok"
    : status === "watch" ? "warn" : "bad";
}
