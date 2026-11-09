"""Step 1 of the app: read settings.

Settings come from two YAML files that are merged:
    config/default.yaml            (values every customer gets)
    config/customers/<name>.yaml   (only what this customer changes)
The result is a plain Python dict, for example  cfg["policy"]["accept_threshold"].
"""
import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent  # the entry-guard-compact folder


def _merge(base, extra):
    """Copy `extra` on top of `base`. Nested dicts are merged, everything else is replaced."""
    result = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _fill_env(value):
    """Replace ${NAME} in strings with the environment variable NAME (for secrets)."""
    if isinstance(value, dict):
        return {k: _fill_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill_env(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ[m.group(1)], value)
    return value


def _read(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(customer=None):
    """Return the settings dict. `customer` is the name of a file in config/customers/."""
    cfg = _read(ROOT / "config" / "default.yaml")
    customer = customer or os.environ.get("ENTRYGUARD_CUSTOMER")
    if customer:
        path = ROOT / "config" / "customers" / f"{customer}.yaml"
        if not path.exists():
            raise SystemExit(f"Customer config not found: {path}")
        cfg = _merge(cfg, _read(path))
    cfg = _fill_env(cfg)

    # Fail early with a clear message if thresholds make no sense.
    p = cfg["policy"]
    if p["reject_threshold"] > p["accept_threshold"]:
        raise SystemExit("policy.reject_threshold must not be higher than accept_threshold")
    return cfg


def path_in_project(text):
    """Turn a path from the config into an absolute path (relative to the project folder)."""
    p = Path(text)
    return p if p.is_absolute() else ROOT / p
