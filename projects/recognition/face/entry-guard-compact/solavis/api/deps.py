from fastapi import Depends, HTTPException, Request
from sqlalchemy import select

from .. import db, security, settings
from ..db import now, one, sessions, tenants, users


def _token(request: Request):
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return request.cookies.get(settings.get().security.session.cookie_name)


def _load(request: Request):
    tok = _token(request)
    if not tok:
        raise HTTPException(401, "login required")
    with db.tx() as c:
        u = one(c, select(users).join(sessions, sessions.c.user_id == users.c.id)
                .where(sessions.c.token_hash == security.hash_token(tok), sessions.c.expires > now(), users.c.active == True))  # noqa: E712
        if not u:
            raise HTTPException(401, "session expired, please log in again")
        if u["tenant_id"]:
            st = c.execute(select(tenants.c.status).where(tenants.c.id == u["tenant_id"])).scalar()
            if st == "closed":
                raise HTTPException(403, "this account is closed")
    return u


def any_user(request: Request):
    return _load(request)


def active_user(u=Depends(any_user)):
    if u["must_change_pw"]:
        raise HTTPException(403, "password change required")
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
    """Staff dependency that also checks one permission from config/roles.yaml."""
    from .. import services

    def dep(u=Depends(staff)):
        if not services.can(u, perm):
            raise HTTPException(403, f"your role does not allow {perm}")
        return u
    return dep
