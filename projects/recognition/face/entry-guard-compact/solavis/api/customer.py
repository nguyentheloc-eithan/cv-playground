import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import delete, func, select, update

from .. import db, recog, security, services, settings, storage
from ..db import alerts, cameras, events, many, now, one, people, tenants, users, vectors
from .deps import member, owner

router = APIRouter(prefix="/api", tags=["customer"])
CAM_PUBLIC = (cameras.c.id, cameras.c.name, cameras.c.state, cameras.c.last_seen, cameras.c.battery, cameras.c.net, cameras.c.rssi,
              cameras.c.lock_reason, cameras.c.tilt, cameras.c.heading, cameras.c.claim_code, cameras.c.source_type)


def own_camera(c, cid, u):
    cam = one(c, select(cameras).where(cameras.c.id == cid, cameras.c.tenant_id == u["tenant_id"]))
    if not cam:
        raise HTTPException(404, "camera not found")        # another customer's camera looks like it does not exist
    return cam


@router.get("/overview")
def overview(u=Depends(member)):
    with db.tx() as c:
        t = services.entitlement(c, u["tenant_id"])
        cams = many(c, select(*CAM_PUBLIC).where(cameras.c.tenant_id == u["tenant_id"]).order_by(cameras.c.id))
        for cam in cams:
            if cam["state"] != "unclaimed":
                cam["claim_code"] = None                     # the code is only useful until the camera is claimed
        n = c.execute(select(func.count()).select_from(people).where(people.c.tenant_id == u["tenant_id"])).scalar()
        open_alerts = c.execute(select(func.count()).select_from(alerts).where(alerts.c.tenant_id == u["tenant_id"], alerts.c.acked == False)).scalar()  # noqa: E712
        return {"tenant": {"name": t["name"], "plan": t["plan_name"], "status": t["effective_status"], "trial_end": t["trial_end"],
                           "max_cameras": t["max_cameras"], "max_people": t["max_people"], "events_per_day": t["events_per_day"],
                           "events_today": t["events_today"], "people": n, "watchlist": bool(t["watchlist"]),
                           "telegram": bool(t["telegram_chat"])},
                "cameras": cams, "open_alerts": open_alerts, "now": now(), "role": u["role"]}


@router.get("/events")
def list_events(limit: int = 60, verdict: str | None = None, before: int | None = None, u=Depends(member)):
    q = (select(events, cameras.c.name.label("camera")).join(cameras, cameras.c.id == events.c.camera_id)
         .where(events.c.tenant_id == u["tenant_id"]).order_by(events.c.id.desc()).limit(min(limit, 200)))
    if verdict:
        q = q.where(events.c.verdict == verdict)
    if before:                                      # cursor paging for phones: pass the smallest id you already have
        q = q.where(events.c.id < before)
    with db.tx() as c:
        return many(c, q)


@router.post("/events/{eid}/review")
def review(eid: int, body: dict, u=Depends(member)):
    if body.get("review") not in ("confirmed", "dismissed", "new"):
        raise HTTPException(400, "review must be confirmed, dismissed or new")
    with db.tx() as c:
        r = c.execute(update(events).where(events.c.id == eid, events.c.tenant_id == u["tenant_id"]).values(review=body["review"]))
        if not r.rowcount:
            raise HTTPException(404, "event not found")
        services.record(c, u["email"], "event_review", f"{eid} {body['review']}", u["tenant_id"])
    return {"ok": True}


@router.get("/alerts")
def list_alerts(limit: int = 60, before: int | None = None, u=Depends(member)):
    q = (select(alerts, cameras.c.name.label("camera")).join(cameras, cameras.c.id == alerts.c.camera_id, isouter=True)
         .where(alerts.c.tenant_id == u["tenant_id"]).order_by(alerts.c.id.desc()).limit(min(limit, 200)))
    if before:
        q = q.where(alerts.c.id < before)
    with db.tx() as c:
        return many(c, q)


