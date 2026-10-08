"""Central config + run-stamp utilities.

Every module reads thresholds/paths from `conf/config.yaml` via `load_config()`.
This keeps the "no hardcoding" discipline (Part 10.7) and makes every run
reproducible: seed, data_version, and code_version travel together.
"""

from __future__ import annotations

import os
import random
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# Repo root = two levels up from this file (.../creditcast/config.py -> repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "creditcast" / "conf" / "config.yaml"


class Config(dict):
    """dict with attribute access and absolute-path resolution helpers."""

    def __getattr__(self, item: str) -> Any:
        try:
            val = self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc
        return Config(val) if isinstance(val, dict) else val

    def path(self, key: str) -> Path:
        """Resolve a configured (repo-relative) path to an absolute Path."""
        return (REPO_ROOT / self["paths"][key]).resolve()


@lru_cache(maxsize=4)
def load_config(path: str | os.PathLike | None = None) -> Config:
    """Load the config. `CREDITCAST_CONFIG` (a path) overrides the default file —
    used by the end-to-end test to run the whole lifecycle in a temp folder."""
    env_path = os.environ.get("CREDITCAST_CONFIG")
    cfg_path = Path(path) if path else Path(env_path) if env_path else DEFAULT_CONFIG_PATH
    with open(cfg_path, "r") as fh:
        raw = yaml.safe_load(fh)
    return Config(raw)


def reload() -> None:
    """Forget the cached config (call after editing config.yaml in-process)."""
    load_config.cache_clear()


def set_global_seed(seed: int | None = None) -> int:
    """Seed Python + NumPy for determinism. Returns the seed used."""
    cfg = load_config()
    seed = int(seed if seed is not None else cfg["run"]["seed"])
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    os.environ["PYTHONHASHSEED"] = str(seed)
    return seed


def run_stamp() -> dict[str, Any]:
    """The reproducibility stamp attached to every run/artifact."""
    cfg = load_config()
    return {
        "seed": cfg["run"]["seed"],
        "data_version": cfg["run"]["data_version"],
        "code_version": cfg["run"]["code_version"],
    }
