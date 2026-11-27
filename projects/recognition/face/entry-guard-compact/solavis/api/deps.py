import ipaddress

from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select, update

from .. import db, security, services, settings
from ..db import now, one, sessions, tenants, users


def _token(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return request.cookies.get(settings.get().security.session.cookie_name)


def client_ip(request: Request):
    return request.client.host if request.client else ""


def ip_allowed(ip, allow):
    if not allow:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in ipaddress.ip_network(a, strict=False) for a in allow)


def _load(request: Request):
    tok = _token(request)
    if not tok:
        raise HTTPException(401, "login required")
    cfg = settings.get().security
    th = security.hash_token(tok)
    with db.tx() as c:
        u = one(c, select(users, sessions.c.token_hash.label("_sid"), sessions.c.face_pending, sessions.c.face_verified_at, sessions.c.last_seen, sessions.c.client)
                .join(sessions, sessions.c.user_id == users.c.id)
                .where(sessions.c.token_hash == th, sessions.c.expires > now(), users.c.active == True))  # noqa: E712
        if not u:
            raise HTTPException(401, "session expired, please log in again")
        if u["role"] == "staff":
            if not ip_allowed(client_ip(request), cfg.admin_ip_allowlist):
                raise HTTPException(403, "staff access is not allowed from this network address")
            if u["last_seen"] and now() - u["last_seen"] > cfg.staff.idle_minutes * 60:
                c.execute(delete(sessions).where(sessions.c.token_hash == th))
                services.sec_log(c, "session_idle_timeout", True, user=u, ip=client_ip(request))
                raise HTTPException(401, "signed out after inactivity, please log in again")
        if not u["last_seen"] or now() - u["last_seen"] > 20:
            vals = {"last_seen": now()}
            if u.get("client") == "mobile":                       # sliding expiry: an app in regular use stays signed in
                vals["expires"] = now() + cfg.session.mobile_days * 86400
            c.execute(update(sessions).where(sessions.c.token_hash == th).values(**vals))
        if u["tenant_id"]:
            st = c.execute(select(tenants.c.status).where(tenants.c.id == u["tenant_id"])).scalar()
            if st == "closed":
                raise HTTPException(403, "this account is closed")
        u["perms"] = services.effective_perms(c, u)
        u["is_head"] = bool(u["role"] == "staff" and u["department_id"] and services.is_head_of(c, u, u["department_id"]))
    request.state.user = u
    return u


def any_user(request: Request):
    return _load(request)


def active_user(u=Depends(any_user)):
    if u["must_change_pw"]:
        raise HTTPException(403, "password change required")
    if u["face_pending"]:
        raise HTTPException(403, "face_required")
    return u


def member(u=Depends(active_user)):
    if u["role"] == "staff":
        raise HTTPException(403, "customer account required")
    return u


def owner(u=Depends(member)):
    if u["role"] != "owner":
        raise HTTPException(403, "only the account owner can do this")
    return u


def staff(u=Depends(active_user)):
    if u["role"] != "staff":
        raise HTTPException(403, "staff only")
    return u


def need(perm: str):
    """Staff dependency that also checks one permission (the President holds all)."""
    def dep(u=Depends(staff)):
        if not services.can(u, perm):
            raise HTTPException(403, f"your role does not allow {perm}")
        return u
    return dep


def super_admin(u=Depends(staff)):
    if not u.get("is_super"):
        raise HTTPException(403, "only the President can do this")
    return u


def fresh(u):
    """Sensitive actions need a face check newer than face.reverify_minutes."""
    if not u.get("face_required"):
        return u
    face = settings.get().security.face
    if not u["face_verified_at"] or now() - u["face_verified_at"] > face.reverify_minutes * 60:
        raise HTTPException(428, "face_reverify")
    return u


def super_fresh(u=Depends(super_admin)):
    return fresh(u)
