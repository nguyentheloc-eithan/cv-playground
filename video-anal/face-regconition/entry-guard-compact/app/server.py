"""Step 5: a tiny web server so a browser can use the app. Python standard library only.

The browser page (static/index.html) talks to these URLs:
    GET  /               the page
    GET  /api/config     customer name and the registration form fields
    GET  /api/people     everyone registered
    POST /api/register   {name, fields, images:[data-url,...]}
    POST /api/check      {image: data-url}
    POST /api/delete     {id}
"""
import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np

from .config import ROOT
from .recognize import RegisterError

PAGE = ROOT / "app" / "static" / "index.html"


def decode_image(data_url):
    """Browser sends 'data:image/jpeg;base64,....'  ->  OpenCV image."""
    raw = base64.b64decode(data_url.split(",", 1)[-1])
    image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RegisterError("BAD_IMAGE", "Cannot read the image")
    return image


def run_server(cfg, recognizer, db, host, port):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, content_type="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep the terminal quiet
            pass

        def do_GET(self):
            if self.path == "/":
                self.reply(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/config":
                self.reply(200, {"customer": cfg["customer"]["name"],
                                 "fields": cfg["person_fields"]})
            elif self.path == "/api/people":
                self.reply(200, db.list_people())
            else:
                self.reply(204 if self.path == "/favicon.ico" else 404, b"")

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(size))
                if self.path == "/api/register":
                    images = [decode_image(i) for i in body["images"]]
                    person_id = recognizer.register(body["name"].strip(), body.get("fields", {}), images)
                    self.reply(201, {"id": person_id, "name": body["name"]})
                elif self.path == "/api/check":
                    self.reply(200, recognizer.check(decode_image(body["image"])))
                elif self.path == "/api/delete":
                    db.delete_person(body["id"])
                    self.reply(200, {"ok": True})
                else:
                    self.reply(404, {})
            except RegisterError as e:
                self.reply(400, {"error": {"code": e.code, "message": str(e)}})
            except (KeyError, ValueError) as e:
                self.reply(400, {"error": {"code": "BAD_REQUEST", "message": str(e)}})

    # A plain HTTPServer handles one request at a time. That is fine here and
    # keeps SQLite and OpenCV safe without any locking.
    print(f"Entry Guard running: http://{host}:{port}   (Ctrl+C to stop)")
    try:
        HTTPServer((host, port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
