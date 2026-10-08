"use client";
import { useState } from "react";
import { GLOSSARY, GLOSSARY_GROUPS } from "@/lib/glossary";
import { PageHead } from "@/components/ui";

export default function GlossaryPage() {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const entries = Object.entries(GLOSSARY).filter(([, g]) =>
    !query || `${g.term} ${g.short} ${g.long}`.toLowerCase().includes(query));

  return (
    <>
      <PageHead title="Glossary"
        subtitle="Every term in the cockpit, in plain language. The ⓘ icons across the app show the short version." />
      <input data-tour="glossary" className="search" type="search" placeholder="Search terms (e.g. PD, fairness, drift)…"
        aria-label="Search the glossary" value={q} onChange={(e) => setQ(e.target.value)} />

      {entries.length === 0 && <p className="muted">No terms match “{q}”.</p>}

      {GLOSSARY_GROUPS.map((group) => {
        const items = entries.filter(([, g]) => g.group === group);
        if (!items.length) return null;
        return (
          <section key={group} className="glossary-group">
            <h2>{group}</h2>
            <div className="grid cols-2">
              {items.map(([key, g]) => (
                <article key={key} id={key} className="card glossary-item">
                  <h4>{g.term}</h4>
                  <p>{g.short}</p>
                  <p className="muted">{g.long}</p>
                  {g.good && <p className="good">{g.good}</p>}
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </>
  );
}
