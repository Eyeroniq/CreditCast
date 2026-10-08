"use client";
// Catches errors in the root layout itself (must render its own <html>/<body>,
// so it can't rely on globals.css).
export default function GlobalError({ error, reset }) {
  return (
    <html lang="en">
      <body style={{ background: "#0a0d12", color: "#dfe6f0", fontFamily: "system-ui, sans-serif", padding: "40px 16px", maxWidth: 560, margin: "0 auto" }}>
        <h2 style={{ marginBottom: 8 }}>CreditCast couldn't load</h2>
        <p style={{ color: "#8090a3", lineHeight: 1.5 }}>
          Something went wrong while starting the app. Please reload the page; if it keeps happening,
          try again in a few minutes.
        </p>
        <button onClick={() => reset()}
          style={{ background: "#5b9cff", color: "#06101f", border: "none", borderRadius: 8, padding: "10px 18px", fontWeight: 600, cursor: "pointer", marginTop: 8 }}>
          Reload
        </button>
        <details style={{ marginTop: 20, color: "#5c6b7e", fontSize: 12 }}>
          <summary style={{ cursor: "pointer" }}>Technical details</summary>
          <p style={{ fontFamily: "monospace", whiteSpace: "pre-wrap" }}>{error?.message || String(error)}</p>
        </details>
      </body>
    </html>
  );
}
