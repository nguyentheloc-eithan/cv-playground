"""Virtual Solavis camera for demos and tests. A separate program: it talks to the cloud only through the public device API."""
import glob
import threading
import time
import uuid
from pathlib import Path

import cv2
import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import settings

HERE = Path(__file__).resolve().parent
S = {"key": None, "tilt": 2.0, "heading": 90.0, "cover_closed": 1, "covered": False, "scene": 0, "power": True,
     "battery": 87, "net": "wifi", "last": None, "log": []}
CFG = {}


def log(msg):
    S["log"] = ([f"{time.strftime('%H:%M:%S')}  {msg}"] + S["log"])[:40]


def frame_jpeg():
    img = np.zeros((240, 320, 3), np.uint8)
    for y in range(240):
        img[y, :, :] = (60 + y // 3, 90 + y // 4, 120)
    if S["scene"] == 0:
        cv2.rectangle(img, (40, 90), (130, 240), (30, 30, 160), -1)
        cv2.rectangle(img, (190, 60), (300, 200), (40, 140, 60), -1)
    else:
        img = cv2.flip(img, 1)
        cv2.circle(img, (160, 120), 70, (200, 200, 30), -1)
    if S["covered"]:
        img[:] = 8
    return cv2.imencode(".jpg", img)[1].tobytes()


def hdr():
    return {"Authorization": f"Bearer {S['key']}"}


def beat():
    if not S["key"] or not S["power"]:
        return
    try:
        r = httpx.post(f"{CFG['cloud_url']}/device/v1/heartbeat", headers=hdr(), timeout=15,
                       data={"battery": S["battery"], "net": S["net"], "rssi": -61, "tilt": S["tilt"], "heading": S["heading"], "cover_closed": S["cover_closed"], "fw": "1.0.0-sim"},
                       files={"frame": ("f.jpg", frame_jpeg(), "image/jpeg")})
        if r.status_code == 401:
            S["key"] = None
            log("cloud rejected the device key (revoked): camera is dead until re-claimed")
            return
        S["last"] = r.json()
    except Exception as e:
        log(f"cannot reach cloud: {e}")


def visitors():
    out = {}
    for v in CFG.get("visitors", []):
        files = sorted(glob.glob(str(settings.ROOT / v["photos"])))
        if files:
            out[v["label"]] = files
    return out


def create_app(package="demo"):
    pkg = settings.load_package(package)
    CFG.update(pkg.get("simulator", {}))
    CFG.setdefault("cloud_url", "http://127.0.0.1:8100")
    app = FastAPI(title="Solavis camera simulator")
    app.mount("/assets", StaticFiles(directory=HERE.parent / "web" / "assets"), name="assets")   # same design tokens as the product

    def loop():
        while True:
            time.sleep(4)
            beat()
    threading.Thread(target=loop, daemon=True).start()

    @app.get("/")
    def page():
        return FileResponse(HERE / "index.html")

    @app.get("/state")
    def state():
        return {**{k: v for k, v in S.items() if k != "key"}, "claimed": bool(S["key"]), "cloud_url": CFG["cloud_url"],
                "claim_code": CFG.get("camera", {}).get("claim_code", ""), "visitors": {k: len(v) for k, v in visitors().items()}}

    @app.post("/claim")
    def claim(body: dict):
        r = httpx.post(f"{CFG['cloud_url']}/device/v1/claim", json={"claim_code": body.get("claim_code", "")}, timeout=15)
        if r.status_code != 200:
            raise HTTPException(r.status_code, r.json().get("detail"))
        S["key"] = r.json()["device_key"]
        log("claimed: device key received, state = mounting")
        beat()
        return {"ok": True}

    @app.post("/set")
    def set_(body: dict):
        for k in ("tilt", "heading", "cover_closed", "covered", "scene", "power", "battery", "net"):
            if k in body:
                S[k] = body[k]
        log("physical change: " + ", ".join(f"{k}={body[k]}" for k in body))
        beat()
        return state()

    @app.post("/visit")
    def visit(body: dict):
        if not S["key"]:
            raise HTTPException(409, "camera is not claimed yet")
        files = visitors().get(body.get("label"))
        if not files:
            raise HTTPException(404, "no photos for that visitor")
        idx = int(body.get("index", 0)) % len(files)
        r = httpx.post(f"{CFG['cloud_url']}/device/v1/events", headers=hdr(), timeout=60, data={"idem": uuid.uuid4().hex},
                       files={"image": ("face.jpg", Path(files[idx]).read_bytes(), "image/jpeg")})
        out = r.json()
        log(f"visitor {body.get('label')} -> HTTP {r.status_code} {out}")
        return {"status": r.status_code, "result": out}

    @app.get("/photo/{label}")
    def photo(label: str):
        files = visitors().get(label)
        if not files:
            raise HTTPException(404)
        return Response(Path(files[0]).read_bytes(), media_type="image/jpeg")

    return app
