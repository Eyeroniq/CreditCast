"""Model registry (ROADMAP 2.5): register, de-duplicate, list, roll back."""

import copy
import json

import pytest

from creditcast import registry
from creditcast.config import Config, load_config

MODEL_FILES = registry.FINGERPRINTED


@pytest.fixture()
def cfg(tmp_path):
    c = Config(copy.deepcopy(dict(load_config())))
    c["paths"] = {
        **c["paths"],
        "artifacts": str(tmp_path / "artifacts"),
        "gold": str(tmp_path / "gold"),
        "model_card": str(tmp_path / "model_card.md"),
    }
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "gold").mkdir()
    return c


def write_run(cfg, tag: str, extra_report: bool = True):
    """Fake one training run's outputs; `tag` changes the model bytes."""
    art, gold = cfg.path("artifacts"), cfg.path("gold")
    for name in MODEL_FILES:
        (art / name).write_text(f"{name}:{tag}")
    (art / "validation_report.json").write_text(
        json.dumps(
            {
                "champion": "challenger",
                "models": {
                    "challenger": {
                        "discrimination": {"gini": 0.42, "ks": 0.3},
                        "calibration": {"max_band_error": 0.01},
                    }
                },
            }
        )
    )
    (art / "governance_report.json").write_text(
        json.dumps(
            {
                "decision": {"threshold": 0.0625, "approval_rate": 0.8},
                "fairness": {"di_ratio_min_observed": 0.81},
            }
        )
    )
    if extra_report:
        (art / f"only_in_{tag}.json").write_text("{}")
    (gold / "feature_manifest.json").write_text(json.dumps({"tag": tag}))
    (gold / "rate_benchmark.parquet").write_text(f"bench:{tag}")
    cfg.path("model_card").write_text(f"# Model Card {tag}")


def test_register_snapshots_everything_and_activates(cfg):
    write_run(cfg, "a")
    m = registry.register(cfg, gates_passed=True, note="first")
    assert m["version"] == "v0001" and m["gates_passed"] is True and m["note"] == "first"
    assert m["metrics"]["gini"] == 0.42 and m["metrics"]["approval_rate"] == 0.8
    assert len(m["fingerprint"]) == 12 and m["git_sha"]
    snap = registry.registry_root(cfg) / "v0001"
    for name in MODEL_FILES:
        assert (snap / name).read_text() == f"{name}:a"
    assert json.loads((snap / "gold" / "feature_manifest.json").read_text()) == {"tag": "a"}
    assert (snap / "model_card.md").read_text() == "# Model Card a"
    assert registry.active_version(cfg) == "v0001"


def test_identical_models_are_not_registered_twice(cfg):
    write_run(cfg, "a")
    first = registry.register(cfg)
    again = registry.register(cfg)
    assert again["version"] == first["version"] and again["reused"] is True
    assert [v["version"] for v in registry.list_versions(cfg)] == ["v0001"]


def test_new_models_get_the_next_version(cfg):
    write_run(cfg, "a")
    registry.register(cfg)
    write_run(cfg, "b")
    m = registry.register(cfg)
    assert (
        m["version"] == "v0002"
        and m["fingerprint"] != registry.list_versions(cfg)[0]["fingerprint"]
    )
    assert registry.active_version(cfg) == "v0002"


def test_rollback_restores_files_and_removes_newer_ones(cfg):
    write_run(cfg, "a")
    v1 = registry.register(cfg)
    write_run(cfg, "b")
    registry.register(cfg)
    art = cfg.path("artifacts")
    assert (art / "only_in_b.json").exists()

    m = registry.activate("v0001", cfg)
    assert m["version"] == "v0001" and registry.active_version(cfg) == "v0001"
    assert registry.fingerprint(art) == v1["fingerprint"]
    assert (art / "scorecard.joblib").read_text() == "scorecard.joblib:a"
    assert not (art / "only_in_b.json").exists()  # newer-only file removed
    assert (art / "only_in_a.json").exists()
    assert json.loads((cfg.path("gold") / "feature_manifest.json").read_text()) == {"tag": "a"}
    assert cfg.path("model_card").read_text() == "# Model Card a"

    registry.activate("v0002", cfg)  # and forward again
    assert (art / "scorecard.joblib").read_text() == "scorecard.joblib:b"


def test_unknown_version_is_a_clear_error(cfg):
    write_run(cfg, "a")
    registry.register(cfg)
    with pytest.raises(registry.RegistryError, match="v0001"):
        registry.activate("v0099", cfg)


def test_cannot_register_without_trained_models(cfg):
    with pytest.raises(registry.RegistryError, match="train first"):
        registry.register(cfg)


def test_tampered_snapshot_is_detected(cfg):
    write_run(cfg, "a")
    registry.register(cfg)
    (registry.registry_root(cfg) / "v0001" / "lgd.joblib").write_text("tampered")
    with pytest.raises(registry.RegistryError, match="fingerprint"):
        registry.activate("v0001", cfg)


def test_health_reports_the_served_version():
    from fastapi.testclient import TestClient

    from app.api.main import app

    body = TestClient(app).get("/api/health").json()
    assert {"status", "git_sha", "model_version"} <= body.keys()
