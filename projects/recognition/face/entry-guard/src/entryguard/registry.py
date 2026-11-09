"""Maps config names to adapter classes. Imports are lazy so unused models need no libraries."""
from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

from .config import Component, Settings

# name -> "module:Class"
DETECTORS = {"yunet": "entryguard.adapters.detectors.yunet:YuNetDetector"}
EMBEDDERS = {"sface": "entryguard.adapters.embedders.sface:SFaceEmbedder"}
LIVENESS = {"none": "entryguard.adapters.liveness.none:NoLiveness"}
SOURCES = {
    "webcam": "entryguard.adapters.sources.cv:WebcamSource",
    "rtsp": "entryguard.adapters.sources.cv:RtspSource",
    "file": "entryguard.adapters.sources.cv:FileSource",
}
STORES = {"sqlite": "entryguard.store.sqlite:SqliteStore"}


def _load(table: dict[str, str], kind: str, name: str) -> Callable[..., Any]:
    if name not in table:
        raise ValueError(f"Unknown {kind} '{name}'. Available: {', '.join(sorted(table))}")
    mod, cls = table[name].split(":")
    return getattr(import_module(mod), cls)


def make_detector(s: Settings):
    c: Component = s.models.detector
    p = dict(c.params)
    if "path" in p:
        p["path"] = s.model_path(p["path"])
    return _load(DETECTORS, "detector", c.name)(**p)


def make_embedder(s: Settings):
    c = s.models.embedder
    p = dict(c.params)
    if "path" in p:
        p["path"] = s.model_path(p["path"])
    return _load(EMBEDDERS, "embedder", c.name)(**p)


def make_liveness(s: Settings):
    c = s.models.liveness
    return _load(LIVENESS, "liveness", c.name)(**c.params)


def make_store(s: Settings):
    return _load(STORES, "storage backend", s.storage.backend)(**s.storage.params)


def make_source(cam) :
    c = cam.adapter
    return _load(SOURCES, "source", c.name)(**{"fps": cam.fps, **c.params})
