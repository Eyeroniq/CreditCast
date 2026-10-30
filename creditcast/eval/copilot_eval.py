"""Risk Copilot evaluation suite (ROADMAP 5.7).

Asks the real agent team every question in `tests/eval/copilot_questions.yaml`
and checks two things in each answer:

1. **Facts:** every expected figure (read from the current artifacts) appears,
   in any common form: 0.434, 43.4%, 37.2M, $37,204,643...
2. **Grounding:** every other number in the answer can be traced to a tool
   output from that conversation (allowing rounding, percent and K/M/B forms),
   so the model can't invent figures. Numbers from the question itself, list
   markers and small counts (up to 12) are ignored.

A question passes when both hold. The run passes at `pass_rate >= 0.90`, and
each run is appended to `reports/copilot_eval_history.jsonl` so the rate can be
tracked over time. Needs GROQ_API_KEY; the nightly workflow skips without it.

    python -m creditcast.eval.copilot_eval
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import UTC, datetime
from typing import Any

import yaml

from creditcast.config import REPO_ROOT, Config, load_config

QUESTIONS = REPO_ROOT / "tests" / "eval" / "copilot_questions.yaml"
PASS_RATE = 0.90

_NUM = re.compile(
    r"(?<![\w.])[-−]?\$?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(%|bps|k|K|M|B|million|billion|thousand)?(?![\w])"
)
_SCALE = {"k": 1e3, "K": 1e3, "thousand": 1e3, "M": 1e6, "million": 1e6, "B": 1e9, "billion": 1e9}


def numbers_in(text: str) -> list[dict]:
    """Every number in `text` with its value, decimals and unit."""
    out = []
    for m in _NUM.finditer(text):
        whole, frac, unit = m.group(1), m.group(2), m.group(3)
        value = float(whole.replace(",", "") + ("." + frac if frac else ""))
        if m.group(0).lstrip().startswith(("-", "−")):
            value = -value
        out.append(
            {"value": value, "decimals": len(frac or ""), "unit": unit, "text": m.group(0).strip()}
        )
    return out


def _forms(n: dict) -> list[float]:
    """The plain values a written number could stand for."""
    v, unit = n["value"], n["unit"]
    if unit == "%":
        return [v / 100, v]
    if unit == "bps":
        return [v, v / 1e4]
    if unit in _SCALE:
        return [v * _SCALE[unit]]
    return [v, v / 100]  # "43.4" may be a percentage written without the sign


def _close(written: dict, form: float, target: float, tol: float | None, rel: float | None) -> bool:
    if rel is not None:
        return abs(form - target) <= rel * max(abs(target), 1e-12)
    if tol is not None:
        # also allow the precision the answer was written at
        shown = 0.5 * 10 ** (-written["decimals"]) * (0.01 if written["unit"] == "%" else 1)
        return abs(form - target) <= max(tol, shown)
    return False


def states_fact(
    answer: str, value: float, tol: float | None = None, rel: float | None = None
) -> bool:
    return any(_close(n, f, value, tol, rel) for n in numbers_in(answer) for f in _forms(n))


def tool_numbers(results: list[Any]) -> list[float]:
    vals: list[float] = []

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)) and math.isfinite(x):
            vals.append(float(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            vals.extend(n["value"] for n in numbers_in(x))

    walk(results)
    return vals


def ungrounded(answer: str, question: str, tool_values: list[float]) -> list[str]:
    """Numbers in the answer that no tool output (or the question) supports."""
    asked = {n["value"] for n in numbers_in(question)}
    bad = []
    for n in numbers_in(answer):
        if n["value"] in asked or (
            n["decimals"] == 0 and n["unit"] is None and abs(n["value"]) <= 12
        ):
            continue
        ok = any(
            _close(n, f, t, tol=0.0, rel=None) or (abs(t) >= 1000 and _close(n, f, t, None, 0.01))
            for f in _forms(n)
            for t in tool_values
        )
        if not ok:
            bad.append(n["text"])
    return bad


def _lookup(cfg: Config, path: str) -> float:
    file, key = path.split(":")
    key = key.replace("{champion}", str(cfg.decision.champion))
    node: Any = json.loads((cfg.path("artifacts") / file).read_text())
    for part in key.split("."):
        node = node[part]
    return float(node)


def evaluate(answer: str, question: str, expected: list[dict], tool_values: list[float]) -> dict:
    missing = [
        e["path"]
        for e in expected
        if not states_fact(answer, e["value"], e.get("tol"), e.get("rel_tol"))
    ]
    invented = ungrounded(answer, question, tool_values)
    return {"passed": not missing and not invented, "missing": missing, "invented": invented}


def run_suite(cfg: Config | None = None) -> dict:
    from creditcast.agents import llm, orchestrator, tools

    cfg = cfg or load_config()
    llm.ensure_configured()
    spec = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    results = []
    original = tools.call_tool
    for q in spec:
        captured: list[Any] = []

        def capture(name, args, _orig=original, _sink=captured):
            out = _orig(name, args)
            _sink.append(json.loads(json.dumps(out, default=str)))
            return out

        tools.call_tool = capture
        try:
            answer = orchestrator.run(q["question"])["answer"]
            expected = [{**e, "value": _lookup(cfg, e["path"])} for e in q.get("expect", [])]
            verdict = evaluate(answer, q["question"], expected, tool_numbers(captured))
        except Exception as e:  # a crash is a failed question, not a crashed suite
            answer, verdict = "", {"passed": False, "missing": [], "invented": [], "error": str(e)}
        finally:
            tools.call_tool = original
        results.append({"id": q["id"], **verdict, "answer": answer})

    rate = sum(r["passed"] for r in results) / len(results)
    run = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": str(cfg.agents.model),
        "data_version": str(cfg.run.data_version),
        "questions": len(results),
        "passed": sum(r["passed"] for r in results),
        "pass_rate": rate,
        "target": PASS_RATE,
    }
    reports = cfg.path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "copilot_eval_latest.json").write_text(
        json.dumps({**run, "results": results}, indent=2)
    )
    with open(reports / "copilot_eval_history.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(run) + "\n")
    return {**run, "results": results}


def main() -> int:
    from creditcast.agents.llm import LLMNotConfigured

    try:
        r = run_suite()
    except LLMNotConfigured as e:
        print(f"[copilot-eval] skipped: {e}")
        return 0
    for q in r["results"]:
        mark = "PASS" if q["passed"] else "FAIL"
        why = q.get("error") or ", ".join(
            [f"missing {m}" for m in q["missing"]] + [f"invented {x}" for x in q["invented"]]
        )
        print(f"  [{mark}] {q['id']:<24} {why}")
    print(
        f"\n  pass rate {r['pass_rate']:.0%} ({r['passed']}/{r['questions']}), target {PASS_RATE:.0%}"
    )
    return 0 if r["pass_rate"] >= PASS_RATE else 1


if __name__ == "__main__":
    sys.exit(main())