@router.post("/alerts/{aid}/ack")
def ack(aid: int, u=Depends(member)):
    with db.tx() as c:
        c.execute(update(alerts).where(alerts.c.id == aid, alerts.c.tenant_id == u["tenant_id"]).values(acked=True))
    return {"ok": True}


@router.post("/alerts/ack-all")
def ack_all(u=Depends(member)):
    with db.tx() as c:
        c.execute(update(alerts).where(alerts.c.tenant_id == u["tenant_id"]).values(acked=True))
    return {"ok": True}


@router.get("/snap/{name}")
def snap(name: str, u=Depends(member)):
    """Snapshots are served only to the customer that owns them."""
    with db.tx() as c:
        owns = c.execute(select(events.c.id).where(events.c.snap == name, events.c.tenant_id == u["tenant_id"])).first() or \
            c.execute(select(alerts.c.id).where(alerts.c.snap == name, alerts.c.tenant_id == u["tenant_id"])).first()
    if not owns:
        raise HTTPException(404)
    data = storage.store().get(name)
    if data is None:
        raise HTTPException(404)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


# ───────── people ─────────
@router.get("/people")
def list_people(u=Depends(member)):
    with db.tx() as c:
        rows = many(c, select(people).where(people.c.tenant_id == u["tenant_id"]).order_by(people.c.id))
        for r in rows:
            r["photos"] = c.execute(select(func.count()).select_from(vectors).where(vectors.c.person_id == r["id"])).scalar()
        return rows


@router.post("/people")
async def add_person(name: str = Form(...), kind: str = Form("known"), consent: str = Form(""),
                     photos: list[UploadFile] = File(...), u=Depends(owner)):
    cfg = settings.get().recognition
    if kind not in ("known", "watchlist"):
        raise HTTPException(400, "kind must be known or watchlist")
    if not name.strip():
        raise HTTPException(400, "name is required")
    if cfg.registration.require_consent_note and not consent.strip():
        raise HTTPException(400, "a consent or legal-basis note is required")
    if len(photos) > cfg.registration.max_photos:
        raise HTTPException(400, f"at most {cfg.registration.max_photos} photos")
    vecs = []
    for ph in photos:
        v = recog.single_face_vector(recog.decode(await ph.read()))
        if v is not None:
            vecs.append(v)
    if not vecs:
        raise HTTPException(400, "no photo with exactly one clear face was found")
    with db.tx() as c:
        t = services.entitlement(c, u["tenant_id"])
        if kind == "watchlist" and not t["watchlist"]:
            raise HTTPException(402, "your plan has no watch list")
        n = c.execute(select(func.count()).select_from(people).where(people.c.tenant_id == u["tenant_id"])).scalar()
        if n >= t["max_people"]:
            raise HTTPException(402, "the people limit of your plan is reached")
        pid = services.add_person(c, u["tenant_id"], name.strip(), kind, consent.strip(), vecs, u["email"])
    return {"id": pid, "photos_used": len(vecs), "photos_rejected": len(photos) - len(vecs)}


@router.delete("/people/{pid}")
def delete_person(pid: int, u=Depends(owner)):
    with db.tx() as c:
        if not c.execute(select(people.c.id).where(people.c.id == pid, people.c.tenant_id == u["tenant_id"])).first():
            raise HTTPException(404)
        c.execute(delete(vectors).where(vectors.c.person_id == pid))
        c.execute(delete(people).where(people.c.id == pid))
        c.execute(update(events).where(events.c.person_id == pid).values(person_id=None))
        services.record(c, u["email"], "person_delete", pid, u["tenant_id"])
    return {"ok": True}


# ───────── camera control ─────────
@router.post("/cameras/{cid}/arm")
def arm(cid: int, u=Depends(owner)):
    with db.tx() as c:
        cam = own_camera(c, cid, u)
        if cam["state"] not in ("mounting", "service"):
            raise HTTPException(409, f"cannot arm from state {cam['state']}")
        c.execute(update(cameras).where(cameras.c.id == cid).values(state="armed", lock_reason=None, quiet_alerted=False))
        services.record(c, u["email"], "arm", cid, u["tenant_id"])
    return {"state": "armed"}


