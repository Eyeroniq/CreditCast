"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { PageHead, Pill, VerdictBanner } from "@/components/ui";
import { copilotVerdict } from "@/lib/verdicts";
import AgentChart from "@/components/AgentChart";

// First question is one click away (6.2.8).
const SUGGESTIONS = [
  "Is the model fair?",
  "Which segment drives most loss?",
  "Why would FICO 645, DTI 47%, LTV 94%, investment property, cash-out be declined?",
  "Is the model valid? Show Gini and calibration.",
  "Why is the 2021 vintage riskier, and is the model still stable?",
  "Summarize the portfolio's risk and expected loss",
];

// Chat history survives a reload; storage can be blocked, so never rely on it.
const HISTORY_KEY = "cc-copilot-history";
const MAX_SAVED = 30;
function loadHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch { return []; }
}
function saveHistory(messages) {
  try {
    const done = messages.filter((m) => !m.pending);
    if (done.length) localStorage.setItem(HISTORY_KEY, JSON.stringify(done.slice(-MAX_SAVED)));
    else localStorage.removeItem(HISTORY_KEY);
  } catch { /* storage blocked: history just isn't kept */ }
}

// minimal markdown: **bold**, bullets, paragraphs
function RichText({ text }) {
  const blocks = (text || "").split("\n");
  return (
    <div className="rich">
      {blocks.map((ln, i) => {
        const bullet = /^\s*[-*]\s+/.test(ln);
        const html = ln.replace(/^\s*[-*]\s+/, "")
          .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
          .replace(/`(.+?)`/g, "<code>$1</code>");
        if (!ln.trim()) return <div key={i} className="rich-gap" />;
        return bullet
          ? <div key={i} className="rich-bullet">
              <span className="accent" aria-hidden="true">•</span>
              <span dangerouslySetInnerHTML={{ __html: html }} />
            </div>
          : <p key={i} dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </div>
  );
}

function AgentChips({ team, active }) {
  return (
    <div className="chips">
      {team.map((a) => {
        const on = active?.some((x) => x.specialist === a.id);
        return (
          <span key={a.id} className={`pill ${on ? "ok" : "neutral"}`}
            title={a.tools.join(", ")}>{a.title}{on ? " ✓" : ""}</span>
        );
      })}
    </div>
  );
}

/** "How I got this": which specialist called which tool, with what. */
function Trace({ trace }) {
  if (!trace?.length) return null;
  return (
    <details className="more trace">
      <summary>How I got this · {trace.length} tool call{trace.length > 1 ? "s" : ""}</summary>
      <ol className="trace-list mono small">
        {trace.map((t, i) => (
          <li key={i}>
            <span className="accent">{t.agent}</span>
            <span className="muted"> → </span>{t.tool}
            <span className="muted">({Object.entries(t.args || {}).map(([k, v]) => `${k}=${v}`).join(", ")})</span>
            {t.chart && <span className="ok"> ▣ chart</span>}
          </li>
        ))}
      </ol>
    </details>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard blocked: nothing to do */ }
  };
  return (
    <button type="button" className="link-btn" onClick={copy} aria-live="polite">
      {copied ? "✓ Copied" : "Copy answer"}
    </button>
  );
}

/** Live progress while the specialists work: one row per agent. */
function Progress({ steps }) {
  if (!steps.length) return <p className="small muted progress-row"><span className="spinner" aria-hidden="true" />Routing your question…</p>;
  return (
    <ul className="progress-list small">
      {steps.map((s) => (
        <li key={s.specialist} className={s.status}>
          {s.status === "done" ? <span className="ok" aria-hidden="true">✓</span>
            : s.status === "working" ? <span className="spinner" aria-hidden="true" />
            : <span className="muted" aria-hidden="true">○</span>}
          {s.title}{s.status === "working" ? " is calling tools…" : s.status === "done" ? " finished" : " (queued)"}
        </li>
      ))}
    </ul>
  );
}

/** Counts down a rate-limit wait, then calls onDone. */
function Countdown({ until, onDone }) {
  const [left, setLeft] = useState(Math.max(0, Math.ceil((until - Date.now()) / 1000)));
  useEffect(() => {
    const t = setInterval(() => {
      const s = Math.max(0, Math.ceil((until - Date.now()) / 1000));
      setLeft(s);
      if (s === 0) { clearInterval(t); onDone(); }
    }, 1000);
    return () => clearInterval(t);
  }, [until, onDone]);
  return <span className="mono">{left}s</span>;
}

function Message({ m, team }) {
  if (m.role === "user") {
    return <div className="msg user"><div className="bubble">{m.text}</div></div>;
  }
  return (
    <div className="msg assistant" aria-busy={m.pending || undefined}>
      {m.agents?.length > 0 && <AgentChips team={team} active={m.agents} />}
      {m.pending && <Progress steps={m.steps} />}
      {m.error ? (
        <div className="bad"><RichText text={m.text} /></div>
      ) : m.pending ? (
        m.sections.map((s) => (
          <div key={s.title} className="section-in">
            {m.steps.length > 1 && <p><b>{s.title}</b></p>}
            <RichText text={s.text} />
          </div>
        ))
      ) : (
        <RichText text={m.text} />
      )}
      {m.charts?.map((c) => <AgentChart key={c.id} spec={c} />)}
      {!m.pending && !m.error && (
        <div className="msg-actions">
          <CopyButton text={m.text} />
        </div>
      )}
      {!m.pending && <Trace trace={m.trace} />}
    </div>
  );
}

export default function CopilotPage() {
  const [team, setTeam] = useState([]);
  const [ready, setReady] = useState(null);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(null);   // epoch ms until the rate limit lifts
  const endRef = useRef(null);
  const inflight = useRef(null);

  useEffect(() => {
    setMessages(loadHistory());
    api.agentTeam().then((t) => { setTeam(t.agents); setReady(t.llm_ready); setModel(t.model); })
      .catch(() => setReady(false));
    return () => inflight.current?.abort();
  }, []);
  useEffect(() => { saveHistory(messages); }, [messages]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [messages]);

  // Update the in-progress answer (always the last message); a no-op once it's
  // finished or the chat was cleared, so late events can't land anywhere else.
  const patchLast = (fn) => setMessages((ms) => {
    const last = ms[ms.length - 1];
    return last?.pending ? [...ms.slice(0, -1), fn(last)] : ms;
  });

  const ask = async (q) => {
    const question = (q ?? input).trim();
    if (!question || busy || cooldown) return;
    setInput("");
    setMessages((ms) => [...ms, { role: "user", text: question },
      { role: "assistant", pending: true, steps: [], sections: [], charts: [] }]);
    setBusy(true);
    const ctrl = new AbortController();
    inflight.current = ctrl;
    try {
      await api.agentChatStream(question, {
        signal: ctrl.signal,
        onEvent: (ev) => {
          if (ev.type === "plan") {
            patchLast((m) => ({ ...m, steps: ev.agents.map((a) => ({ ...a, status: "queued" })) }));
          } else if (ev.type === "agent_start") {
            patchLast((m) => ({ ...m, steps: m.steps.map((s) =>
              s.specialist === ev.specialist ? { ...s, status: "working" } : s) }));
          } else if (ev.type === "agent_done") {
            patchLast((m) => ({ ...m,
              steps: m.steps.map((s) => (s.specialist === ev.specialist ? { ...s, status: "done" } : s)),
              sections: [...m.sections, { title: ev.title, text: ev.text }],
              charts: [...m.charts, ...ev.charts] }));
          } else if (ev.type === "done") {
            patchLast(() => ({ role: "assistant", text: ev.answer, agents: ev.agents,
              charts: ev.charts, trace: ev.trace }));
          } else if (ev.type === "error") {
            patchLast(() => ({ role: "assistant", error: true, text: ev.detail }));
          }
        },
      });
      // The connection closed without a final event (e.g. a proxy timeout).
      patchLast(() => ({ role: "assistant", error: true,
        text: "The answer was cut off before it finished. Please ask again." }));
    } catch (e) {
      if (e.name === "AbortError") return;
      if (e.kind === "busy") setCooldown(Date.now() + (e.retryAfter || 60) * 1000);
      if (e.kind === "unavailable") setReady(false);
      patchLast(() => ({ role: "assistant", error: true, text: e.message }));
    } finally {
      if (inflight.current === ctrl) setBusy(false);
    }
  };

  const newChat = () => { inflight.current?.abort(); setBusy(false); setMessages([]); };
  const blocked = busy || ready === false || Boolean(cooldown);

  return (
    <>
      <PageHead title="Risk Copilot"
        subtitle="Ask the specialist agent team — they call the real PD/LGD/EL tools and answer with live charts." />
      <VerdictBanner verdict={copilotVerdict(ready)} />

      <div className="card copilot-team">
        <div className="card-head">
          <h3>Agent team</h3>
          <span className="small mono muted">
            {ready === null ? "…" : ready
              ? <>orchestrator · {model} <Pill status={true}>online</Pill></>
              : <Pill status={false}>LLM key not set</Pill>}
          </span>
        </div>
        <AgentChips team={team} active={null} />
        {ready === false && (
          <p className="small muted">
            To switch the agents on, create a free key at{" "}
            <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer">console.groq.com</a>{" "}
            and set <span className="mono">GROQ_API_KEY</span> on the server. The charts and metrics
            on every other page work without it.
          </p>
        )}
      </div>

      <div className="card chat">
        <div className="card-head">
          <h3>Conversation</h3>
          {messages.length > 0 && (
            <button type="button" className="chip" onClick={newChat}>＋ New chat</button>
          )}
        </div>
        {messages.length === 0 && (
          <div className="muted">
            <p>Try one of these — each answer comes from the agents calling real tools, with charts:</p>
            <div className="chips" role="group" aria-label="Suggested questions">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => ask(s)} disabled={blocked}>{s}</button>
              ))}
            </div>
          </div>
        )}

        <div className="messages" aria-live="polite">
          {messages.map((m, i) => <Message key={i} m={m} team={team} />)}
        </div>
        {cooldown && (
          <p className="small warn" role="status">
            Too many questions in a short time. You can ask again in{" "}
            <Countdown until={cooldown} onDone={() => setCooldown(null)} />.
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form data-tour="copilot" className="ask-row" onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <label htmlFor="copilot-q" className="sr-only">Ask the risk team</label>
        <input id="copilot-q" placeholder="Ask the risk team… (e.g. what drives expected loss in the book?)"
          value={input} onChange={(e) => setInput(e.target.value)} disabled={blocked} />
        <button type="submit" className="primary" disabled={blocked || !input.trim()}>
          {busy ? "…" : "Ask"}
        </button>
      </form>
    </>
  );
}
