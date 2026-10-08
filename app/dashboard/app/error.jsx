"use client";
// Route-level error boundary: a render error shows this friendly card instead
// of a blank screen. Technical details stay folded away.
export default function Error({ error, reset }) {
  return (
    <div className="card error-state" role="alert" style={{ marginTop: 20 }}>
      <h3 className="bad">This screen ran into a problem</h3>
      <p style={{ margin: "0 0 12px" }}>
        Something unexpected happened while showing this page. Trying again usually fixes it.
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <button className="primary" onClick={() => reset()}>Try again</button>
        <a href="/" className="small muted">Go to the start page</a>
      </div>
      <details className="more">
        <summary>Technical details</summary>
        <p className="small mono muted" style={{ whiteSpace: "pre-wrap" }}>
          {error?.message || String(error)}
          {error?.digest ? `\nreference: ${error.digest}` : ""}
        </p>
      </details>
    </div>
  );
}
