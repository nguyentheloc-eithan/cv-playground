"""Minimal local web UI (stdlib only): capture from the browser camera, register, check."""
from __future__ import annotations

import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import cv2
import numpy as np

from ..core.service import EnrollmentError, FaceService

STATIC = Path(__file__).parent / "static"


def _decode(data_url: str) -> np.ndarray:
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise EnrollmentError("BAD_IMAGE", "Cannot decode image")
    return img


def make_handler(svc: FaceService):
    class H(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype="application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj).encode())

        def log_message(self, *a) -> None:  # quiet
            pass

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/favicon.ico":
                self._send(204, b"")
            elif self.path == "/api/schema":
                self._json(200, {"customer": svc.s.customer.name,
                                 "fields": [f.model_dump() for f in svc.s.person_schema]})
            elif self.path == "/api/people":
                self._json(200, [{"id": p.id, "name": p.name, "attributes": p.attributes,
                                  "status": p.status} for p in svc.store.list_persons()])
            else:
                self._json(404, {"error": {"code": "NOT_FOUND"}})

        def do_POST(self) -> None:
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                if self.path == "/api/register":
                    imgs = [_decode(i) for i in body["images"]]
                    p = svc.enroll(body["name"].strip(), body.get("attributes", {}), imgs)
                    self._json(201, {"id": p.id, "name": p.name})
                elif self.path == "/api/check":
                    out = []
                    for r in svc.check_image(_decode(body["image"])):
                        d = r.detection
                        out.append({"decision": r.decision.value, "score": round(r.match.score, 3),
                                    "person": r.person.name if r.person else None,
                                    "attributes": r.person.attributes if r.person else {},
                                    "bbox": list(d.bbox) if d else None})
                    self._json(200, out)
                elif self.path == "/api/delete":
                    svc.store.delete_person(body["id"])
                    self._json(200, {"ok": True})
                else:
                    self._json(404, {"error": {"code": "NOT_FOUND"}})
            except EnrollmentError as e:
                self._json(400, {"error": {"code": e.code, "message": str(e)}})
            except (KeyError, ValueError) as e:
                self._json(400, {"error": {"code": "BAD_REQUEST", "message": str(e)}})

    return H


def serve(svc: FaceService, host: str = "127.0.0.1", port: int = 8000) -> None:
    srv = HTTPServer((host, port), make_handler(svc))  # single-threaded: safe for sqlite/cv2
    print(f"Entry Guard UI: http://{host}:{port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
