"""Layered configuration: default.yaml < customers/<id>.yaml < env (ENTRYGUARD__A__B)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ENV_PREFIX = "ENTRYGUARD__"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Customer(_Base):
    id: str = "default"
    name: str = "Default customer"


class System(_Base):
    data_dir: Path = Path("./data")
    models_dir: Path = Path("./models")
    log_level: str = "INFO"


class Component(_Base):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class Models(_Base):
    detector: Component
    embedder: Component
    liveness: Component


class PersonField(_Base):
    key: str
    label: str = ""
    required: bool = False


class Enrollment(_Base):
    min_photos: int = 1
    max_photos: int = 10
    min_face_px: int = 80
    min_detect_score: float = 0.9
    allowed_extensions: list[str] = [".jpg", ".jpeg", ".png"]


class Policy(_Base):
    accept_threshold: float
    reject_threshold: float
    min_face_px: int = 60
    frames_to_decide: int = 5
    track_iou: float = 0.3
    track_max_missed: int = 10
    event_cooldown_s: float = 10

    @model_validator(mode="after")
    def _order(self) -> "Policy":
        if self.reject_threshold > self.accept_threshold:
            raise ValueError("policy.reject_threshold must be <= accept_threshold")
        return self


class Storage(_Base):
    backend: str = "sqlite"
    params: dict[str, Any] = Field(default_factory=dict)


class Events(_Base):
    save_snapshots: bool = True
    snapshot_retention_days: int = 30


class Camera(_Base):
    id: str
    name: str = ""
    direction: str = "in"
    fps: float = 10
    source: Component | dict[str, Any]

    @property
    def adapter(self) -> Component:
        s = self.source
        if isinstance(s, Component):
            return s
        return Component(name=s["adapter"], params=s.get("params", {}))


class Settings(_Base):
    customer: Customer = Customer()
    system: System = System()
    models: Models
    person_schema: list[PersonField] = []
    enrollment: Enrollment = Enrollment()
    policy: Policy
    storage: Storage = Storage()
    events: Events = Events()
    cameras: list[Camera] = []

    def model_path(self, filename: str) -> Path:
        p = Path(filename)
        return p if p.is_absolute() else self.system.models_dir / p


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _lookup(tree: dict, dotted: str) -> Any:
    cur: Any = tree
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def _expand(node: Any, root: dict) -> Any:
    """Replace ${ENV_VAR} from environment and ${a.b} from the config itself."""
    if isinstance(node, dict):
        return {k: _expand(v, root) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand(v, root) for v in node]
    if isinstance(node, str):
        def sub(m: re.Match) -> str:
            key = m.group(1)
            if key in os.environ:
                return os.environ[key]
            if "." in key:
                try:
                    return str(_lookup(root, key))
                except (KeyError, TypeError):
                    pass
            raise KeyError(f"Unresolved ${{{key}}} in config")
        return re.sub(r"\$\{([^}]+)\}", sub, node)
    return node


def _env_overrides() -> dict:
    out: dict = {}
    for key, val in os.environ.items():
        if not key.startswith(ENV_PREFIX):
            continue
        path = [p.lower() for p in key[len(ENV_PREFIX):].split("__")]
        cur = out
        for p in path[:-1]:
            cur = cur.setdefault(p, {})
        cur[path[-1]] = yaml.safe_load(val)
    return out


def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(
    customer: str | None = None,
    config_dir: str | Path | None = None,
    config_file: str | Path | None = None,
) -> Settings:
    """Load settings. `config_file` replaces the customer lookup with an explicit file."""
    cdir = Path(config_dir or os.environ.get("ENTRYGUARD_CONFIG_DIR", "config"))
    data = _read(cdir / "default.yaml")
    if config_file:
        data = _deep_merge(data, _read(Path(config_file)))
    else:
        customer = customer or os.environ.get("ENTRYGUARD_CUSTOMER")
        if customer:
            f = cdir / "customers" / f"{customer}.yaml"
            if not f.exists():
                raise FileNotFoundError(f"Customer config not found: {f}")
            data = _deep_merge(data, _read(f))
    data = _deep_merge(data, _env_overrides())
    data = _expand(data, data)
    return Settings.model_validate(data)
