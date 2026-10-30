"""Copilot evaluation checks (ROADMAP 5.7): run without an LLM key, on fixed text."""

import yaml

from creditcast.eval.copilot_eval import (
    QUESTIONS,
    evaluate,
    numbers_in,
    states_fact,
    tool_numbers,
    ungrounded,
)

TOOLS = tool_numbers([
    {"gini": 0.43398, "ks": 0.3263, "el": 40636906.3, "el_rate_bps": 132.96, "approval_rate": 0.8209},
    {"groups": [{"group": "Black", "di": 0.8017}]},
])  # fmt: skip


def test_numbers_are_read_in_their_common_forms():
    got = [
        (n["value"], n["unit"])
        for n in numbers_in("Gini 0.434, approvals 82.1%, EL $40.6M, 133 bps, 12,780 loans")
    ]
    assert got == [(0.434, None), (82.1, "%"), (40.6, "M"), (133.0, "bps"), (12780.0, None)]


def test_facts_match_at_the_precision_written():
    assert states_fact("The Gini is 0.43.", 0.43398, tol=0.005)
    assert states_fact("About 43.4% Gini.", 0.43398, tol=0.005)
    assert states_fact("Expected loss is $40.6 million.", 40636906.3, rel=0.01)
    assert not states_fact("The Gini is 0.52.", 0.43398, tol=0.005)


def test_invented_figures_are_caught_and_real_ones_pass():
    answer = (
        "Gini is 0.434, KS 32.6%, EL $40.6M (133 bps); approval ratio 0.80 for Black applicants."
    )
    assert ungrounded(answer, "Is it fair?", TOOLS) == []
    assert ungrounded("The Gini is 0.61 and approvals 91%.", "q", TOOLS) == ["0.61", "91%"]


def test_question_numbers_and_small_counts_are_not_flagged():
    q = "Score FICO 650, DTI 46, LTV 93."
    assert ungrounded("For FICO 650 and DTI 46 the top 3 reasons are...", q, TOOLS) == []


def test_a_question_passes_only_with_every_fact_and_no_invention():
    exp = [{"path": "x:gini", "value": 0.43398, "tol": 0.005}]
    assert evaluate("Gini 0.434.", "q", exp, TOOLS)["passed"]
    assert not evaluate("Gini is strong.", "q", exp, TOOLS)["passed"]  # missing
    assert not evaluate("Gini 0.434, KS 0.71.", "q", exp, TOOLS)["passed"]  # invented


def test_question_file_is_well_formed():
    qs = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    assert len(qs) == 20 and len({q["id"] for q in qs}) == 20
    for q in qs:
        for e in q["expect"]:
            assert ":" in e["path"] and ("tol" in e or "rel_tol" in e)


def test_every_expected_fact_resolves_against_the_reports():
    import pytest

    from creditcast.config import load_config
    from creditcast.eval.copilot_eval import _lookup

    cfg = load_config()
    if not (cfg.path("artifacts") / "governance_report.json").exists():
        pytest.skip("run the pipeline first (python -m creditcast.cli all)")
    for q in yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))["questions"]:
        for e in q["expect"]:
            assert isinstance(_lookup(cfg, e["path"]), float)
