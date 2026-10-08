"use client";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { START_TOUR_EVENT } from "@/components/Tour";

const NAV = [
  { href: "/", label: "Score an applicant" },
  { href: "/portfolio", label: "Portfolio risk" },
  { href: "/validation", label: "Model quality" },
  { href: "/monitoring", label: "Stability & drift" },
  { href: "/governance", label: "Fairness & explanations" },
  { href: "/copilot", label: "Risk Copilot", accent: true },
  { href: "/glossary", label: "Glossary" },
];

export default function Sidebar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);          // mobile menu
  useEffect(() => setOpen(false), [path]);          // close after navigating

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <span className="name">CreditCast</span>
          <span className="tag">Mortgage credit-risk cockpit</span>
        </div>
        <button type="button" className="menu-btn" aria-expanded={open}
          aria-controls="main-nav" onClick={() => setOpen((o) => !o)}>
          {open ? "✕ Close" : "☰ Menu"}
        </button>
      </div>
      <nav id="main-nav" data-tour="nav" className={`nav ${open ? "open" : ""}`} aria-label="Main">
        {NAV.map((n) => {
          const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link key={n.href} href={n.href} className={active ? "active" : ""}
              aria-current={active ? "page" : undefined}
              style={n.accent && !active ? { color: "var(--accent)" } : undefined}>
              <span className="dot" /> {n.label}
              {n.accent && <span style={{ marginLeft: "auto", fontSize: 9, opacity: .8,
                border: "1px solid currentColor", borderRadius: 5, padding: "1px 5px",
                letterSpacing: ".5px" }}>AI</span>}
            </Link>
          );
        })}
        <button type="button" className="theme-toggle"
          onClick={() => { setOpen(false); window.dispatchEvent(new Event(START_TOUR_EVENT)); }}>
          ✦ Take the tour
        </button>
        <ThemeToggle />
      </nav>
      <div className="sidebar-foot small muted">
        Tested on loans it never saw<br />(out-of-time validation)
      </div>
    </aside>
  );
}
