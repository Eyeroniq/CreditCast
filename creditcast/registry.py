"""Model registry — numbered, immutable snapshots of trained models (ROADMAP 2.5).

After a lifecycle run passes its gates, `register()` copies everything the
scoring service needs — the model files, calibrators, reports, the feature
manifest and rate benchmark the models were trained with, and the model card —
into `artifacts/registry/v0001/`, `v0002/`, … with a `manifest.json` holding the
version id, git commit, run stamp, model fingerprint and headline metrics.

`activate(version)` copies a snapshot back into the working locations, so
rolling back is one command (`python -m creditcast.cli models use v0003`) or
one config value (`serving.pinned_version`, applied when the API starts).
The serving code itself never changes: it always reads the working artifacts.

Re-registering a run whose model files are byte-identical to the latest
version returns that version instead of creating a duplicate.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from creditcast.config import Config, git_sha, load_config, run_stamp

REGISTRY_DIR = "registry"
ACTIVE_FILE = "active.json"
# Files from the gold layer the models depend on (snapshot alongside them).
GOLD_FILES = ["feature_manifest.json", "rate_benchmark.parquet"]
# Model files whose bytes identify a version (same list as serving's fingerprint).
FINGERPRINTED = [
    "scorecard.joblib",
    "challenger.joblib",
    "calibrator_scorecard.joblib",
    "calibrator_challenger.joblib",
    "lgd.joblib",
]
_VERSION_RE = re.compile(r"^v(\d{4})$")


class RegistryError(RuntimeError):
    pass


def _version_number(version: str) -> int:
    m = _VERSION_RE.match(version)
    if not m:
        raise RegistryError(f"malformed version id {version!r}")
    return int(m.group(1))


def registry_root(cfg: Config) -> Path:
    return cfg.path("artifacts") / REGISTRY_DIR


def fingerprint(artifacts: Path) -> str:
    h = hashlib.sha256()
    for name in FINGERPRINTED:
        h.update((artifacts / name).read_bytes())
    return h.hexdigest()[:12]


def list_versions(cfg: Config | None = None) -> list[dict]:
    """All registered versions, oldest first (each one's manifest)."""
    cfg = cfg or load_config()
    root = registry_root(cfg)
    if not root.exists():
        return []
    out = []
    for d in sorted(root.iterdir()):
        if d.is_dir() and _VERSION_RE.match(d.name) and (d / "manifest.json").exists():
            out.append(json.loads((d / "manifest.json").read_text()))
    return out


def active_version(cfg: Config | None = None) -> str | None:
    cfg = cfg or load_config()
    f = registry_root(cfg) / ACTIVE_FILE
    return json.loads(f.read_text())["version"] if f.exists() else None


def _metrics(artifacts: Path) -> dict:
    """Headline numbers for the manifest (best-effort: missing reports are skipped)."""

    def load(name: str) -> dict:
        p = artifacts / name
        return json.loads(p.read_text()) if p.exists() else {}

    tm, val, gov = (
        load("train_metrics.json"),
        load("validation_report.json"),
        load("governance_report.json"),
    )
    champ = val.get("champion", "challenger")
    m = val.get("models", {}).get(champ, {})
    return {
        "champion": champ,
        "gini": m.get("discrimination", {}).get("gini"),
        "ks": m.get("discrimination", {}).get("ks"),
        "calibration_max_band_error": m.get("calibration", {}).get("max_band_error"),
        "threshold": gov.get("decision", {}).get("threshold"),
        "approval_rate": gov.get("decision", {}).get("approval_rate"),
        "min_disparate_impact": gov.get("fairness", {}).get("di_ratio_min_observed"),
        "el_rate_bps": tm.get("expected_loss", {}).get("el_rate_bps"),
    }


def register(cfg: Config | None = None, gates_passed: bool | None = None, note: str = "") -> dict:
    """Snapshot the current working artifacts as a new version (or return the
    latest version if the model files are byte-identical to it)."""
    cfg = cfg or load_config()
    art, gold = cfg.path("artifacts"), cfg.path("gold")
    missing = [n for n in FINGERPRINTED if not (art / n).exists()]
    if missing:
        raise RegistryError(f"nothing to register — missing {missing}; train first")

    fp = fingerprint(art)
    versions = list_versions(cfg)
    if versions and versions[-1]["fingerprint"] == fp:
        return {**versions[-1], "reused": True}

    n = _version_number(versions[-1]["version"]) + 1 if versions else 1
    version = f"v{n:04d}"
    dest = registry_root(cfg) / version
    (dest / "gold").mkdir(parents=True)
    files = []
    for f in sorted(art.iterdir()):
        if f.is_file() and f.name != ".gitkeep":
            shutil.copy2(f, dest / f.name)
            files.append(f.name)
    for name in GOLD_FILES:
        if (gold / name).exists():
            shutil.copy2(gold / name, dest / "gold" / name)
    card = cfg.path("model_card") if "model_card" in cfg["paths"] else None
    if card and card.exists():
        shutil.copy2(card, dest / "model_card.md")

    manifest = {
        "version": version,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": git_sha(),
        "stamp": run_stamp(),
        "fingerprint": fp,
        "gates_passed": gates_passed,
        "note": note,
        "metrics": _metrics(art),
        "files": files,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2, default=float))
    _set_active(cfg, version)
    return manifest


def _set_active(cfg: Config, version: str) -> None:
    (registry_root(cfg) / ACTIVE_FILE).write_text(
        json.dumps({"version": version, "since": datetime.now(UTC).isoformat(timespec="seconds")})
    )


def activate(version: str, cfg: Config | None = None) -> dict:
    """Make `version` the served model: restore its files into the working
    artifacts (removing files that version didn't have) and the gold layer."""
    cfg = cfg or load_config()
    src = registry_root(cfg) / version
    if not (src / "manifest.json").exists():
        known = ", ".join(v["version"] for v in list_versions(cfg)) or "none"
        raise RegistryError(f"unknown model version {version!r} (registered: {known})")
    manifest = json.loads((src / "manifest.json").read_text())
    art, gold = cfg.path("artifacts"), cfg.path("gold")
    art.mkdir(parents=True, exist_ok=True)
    gold.mkdir(parents=True, exist_ok=True)

    keep = set(manifest["files"]) | {".gitkeep"}
    for f in art.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()
    for name in manifest["files"]:
        shutil.copy2(src / name, art / name)
    for f in (src / "gold").iterdir():
        shutil.copy2(f, gold / f.name)
    if (src / "model_card.md").exists() and "model_card" in cfg["paths"]:
        shutil.copy2(src / "model_card.md", cfg.path("model_card"))

    if fingerprint(art) != manifest["fingerprint"]:
        raise RegistryError(f"restored files for {version} do not match its fingerprint")
    _set_active(cfg, version)
    return manifest
