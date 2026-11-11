"use client";
// Catches errors in the root layout itself (must render its own <html>/<body>,
// so it can't rely on globals.css; it brings its own small stylesheet).
import "./global-error.css";

export default function GlobalError({ error, reset }) {
  return (
    <html lang="en">
      <body className="ge-body">
        <h2 className="ge-title">CreditCast couldn&apos;t load</h2>
        <p className="ge-text">
          Something went wrong while starting the app. Please reload the page; if it keeps happening,
          try again in a few minutes.
        </p>
        <button className="ge-btn" onClick={() => reset()}>
          Reload
        </button>
        <details className="ge-details">
          <summary>Technical details</summary>
          <p>{error?.message || String(error)}</p>
        </details>
      </body>
    </html>
  );
}
