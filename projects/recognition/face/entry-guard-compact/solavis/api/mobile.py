"""What a phone app needs beyond the web app: version gate, push tokens, signed picture links, device sessions."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import delete, select

from .. import db, security, services, settings, storage
from ..db import alerts, events, now, one, push_tokens
from .deps import member

router = APIRouter(prefix="/api", tags=["mobile"])
public = APIRouter(tags=["mobile"])


def _ver(v):
    try:
        return tuple(int(x) for x in str(v).split(".")[:3])
    except ValueError:
        return (0,)


@router.get("/app-config")
def app_config(app_version: str | None = None, platform: str | None = None):
    """Public. The app calls this on start: force-update gate, maintenance notice, feature flags."""
    cfg = settings.get()
    m = cfg.server.mobile
    floor = m.min_version_by_platform.get(platform or "", m.min_version)
    return {"min_version": floor, "latest_version": m.latest_version,
            "update_required": bool(app_version and _ver(app_version) < _ver(floor)),
            "maintenance": m.maintenance, "message": m.message,
            "store_url": {"ios": m.ios_url, "android": m.android_url, "windows": m.windows_url, "macos": m.macos_url}.get(platform or "", ""),
            "features": {"push": cfg.notifications.push.enabled}, "api": "v1", "server_time": now()}


@router.post("/push/register")
def push_register(body: dict, u=Depends(member)):
    token = str(body.get("token", "")).strip()
    if len(token) < 10 or len(token) > 300:
        raise HTTPException(400, "token is required")
    platform = body.get("platform") if body.get("platform") in ("ios", "android", "windows", "macos") else "other"
    with db.tx() as c:
        have = one(c, select(push_tokens).where(push_tokens.c.token == token))
        vals = dict(user_id=u["id"], tenant_id=u["tenant_id"], platform=platform, device_name=str(body.get("device_name", ""))[:120], last_seen=now())
        if have:
            c.execute(push_tokens.update().where(push_tokens.c.id == have["id"]).values(**vals))      # a token moves with the person who signs in on that phone
        else:
            c.execute(push_tokens.insert().values(token=token, created=now(), **vals))
    return {"ok": True}


@router.post("/push/unregister")
def push_unregister(body: dict, u=Depends(member)):
    with db.tx() as c:
        c.execute(delete(push_tokens).where(push_tokens.c.token == str(body.get("token", "")), push_tokens.c.user_id == u["id"]))
    return {"ok": True}


@router.get("/snap-url/{name}")
def snap_url(name: str, u=Depends(member)):
    """A short-lived signed link to one of the caller's pictures, for image views and notification attachments."""
    with db.tx() as c:
        owns = c.execute(select(events.c.id).where(events.c.snap == name, events.c.tenant_id == u["tenant_id"])).first() or \
            c.execute(select(alerts.c.id).where(alerts.c.snap == name, alerts.c.tenant_id == u["tenant_id"])).first()
    if not owns:
        raise HTTPException(404)
    url, exp = services.signed_snap_url(name)
    return {"url": url, "expires": exp}


@public.get("/s/{token}", include_in_schema=False)
def signed_snap(token: str):
    parts = token.rsplit(".", 2)                   # <stored name, which has its own extension>.<expiry>.<signature>
    if len(parts) != 3 or not parts[1].isdigit():
        raise HTTPException(404)
    name, exp, sig = parts
    if not security.verify_sig(f"{name}|{exp}", sig) or int(exp) < now() or "/" in name:
        raise HTTPException(404)
    data = storage.store().get(name)
    if data is None:
        raise HTTPException(404)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})
