"""eg: command line for the MVP.  eg --customer acme enroll --name An --attr unit_no=302 a.jpg"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Settings, load_settings


def _service(s: Settings):
    import cv2  # noqa: F401  (fail early with a clear error if missing)
    from . import registry
    from .core.service import FaceService
    return FaceService(s, registry.make_detector(s), registry.make_embedder(s),
                       registry.make_liveness(s), registry.make_store(s))


def _read(path: str):
    import cv2
    img = cv2.imread(path)
    if img is None:
        raise SystemExit(f"Cannot read image: {path}")
    return img


def cmd_config(s: Settings, a) -> None:
    print(s.model_dump_json(indent=2))


def cmd_enroll(s: Settings, a) -> None:
    from .core.service import EnrollmentError
    ext = set(s.enrollment.allowed_extensions)
    for p in a.photos:
        if Path(p).suffix.lower() not in ext:
            raise SystemExit(f"Extension not allowed: {p}")
    attrs = dict(kv.split("=", 1) for kv in a.attr)
    try:
        person = _service(s).enroll(a.name, attrs, [_read(p) for p in a.photos])
    except EnrollmentError as e:
        raise SystemExit(f"[{e.code}] {e}")
    print(f"Enrolled {person.name} ({person.id})")


def cmd_check(s: Settings, a) -> None:
    for r in _service(s).check_image(_read(a.image)):
        who = f"{r.person.name} {r.person.attributes}" if r.person else "-"
        print(f"{r.decision.value:10} score={r.match.score:.3f} person={who}")


def cmd_run(s: Settings, a) -> None:
    from . import registry
    svc = _service(s)
    cams = [c for c in s.cameras if not a.camera or c.id == a.camera]
    if not cams:
        raise SystemExit("No camera configured (see cameras: in the config)")
    cam = cams[0]  # MVP: one camera per process; run one `eg run` per camera
    src = registry.make_source(cam)

    def show(cid, r):
        who = r.person.name if r.person else "-"
        print(f"[{cid}] {r.decision.value} score={r.match.score:.3f} {who}", flush=True)
    try:
        svc.watch(cam.id, src, show)
    except KeyboardInterrupt:
        pass
    finally:
        src.close()


def cmd_ui(s: Settings, a) -> None:
    from .web.server import serve
    serve(_service(s), a.host, a.port)


def cmd_list(s: Settings, a) -> None:
    from . import registry
    for p in registry.make_store(s).list_persons():
        print(f"{p.id}  {p.status:8} {p.name}  {p.attributes}")


def cmd_remove(s: Settings, a) -> None:
    from . import registry
    registry.make_store(s).delete_person(a.id)
    print("Removed (person and face vectors erased)")


def cmd_events(s: Settings, a) -> None:
    from . import registry
    for e in registry.make_store(s).list_events(a.limit):
        print(e)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="eg")
    ap.add_argument("--customer", help="customer id (config/customers/<id>.yaml)")
    ap.add_argument("--config-dir", help="config directory (default ./config)")
    ap.add_argument("--config-file", help="explicit override file instead of --customer")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("config", help="print the effective configuration").set_defaults(fn=cmd_config)

    e = sub.add_parser("enroll", help="register a person from photos")
    e.add_argument("--name", required=True)
    e.add_argument("--attr", action="append", default=[], metavar="KEY=VALUE",
                   help="field from person_schema; repeatable")
    e.add_argument("photos", nargs="+")
    e.set_defaults(fn=cmd_enroll)

    c = sub.add_parser("check", help="check who is in an image")
    c.add_argument("image")
    c.set_defaults(fn=cmd_check)

    r = sub.add_parser("run", help="watch a configured camera")
    r.add_argument("--camera", help="camera id")
    r.set_defaults(fn=cmd_run)

    u = sub.add_parser("ui", help="local web UI: capture, register, check")
    u.add_argument("--host", default="127.0.0.1")
    u.add_argument("--port", type=int, default=8000)
    u.set_defaults(fn=cmd_ui)

    sub.add_parser("list", help="list registered people").set_defaults(fn=cmd_list)
    rm = sub.add_parser("remove", help="erase a person and their face vectors")
    rm.add_argument("id")
    rm.set_defaults(fn=cmd_remove)
    ev = sub.add_parser("events", help="recent events")
    ev.add_argument("--limit", type=int, default=20)
    ev.set_defaults(fn=cmd_events)

    a = ap.parse_args(argv)
    s = load_settings(a.customer, a.config_dir, a.config_file)
    logging.basicConfig(level=s.system.log_level)
    a.fn(s, a)


if __name__ == "__main__":
    main(sys.argv[1:])
