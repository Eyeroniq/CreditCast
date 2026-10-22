"use client";
// Floating glass top bar: brand, pill navigation, live model status, tour and
// theme. On phones the pills fold into a glass dropdown behind "☰ Menu".
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import ThemeToggle from "@/components/ThemeToggle";
import { START_TOUR_EVENT } from "@/components/Tour";

const NAV = [
  { href: "/", label: "Score", full: "Score an applicant" },
  { href: "/portfolio", label: "Portfolio", full: "Portfolio risk" },
  { href: "/validation", label: "Quality", full: "Model quality" },
  { href: "/monitoring", label: "Stability", full: "Stability & drift" },
  { href: "/governance", label: "Fairness", full: "Fairness & explanations" },
  { href: "/copilot", label: "Copilot", full: "Risk Copilot", ai: true },
  { href: "/glossary", label: "Glossary", full: "Glossary" },
];

const startTour = () => window.dispatchEvent(new Event(START_TOUR_EVENT));

export default function TopBar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);          // phone menu
  const [status, setStatus] = useState(null);       // null = checking
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    api.health()
      .then((h) => setStatus({ ok: true, version: h.model_version }))
      .catch(() => setStatus({ ok: false }));
  }, []);

  const statusText = status === null ? "connecting…"
    : status.ok ? `models live${status.version ? ` · ${status.version}` : ""}` : "api offline";

  return (
    <header className="topbar">
      <Link href="/" className="brand" aria-label="CreditCast — score an applicant">
        CREDITCAST<span className="brand-dot" aria-hidden="true" />
      </Link>

      <nav id="main-nav" data-tour="nav" className={`nav ${open ? "open" : ""}`} aria-label="Main">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} className={active ? "active" : ""} title={n.full}
              aria-current={active ? "page" : undefined}>
              {n.label}
              {n.ai && <span className="ai-tag" aria-label="AI">AI</span>}
            </Link>
          );
        })}
        <button type="button" className="nav-tour" onClick={() => { setOpen(false); startTour(); }}>
          ✦ Take the tour
        </button>
      </nav>

      <div className="topbar-right">
        <span className={`status-pill ${status?.ok === false ? "down" : ""}`} role="status"
          aria-label={`Scoring service: ${statusText}`}>
          <span className="dot" aria-hidden="true" />{statusText}
        </span>
        <button type="button" className="icon-btn tour-btn" onClick={startTour}
          aria-label="Take the guided tour" title="Take the guided tour">✦</button>
        <ThemeToggle compact />
        <button type="button" className="menu-btn" aria-expanded={open}
          aria-controls="main-nav" onClick={() => setOpen((o) => !o)}>
          {open ? "✕ Close" : "☰ Menu"}
        </button>
      </div>
    </header>
  );
}