@router.post("/cameras/{cid}/unlock")
def unlock(cid: int, u=Depends(owner)):
    """The owner clears a lock. The camera enters a service window so it can be fixed, then must be armed again."""
    cfg = settings.get().tamper
    with db.tx() as c:
        cam = own_camera(c, cid, u)
        if cam["state"] != "locked":
            raise HTTPException(409, "camera is not locked")
        c.execute(update(cameras).where(cameras.c.id == cid).values(state="service", lock_reason=None, service_until=now() + cfg.service_window_minutes * 60))
        services.record(c, u["email"], "unlock", cid, u["tenant_id"])
    return {"state": "service"}


@router.post("/cameras/{cid}/service")
def service(cid: int, u=Depends(owner)):
    cfg = settings.get().tamper
    with db.tx() as c:
        cam = own_camera(c, cid, u)
        if cam["state"] != "armed":
            raise HTTPException(409, "only an armed camera can enter a service window")
        c.execute(update(cameras).where(cameras.c.id == cid).values(state="service", service_until=now() + cfg.service_window_minutes * 60))
        services.record(c, u["email"], "service_window", cid, u["tenant_id"])
    return {"state": "service"}


@router.post("/cameras/{cid}/rename")
def rename(cid: int, body: dict, u=Depends(owner)):
    name = str(body.get("name", "")).strip()
    if not name:
        raise HTTPException(400, "name required")
    with db.tx() as c:
        own_camera(c, cid, u)
        c.execute(update(cameras).where(cameras.c.id == cid).values(name=name))
    return {"ok": True}


# ───────── account ─────────
@router.post("/settings/telegram")
def set_telegram(body: dict, u=Depends(owner)):
    with db.tx() as c:
        c.execute(update(tenants).where(tenants.c.id == u["tenant_id"]).values(telegram_chat=(str(body.get("chat_id") or "").strip() or None)))
    return {"ok": True, "live": settings.get().notifications.telegram.enabled}


@router.get("/team")
def team(u=Depends(owner)):
    with db.tx() as c:
        return many(c, select(users.c.id, users.c.email, users.c.name, users.c.role, users.c.active, users.c.last_login)
                    .where(users.c.tenant_id == u["tenant_id"]).order_by(users.c.id))


@router.post("/team")
def invite(body: dict, u=Depends(owner)):
    with db.tx() as c:
        try:
            _, pw = services.create_user(c, body.get("email", ""), role="member", tenant_id=u["tenant_id"], name=body.get("name", ""), actor=u["email"])
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"email": body["email"].strip().lower(), "temporary_password": pw}


@router.post("/team/{uid}/disable")
def disable_member(uid: int, u=Depends(owner)):
    if uid == u["id"]:
        raise HTTPException(400, "you cannot disable yourself")
    with db.tx() as c:
        c.execute(update(users).where(users.c.id == uid, users.c.tenant_id == u["tenant_id"]).values(active=False))
        services.record(c, u["email"], "user_disable", uid, u["tenant_id"])
    return {"ok": True}


