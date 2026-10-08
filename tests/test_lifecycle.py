"""End-to-end lifecycle (ROADMAP 2.3): run `creditcast.cli all` in-process on a
small synthetic book in a temp folder, then check every stage's outputs.

This is what CI does with the real 60k-loan config, but in-process, so the
pipeline, training, validation, governance, monitoring, gates and CLI code is
exercised by the test suite (and measured by coverage). `CREDITCAST_CONFIG`
points the whole app at a temp config; nothing in the repo is touched.
"""

import hashlib
import json
import os

import pytest
import yaml
from typer.testing import CliRunner

from creditcast import config as config_mod
from creditcast import dataset
from creditcast.config import DEFAULT_CONFIG_PATH, load_config

N_LOANS = 4000
REAL_CARD = DEFAULT_CONFIG_PATH.parent.parent / "governance" / "model_card.md"


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lifecycle")
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    dirs = ("bronze", "silver", "gold", "artifacts", "reports")
    raw["paths"] = {**{d: str(tmp / d) for d in dirs}, "model_card": str(tmp / "model_card.md")}
    raw["generator"]["n_loans"] = N_LOANS
    raw["tracking"] = {"enabled": False}
    for d in dirs:
        (tmp / d).mkdir()
    cfg_file = tmp / "config.yaml"
    cfg_file.write_text(yaml.safe_dump(raw), encoding="utf-8")

    real_card_before = _digest(REAL_CARD)
    previous = os.environ.get("CREDITCAST_CONFIG")
    os.environ["CREDITCAST_CONFIG"] = str(cfg_file)
    config_mod.reload()
    dataset.reload()
    try:
        from creditcast import cli

        result = CliRunner().invoke(cli.app, ["all"])
        yield {
            "tmp": tmp,
            "result": result,
            "cfg": load_config(),
            "cli": cli,
            "real_card_before": real_card_before,
        }
    finally:
        if previous is None:
            os.environ.pop("CREDITCAST_CONFIG", None)
        else:
            os.environ["CREDITCAST_CONFIG"] = previous
        config_mod.reload()
        dataset.reload()


def test_lifecycle_runs_to_the_gates(tiny):
    r = tiny["result"]
    assert r.exception is None or isinstance(r.exception, SystemExit), r.output
    # gates may pass or fail on a tiny book; either way the run must reach them
    assert r.exit_code in (0, 1), r.output
    assert "CI gates" in r.output


def test_every_stage_writes_its_outputs(tiny):
    art = tiny["tmp"] / "artifacts"
    for name in (
        "scorecard.joblib",
        "challenger.joblib",
        "lgd.joblib",
        "calibrator_scorecard.joblib",
        "calibrator_challenger.joblib",
        "test_scored.parquet",
        "calib_scored.parquet",
        "baseline.parquet",
        "train_metrics.json",
        "validation_report.json",
        "governance_report.json",
        "monitoring_report.json",
        "threshold_curve.json",
        "shap_global.json",
    ):
        assert (art / name).exists(), name
    assert (tiny["tmp"] / "reports" / "validation_report.html").exists()
    assert (tiny["tmp"] / "gold" / "feature_manifest.json").exists()
    assert (tiny["tmp"] / "gold" / "rate_benchmark.parquet").exists()
    assert (tiny["tmp"] / "model_card.md").read_text(encoding="utf-8").startswith("# Model Card")


def test_real_model_card_is_not_touched(tiny):
    assert _digest(REAL_CARD) == tiny["real_card_before"]


def test_reports_are_coherent(tiny):
    art = tiny["tmp"] / "artifacts"
    tm = json.loads((art / "train_metrics.json").read_text())
    val = json.loads((art / "validation_report.json").read_text())
    gov = json.loads((art / "governance_report.json").read_text())
    mon = json.loads((art / "monitoring_report.json").read_text())
    split = tm["split"]
    assert sum(split[k]["n"] for k in ("train", "valid", "calib", "test")) <= N_LOANS
    assert 0 < val["models"]["challenger"]["discrimination"]["gini"] <= 1
    assert val["loss_components"]["n_defaults"] > 0
    assert gov["decision"]["threshold_source"].startswith("calib")
    assert 0 <= gov["decision"]["approval_rate"] <= 1
    assert gov["fairness"]["groups"]
    assert isinstance(mon["healthy"], bool) and mon["n_batch"] == split["test"]["n"]


def test_gates_report_every_check(tiny):
    from creditcast.eval.gates import run_gates

    passed, results = run_gates(tiny["cfg"])
    assert isinstance(passed, bool)
    assert {r["check"].split(" ")[0] for r in results} >= {"Gini", "KS", "Calibration", "Max"}


def test_serving_scores_with_the_freshly_trained_models(tiny):
    from creditcast.serving import ModelBundle

    b = ModelBundle(tiny["cfg"])
    assert b.missing_artifacts() == []
    out = b.score(
        dict(
            fico=690,
            dti=38.0,
            ltv=82,
            orig_interest_rate=4.3,
            orig_upb=300000,
            orig_loan_term=360,
            occupancy_status="P",
            loan_purpose="N",
            property_type="CO",
            first_time_homebuyer="Y",
        )
    )
    assert out["decision"] in {"approve", "decline"} and 0 < out["pd"] < 1
    assert len(b.model_version["fingerprint"]) == 12


def test_cli_split_prints_four_slices(tiny):
    r = CliRunner().invoke(tiny["cli"].app, ["split"])
    assert r.exit_code == 0
    assert set(json.loads(r.output)) == {"train", "valid", "calib", "test"}


def test_passing_run_is_registered_and_listed(tiny):
    from creditcast.registry import active_version, list_versions

    versions = list_versions(tiny["cfg"])
    if tiny["result"].exit_code == 0:  # gates passed -> exactly one version
        assert [v["version"] for v in versions] == ["v0001"]
        assert versions[0]["gates_passed"] is True
        assert active_version(tiny["cfg"]) == "v0001"
        out = CliRunner().invoke(tiny["cli"].app, ["models", "list"])
        assert out.exit_code == 0 and "* v0001" in out.output
        use = CliRunner().invoke(tiny["cli"].app, ["models", "use", "v0001"])
        assert use.exit_code == 0 and "now serving v0001" in use.output
    else:  # gates failed -> nothing registered
        assert versions == [] and "not registering" in tiny["result"].output
    bad = CliRunner().invoke(tiny["cli"].app, ["models", "use", "v0042"])
    assert bad.exit_code == 1


def test_retraining_reproduces_identical_model_files(tiny):
    """Same data + seed + locked libraries -> byte-identical models, so a model
    fingerprint identifies the model rather than the moment it was trained."""
    from creditcast.registry import fingerprint

    art = tiny["cfg"].path("artifacts")
    before = fingerprint(art)
    r = CliRunner().invoke(tiny["cli"].app, ["train"])
    assert r.exit_code == 0, r.output
    assert fingerprint(art) == before
