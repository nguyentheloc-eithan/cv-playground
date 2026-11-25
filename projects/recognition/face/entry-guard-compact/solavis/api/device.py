"""Device API v1: what the camera firmware (or an edge agent) calls. Auth is a per-camera bearer key; the server checks every rule."""
import json
import secrets

import numpy as np
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy import select, update

from .. import db, recog, security, services, settings, storage
from ..db import cameras, events, many, now, one, people, vectors

router = APIRouter(prefix="/device/v1", tags=["device"])


def camera_from(authorization: str = Header(None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "device key required")
    with db.tx() as c:
        cam = one(c, select(cameras).where(cameras.c.key_hash == security.hash_key(authorization[7:].strip())))
    if not cam:
        raise HTTPException(401, "unknown or revoked device key")
    return cam


def config_for(c, cam):
    t = services.entitlement(c, cam["tenant_id"])
    tc = settings.get().tamper
    return {"state": cam["state"], "lock_reason": cam["lock_reason"], "subscription": t["effective_status"],
            "upload": bool(t["upload_ok"] and cam["state"] in ("armed", "mounting", "service")),
            "checkin_seconds": tc.checkin_seconds,
            "limits": {"tilt_deg": tc.tilt_limit_degrees, "heading_deg": tc.heading_limit_degrees}}


@router.post("/claim")
def claim(body: dict):
    """First boot: swap the code printed on the box for a device key (shown once, stored only as a hash)."""
    code = str(body.get("claim_code", "")).strip().upper()
    with db.tx() as c:
        cam = one(c, select(cameras).where(cameras.c.claim_code == code, cameras.c.state == "unclaimed"))
        if not cam:
            raise HTTPException(404, "claim code not valid or already used")
        key = security.new_device_key()
        c.execute(update(cameras).where(cameras.c.id == cam["id"]).values(key_hash=security.hash_key(key), state="mounting", last_seen=now(), quiet_alerted=False))
        services.record(c, f"camera:{cam['id']}", "claim", cam["name"], cam["tenant_id"])
    return {"device_key": key, "camera_id": cam["id"]}


@router.get("/config")
def get_config(cam=Depends(camera_from)):
    with db.tx() as c:
        return config_for(c, cam)


@router.post("/heartbeat")
async def heartbeat(battery: int = Form(...), net: str = Form("wifi"), rssi: int = Form(-60), tilt: float = Form(0),
                    heading: float = Form(0), cover_closed: int = Form(1), fw: str = Form(""), frame: UploadFile = File(None), cam=Depends(camera_from)):
    hist = recog.histogram(await frame.read()) if frame else None
    with db.tx() as c:
        cam = one(c, select(cameras).where(cameras.c.id == cam["id"]))
        if cam["state"] == "revoked":
            raise HTTPException(401, "revoked")
        c.execute(update(cameras).where(cameras.c.id == cam["id"]).values(
            last_seen=now(), battery=battery, net=net, rssi=rssi, tilt=tilt, heading=heading, quiet_alerted=False,
            fw_version=fw[:40] or cam["fw_version"]))
        if cam["state"] == "armed":
            services.evaluate_tamper(c, cam, tilt, heading, bool(cover_closed), hist)
        elif cam["state"] == "service" and cam["service_until"] and cam["service_until"] < now():
            c.execute(update(cameras).where(cameras.c.id == cam["id"]).values(state="armed", base_tilt=tilt, base_heading=heading))
        fresh = one(c, select(cameras).where(cameras.c.id == cam["id"]))
        if fresh["state"] in ("mounting", "service"):        # while being installed, keep the latest reading as the baseline
            c.execute(update(cameras).where(cameras.c.id == cam["id"]).values(
                base_tilt=tilt, base_heading=heading, base_hist=json.dumps(hist.tolist()) if hist is not None else fresh["base_hist"]))
        return config_for(c, fresh)


@router.post("/events")
async def post_event(image: UploadFile = File(...), idem: str = Form(...), cam=Depends(camera_from)):
    cfg = settings.get()
    data = await image.read(cfg.server.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > cfg.server.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "image too large")
    with db.tx() as c:
        cam = one(c, select(cameras).where(cameras.c.id == cam["id"]))
        if cam["state"] in ("locked", "revoked", "unclaimed"):
            raise HTTPException(423, f"camera is {cam['state']}")
        t = services.entitlement(c, cam["tenant_id"])
        if not t["upload_ok"]:
            raise HTTPException(402, f"subscription {t['effective_status']}")
        if c.execute(select(events.c.id).where(events.c.idem == idem)).first():
            return {"duplicate": True}
        if t["events_today"] >= t["events_per_day"]:
            raise HTTPException(429, "daily event limit of the plan reached")
        img = recog.decode(data)
        if img is None:
            raise HTTPException(400, "not an image")
        got = recog.largest_face_vector(img, cfg.recognition.min_face_px)
        if not got:
            return {"faces": 0}
        vec, _, crop = got
        th = cfg.recognition.thresholds
        best, who = -1.0, None
        rows = c.execute(select(vectors.c.vec, people.c.id, people.c.name, people.c.kind)
                         .join(people, people.c.id == vectors.c.person_id).where(vectors.c.tenant_id == cam["tenant_id"])).mappings()
        for r in rows:
            if r["kind"] == "watchlist" and not t["watchlist"]:
                continue
            s = float(np.dot(vec, np.frombuffer(r["vec"], np.float32)))
            if s > best:
                best, who = s, dict(r)
        if who and best >= th.accept:
            verdict = "known"
        elif who and best >= th.reject:
            verdict, who = "uncertain", None
        else:
            verdict, who = "unknown", None
        snap = f"{secrets.token_hex(12)}.jpg"
        storage.store().put(snap, crop)
        kind = who["kind"] if who else "unknown"
        eid = db.insert(c, events, tenant_id=cam["tenant_id"], camera_id=cam["id"], ts=now(), person_id=who["id"] if who else None,
                        name=who["name"] if who else None, kind=kind, score=round(best, 3) if best > -1 else None,
                        verdict=verdict, snap=snap, review="new", idem=idem)
        if kind == "watchlist":
            word = "Likely" if best >= th.watchlist_confirm else "Possible"
            services.add_alert(c, cam["tenant_id"], cam["id"], "high", "watchlist",
                               f"{word} watch-list match at {cam['name']} (score {best:.2f}). A person must verify before any action.", snap)
        elif verdict == "unknown":
            services.add_alert(c, cam["tenant_id"], cam["id"], "info", "unknown", f"Unknown person at {cam['name']}.", snap)
        return {"event_id": eid, "verdict": verdict, "name": who["name"] if who else None}


@router.post("/tamper")
def tamper(body: dict, cam=Depends(camera_from)):
    """The camera's own sensors (accelerometer wake, reed switch) report immediately instead of waiting for the next check-in."""
    with db.tx() as c:
        cam = one(c, select(cameras).where(cameras.c.id == cam["id"]))
        if cam["state"] == "armed":
            services.lock_camera(c, cam, str(body.get("kind", "tamper"))[:40], str(body.get("detail", "tamper reported by the camera"))[:200])
        return {"state": one(c, select(cameras.c.state).where(cameras.c.id == cam["id"]))["state"]}
