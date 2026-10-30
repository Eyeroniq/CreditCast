"use client";
// Guided tour (ROADMAP 6.1.4): short steps across the cockpit (seven while the
// Copilot is hidden, eight with it). Starts by
// itself on a first visit to the start page; "Take the tour" in the sidebar
// replays it. Built in-house (no library): steps span several pages, and the
// spotlight and card use the theme tokens. Targets are `[data-tour="…"]`.
import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { SHOW_COPILOT } from "@/lib/features";

const DONE_KEY = "cc-tour-done";
export const START_TOUR_EVENT = "cc-start-tour";

const ALL_STEPS = [
  { path: "/", target: "nav", title: "Welcome to CreditCast",
    text: "A mortgage credit-risk cockpit. These screens take you from scoring one applicant to checking the whole model. This tour takes under a minute." },
  { path: "/", target: "sliders", title: "Score an applicant live",
    text: "Drag any slider: the decision updates instantly. The coloured tracks show which values are safe (green), borderline (amber) or risky (red)." },
  { path: "/", target: "decision", title: "The decision, explained",
    text: "Approved or declined, why in one line, the default-risk meter against the approval limit, and the risk grade. Declined applicants also see what change would get them approved." },
  { path: "/portfolio/", target: "charts", title: "The whole portfolio",
    text: "How much loss to expect and where it sits. Click any bar to filter the loan table below it." },
  { path: "/portfolio/", target: "loan-table", title: "Every loan, searchable",
    text: "Search, sort any column, filter, and export exactly what you see to CSV." },
  { path: "/governance/", target: "threshold", title: "Try a different approval limit",
    text: "Drag the limit and watch approvals, expected loss and fairness move together. The fairness rule (4/5ths) is shown with ✓ or ✗." },
  { path: "/copilot/", target: "copilot", title: "Ask the AI risk team",
    text: "Ask questions in plain English. Specialist agents answer with the real numbers and charts, never invented figures." },
  { path: "/glossary/", target: "glossary", title: "Jargon, explained",
    text: "Tap any ⓘ for a one-line explanation, or browse every term here. You can replay this tour from the menu anytime." },
];
// Without an LLM key the Copilot is hidden, so its step is skipped too.
const STEPS = ALL_STEPS.filter((s) => SHOW_COPILOT || s.path !== "/copilot/");

const PAD = 8;

function markDone() {
  try { localStorage.setItem(DONE_KEY, "1"); } catch { /* storage blocked */ }
}

/** Wait until a [data-tour] target exists and is visible (pages load data first). */
function waitFor(target, timeout = 4000) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const tick = () => {
      const el = document.querySelector(`[data-tour="${target}"]`);
      if (el && el.getClientRects().length) return resolve(el);
      // Present but hidden (e.g. the collapsed menu on phones), or never
      // appeared: fall back to a centred card.
      if (el || Date.now() - t0 > timeout) return resolve(null);
      setTimeout(tick, 100);
    };
    tick();
  });
}

export default function Tour() {
  const router = useRouter();
  const path = usePathname();
  const [step, setStep] = useState(null);          // null = closed
  const [rect, setRect] = useState(null);
  const cardRef = useRef(null);
  const elRef = useRef(null);

  const close = useCallback(() => { setStep(null); setRect(null); markDone(); }, []);

  // Start: first visit to the start page, or the sidebar button / event.
  useEffect(() => {
    const start = () => setStep(0);
    window.addEventListener(START_TOUR_EVENT, start);
    let seen = true;
    try { seen = localStorage.getItem(DONE_KEY) === "1"; } catch { /* treat as seen */ }
    if (!seen && path === "/") setTimeout(start, 900);    // let the page settle first
    return () => window.removeEventListener(START_TOUR_EVENT, start);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Go to the step's page, wait for its target, spotlight it.
  useEffect(() => {
    if (step === null) return;
    const s = STEPS[step];
    let alive = true;
    setRect(null);
    if (path !== s.path) { router.push(s.path); return; }   // effect re-runs on arrival
    waitFor(s.target).then((el) => {
      if (!alive) return;
      elRef.current = el;
      if (el) {
        el.scrollIntoView({ block: "center", behavior: "instant" });
        setRect(el.getBoundingClientRect());
      } else {
        setRect("center");
      }
      setTimeout(() => cardRef.current?.focus(), 0);
    });
    return () => { alive = false; };
  }, [step, path, router]);

  // Keep the spotlight on its element while scrolling/resizing.
  useEffect(() => {
    if (step === null) return;
    const update = () => elRef.current && setRect(elRef.current.getBoundingClientRect());
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => { window.removeEventListener("resize", update); window.removeEventListener("scroll", update, true); };
  }, [step]);

  // Keyboard: Esc closes, arrows move.
  useEffect(() => {
    if (step === null) return;
    const onKey = (e) => {
      if (e.key === "Escape") close();
      if (e.key === "ArrowRight") setStep((i) => (i < STEPS.length - 1 ? i + 1 : i));
      if (e.key === "ArrowLeft") setStep((i) => (i > 0 ? i - 1 : i));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, close]);

  if (step === null || rect === null) return null;
  const s = STEPS[step];
  const last = step === STEPS.length - 1;
  const centred = rect === "center" || typeof window === "undefined";

  // Card below the target if there's room, else above; clamped to the viewport.
  let cardStyle = {};
  if (!centred) {
    const vw = window.innerWidth, vh = window.innerHeight, w = Math.min(340, vw - 32);
    const below = rect.bottom + PAD + 12;
    const top = below + 190 < vh ? below : Math.max(16, rect.top - PAD - 12 - 190);
    const left = Math.min(Math.max(16, rect.left), vw - w - 16);
    cardStyle = { top, left, width: w };
  }

  return (
    <div className="tour" aria-live="polite">
      {centred ? <div className="tour-dim" onClick={close} /> : (
        <div className="tour-spot" onClick={close} style={{
          top: rect.top - PAD, left: rect.left - PAD,
          width: rect.width + PAD * 2, height: rect.height + PAD * 2,
        }} />
      )}
      <div ref={cardRef} tabIndex={-1} role="dialog" aria-modal="true"
        aria-labelledby="tour-title" className={`tour-card ${centred ? "centred" : ""}`} style={cardStyle}>
        <div className="small muted">Step {step + 1} of {STEPS.length}</div>
        <h3 id="tour-title">{s.title}</h3>
        <p>{s.text}</p>
        <div className="tour-actions">
          <button type="button" className="chip" onClick={close}>Skip tour</button>
          <div style={{ display: "flex", gap: 8 }}>
            {step > 0 && <button type="button" className="chip" onClick={() => setStep(step - 1)}>‹ Back</button>}
            <button type="button" className="primary" onClick={() => (last ? close() : setStep(step + 1))}>
              {last ? "Finish" : "Next ›"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
