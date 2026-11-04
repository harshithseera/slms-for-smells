"""Config loading. Every model, threshold and path comes from YAML, never hardcoded."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None, overrides: dict | None = None) -> dict[str, Any]:
    """Load a config, layered on top of dev.example.yaml so every key has a default."""
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:  # pragma: no cover
        pass
    base = yaml.safe_load((REPO_ROOT / "configs" / "dev.example.yaml").read_text())
    cfg = base
    if path is not None:
        cfg = _deep_merge(base, yaml.safe_load(Path(path).read_text()) or {})
        cfg["_config_path"] = str(path)
    if overrides:
        cfg = _deep_merge(cfg, overrides)
    return cfg


def resolve_path(cfg: dict, key: str) -> Path:
    p = Path(cfg["paths"][key])
    return p if p.is_absolute() else REPO_ROOT / p


def api_key(model_cfg: dict) -> str | None:
    env = model_cfg.get("api_key_env")
    return os.environ.get(env) if env else None
