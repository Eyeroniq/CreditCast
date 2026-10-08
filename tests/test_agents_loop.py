"""Risk Copilot orchestration with a scripted fake LLM (ROADMAP 2.3): routing,
the tool-calling loop, chart collection, fallbacks — no Groq key needed."""

import json
from types import SimpleNamespace as NS

import pytest

from creditcast.agents import llm, orchestrator
from creditcast.config import load_config

ART = load_config().path("artifacts")
needs_artifacts = pytest.mark.skipif(
    not (ART / "test_scored.parquet").exists(),
    reason="run the pipeline first (python -m creditcast.cli all)",
)


def reply(text=None, tool=None, args="{}"):
    calls = None
    if tool:
        calls = [NS(id="call_1", function=NS(name=tool, arguments=args))]
    return NS(choices=[NS(message=NS(content=text, tool_calls=calls))])


class Script:
    """Stands in for llm.complete: routing call first, then the tool loop."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, messages, tool_names=None, temperature=None, tool_choice="auto"):
        self.calls.append(
            {"tools": tool_names, "choice": tool_choice, "last": messages[-1]["role"]}
        )
        return self.responses.pop(0)


@needs_artifacts
def test_question_is_routed_tools_called_and_charts_returned(monkeypatch):
    script = Script(
        reply(json.dumps({"plan": [{"specialist": "analyst", "task": "Summarize the book"}]})),
        reply(tool="portfolio_summary"),
        reply("Expected loss is concentrated in grades BB and B (see the chart)."),
    )
    monkeypatch.setattr(llm, "complete", script)
    out = orchestrator.run("How risky is the portfolio?")
    assert "grades BB and B" in out["answer"]
    assert out["agents"] == [{"specialist": "analyst", "title": "Portfolio Analyst"}]
    assert [t["tool"] for t in out["trace"]] == ["portfolio_summary"]
    assert out["charts"] and out["charts"][0]["type"] in {"bar", "hbar", "line", "scatter"}
    # the first tool-loop call forces a tool (grounding), later ones are free
    assert script.calls[1]["choice"] == "required" and script.calls[2]["choice"] == "auto"
    # the tool result went back to the model as a `tool` message
    assert script.calls[2]["last"] == "tool"


@needs_artifacts
def test_multiple_specialists_are_composed_under_headings(monkeypatch):
    script = Script(
        reply(
            json.dumps(
                {
                    "plan": [
                        {"specialist": "analyst", "task": "a"},
                        {"specialist": "validator", "task": "b"},
                    ]
                }
            )
        ),
        reply(tool="portfolio_summary"),
        reply("Book answer."),
        reply(tool="validation_metrics"),
        reply("Model passes."),
    )
    monkeypatch.setattr(llm, "complete", script)
    out = orchestrator.run("Is the book risky and is the model valid?")
    assert "**Portfolio Analyst**" in out["answer"] and "**Model Validator**" in out["answer"]
    assert {a["specialist"] for a in out["agents"]} == {"analyst", "validator"}


def test_greeting_gets_a_direct_reply_without_tools(monkeypatch):
    monkeypatch.setattr(
        llm,
        "complete",
        Script(reply(json.dumps({"plan": [], "direct": "Hi! Ask me about the portfolio."}))),
    )
    out = orchestrator.run("hello")
    assert out["answer"].startswith("Hi!") and out["trace"] == [] and out["charts"] == []


@needs_artifacts
def test_unparseable_routing_falls_back_to_the_analyst(monkeypatch):
    monkeypatch.setattr(
        llm,
        "complete",
        Script(
            reply("I think the analyst should handle this"),  # not JSON
            reply(tool="portfolio_summary"),
            reply("Fallback answer."),
        ),
    )
    out = orchestrator.run("what's up with the book")
    assert out["answer"] == "Fallback answer."


def test_unknown_specialists_are_dropped_and_capped(monkeypatch):
    plan = {"plan": [{"specialist": "astrologer", "task": "x"}]}
    monkeypatch.setattr(llm, "complete", Script(reply(json.dumps(plan))))
    out = orchestrator.run("read my stars")
    assert out["agents"] == [] and "credit-risk platform" in out["answer"]


@needs_artifacts
def test_tool_loop_stops_at_the_iteration_cap(monkeypatch):
    cap = 2
    script = Script(
        reply(tool="portfolio_summary"),
        reply(tool="top_exposures", args='{"n": 3}'),
        reply("Final summary."),
    )
    monkeypatch.setattr(llm, "complete", script)
    out = llm.run_tool_loop(
        "system", "keep calling tools", ["portfolio_summary", "top_exposures"], max_iters=cap
    )
    assert out["text"] == "Final summary."
    assert len(out["trace"]) == cap
    assert script.calls[-1]["tools"] is None  # final synthesis has no tools


@needs_artifacts
def test_malformed_tool_arguments_are_tolerated(monkeypatch):
    monkeypatch.setattr(
        llm, "complete", Script(reply(tool="portfolio_summary", args="not json"), reply("ok"))
    )
    out = llm.run_tool_loop("s", "u", ["portfolio_summary"])
    assert out["trace"][0]["args"] == {}


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.LLMNotConfigured, match="GROQ_API_KEY"):
        llm._client()


def test_rate_limit_falls_back_to_the_lighter_model(monkeypatch):
    import httpx
    from groq import RateLimitError

    used = []

    class FakeCompletions:
        def create(self, model, **kw):
            used.append(model)
            if model != llm.FALLBACK_MODEL:
                resp = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com"))
                raise RateLimitError("rate limited", response=resp, body=None)
            return reply("from fallback")

    monkeypatch.setattr(llm, "_client", lambda: NS(chat=NS(completions=FakeCompletions())))
    monkeypatch.setenv("CF_AGENT_MODEL", "big-model")
    out = llm.complete([{"role": "user", "content": "hi"}])
    assert used == ["big-model", llm.FALLBACK_MODEL]
    assert out.choices[0].message.content == "from fallback"
