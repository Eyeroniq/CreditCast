"use client";
// PDF export (ROADMAP 6.3.6) via the browser's own print → "Save as PDF".
// No dependency: print CSS in globals.css hides the app chrome, forces the
// light palette and keeps cards whole across pages.
//
// Charts size themselves to the screen, and the browser would just shrink them
// onto the page (tiny axis labels). So printing first switches to the
// `print-layout` class (content exactly A4 wide), lets the charts redraw at
// that width, then prints. `#print` in the URL opens a page in that layout.
import { useEffect } from "react";

const PRINT_LAYOUT = "print-layout";
// A plain timer rather than animation frames, which browsers pause in
// background tabs; 300 ms covers the re-layout and chart redraw.
const settle = () => new Promise((r) => setTimeout(r, 300));

/** Opens the print dialog; `filename` becomes the suggested PDF name. */
export function PrintButton({ label = "⤓ Download PDF", filename }) {
  const print = async () => {
    const root = document.documentElement;
    const previous = document.title;
    const hadLayout = root.classList.contains(PRINT_LAYOUT);
    if (filename) document.title = filename;
    root.classList.add(PRINT_LAYOUT);
    await settle();                          // layout at page width, charts redrawn
    const restore = () => {
      document.title = previous;
      if (!hadLayout) root.classList.remove(PRINT_LAYOUT);
      window.removeEventListener("afterprint", restore);
    };
    window.addEventListener("afterprint", restore);
    window.print();
  };
  return (
    <button type="button" className="chip print-btn" onClick={print}
      title="Opens the print dialog. Choose “Save as PDF” as the destination.">
      {label}
    </button>
  );
}

/** Header that appears only on paper: what this is, when, and which model.
 *  Also applies the print-ready layout when the URL ends with `#print`. */
export function PrintHeader({ title, stamp }) {
  useEffect(() => {
    if (window.location.hash === "#print") document.documentElement.classList.add(PRINT_LAYOUT);
  }, []);
  const when = new Date().toLocaleString(undefined, { dateStyle: "long", timeStyle: "short" });
  return (
    <div className="print-only print-header">
      <div className="print-brand">CreditCast</div>
      <div>
        <strong>{title}</strong> · generated {when}
        {stamp && (
          <> · model data {stamp.data_version}, code {stamp.code_version}
            {stamp.git_sha && stamp.git_sha !== "unknown" ? ` (${stamp.git_sha.slice(0, 7)})` : ""}</>
        )}
      </div>
      <div className="print-note">
        Demonstration system on synthetic mortgage data — not a real credit decision or report.
      </div>
    </div>
  );
}