@router.get("/export")
def export(u=Depends(owner)):
    """Everything we hold about this customer except the raw face vectors (data portability)."""
    with db.tx() as c:
        data = {"tenant": one(c, select(tenants).where(tenants.c.id == u["tenant_id"])),
                "people": many(c, select(people).where(people.c.tenant_id == u["tenant_id"])),
                "events": many(c, select(events).where(events.c.tenant_id == u["tenant_id"])),
                "alerts": many(c, select(alerts).where(alerts.c.tenant_id == u["tenant_id"])),
                "exported_at": now()}
        services.record(c, u["email"], "export", "", u["tenant_id"])
    return Response(json.dumps(data, default=str, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="solavis-export.json"'})


# ───────── devices, activity, reports ─────────
ACTIONS = {"arm": "Armed", "unlock": "Unlocked", "service_window": "Service window opened", "lock": "Locked (tamper)", "claim": "Camera set up",
           "person_add": "Person added", "person_delete": "Person deleted", "event_review": "Visitor reviewed", "export": "Data exported",
           "password_change": "Password changed", "login": "Signed in", "user_create": "Account created", "user_disable": "Account disabled",
           "ticket_open": "Support ticket opened", "camera_create": "Camera added", "invoice_create": "Invoice issued", "invoice_paid": "Invoice paid",
           "tenant_update": "Account updated by Solavis", "device_rma": "Device returned", "device_retire": "Device retired", "device_restock": "Device restocked"}


@router.get("/devices")
def devices(u=Depends(member)):
    from ..db import inventory
    with db.tx() as c:
        rows = many(c, select(cameras, inventory.c.serial, inventory.c.warranty_until).join(inventory, inventory.c.camera_id == cameras.c.id, isouter=True)
                    .where(cameras.c.tenant_id == u["tenant_id"]).order_by(cameras.c.id))
        day = now() - 86400
        for r in rows:
            r["visitors_24h"] = c.execute(select(func.count()).select_from(events).where(events.c.camera_id == r["id"], events.c.ts >= day)).scalar()
            r["alerts_open"] = c.execute(select(func.count()).select_from(alerts).where(alerts.c.camera_id == r["id"], alerts.c.acked == False)).scalar()  # noqa: E712
            r["online"] = bool(r["last_seen"] and now() - r["last_seen"] < settings.get().tamper.checkin_seconds * settings.get().tamper.quiet_after_missed)
            if r["state"] != "unclaimed":
                r["claim_code"] = None
            for k in ("key_hash", "base_hist", "base_tilt", "base_heading", "capabilities", "quiet_alerted", "service_until"):
                r.pop(k, None)
        return rows


@router.get("/activity")
def activity(limit: int = 100, u=Depends(member)):
    from ..db import audit
    with db.tx() as c:
        rows = many(c, select(audit).where(audit.c.tenant_id == u["tenant_id"]).order_by(audit.c.id.desc()).limit(min(limit, 300)))
    out = []
    for r in rows:
        who = "Camera" if r["actor"].startswith("camera:") else ("Solavis" if r["actor"] != "system" and "@" in r["actor"] and not _is_customer(r["actor"], u) else r["actor"])
        out.append({"ts": r["ts"], "who": who, "action": ACTIONS.get(r["action"], r["action"].replace("_", " ").capitalize()), "detail": r["target"] if r["action"] in ("lock", "person_add", "camera_create") else ""})
    return out


def _is_customer(email, u):
    with db.tx() as c:
        return bool(c.execute(select(users.c.id).where(users.c.email == email, users.c.tenant_id == u["tenant_id"])).first())


@router.get("/reports")
def reports(days: int = 14, u=Depends(member)):
    import datetime
    days = max(1, min(days, 90))
    start = now() - days * 86400
    with db.tx() as c:
        rows = many(c, select(events.c.ts, events.c.verdict, events.c.kind, events.c.name).where(events.c.tenant_id == u["tenant_id"], events.c.ts >= start))
    buckets = {}
    for i in range(days):
        d = (datetime.date.today() - datetime.timedelta(days=days - 1 - i)).isoformat()
        buckets[d] = {"date": d, "known": 0, "unknown": 0, "watchlist": 0}
    hours, names = [0] * 24, {}
    for r in rows:
        dt = datetime.datetime.fromtimestamp(r["ts"])
        b = buckets.get(dt.date().isoformat())
        if b is None:
            continue
        key = "watchlist" if r["kind"] == "watchlist" else ("known" if r["verdict"] == "known" else "unknown")
        b[key] += 1
        hours[dt.hour] += 1
        if r["name"]:
            names[r["name"]] = names.get(r["name"], 0) + 1
    return {"days": list(buckets.values()), "by_hour": hours, "total": len(rows), "top_people": sorted(names.items(), key=lambda x: -x[1])[:5]}
