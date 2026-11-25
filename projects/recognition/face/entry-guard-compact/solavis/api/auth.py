from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select, update

from .. import db, security, services, settings
from ..db import now, one, sessions, tenants, users
from .deps import any_user, _token

router = APIRouter(prefix="/api/auth", tags=["auth"])


def public_user(u):
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "tenant_id": u["tenant_id"],
            "must_change_pw": bool(u["must_change_pw"]), "staff_role": u.get("staff_role"), "perms": services.perms_for(u)}


@router.post("/login")
def login(body: dict, request: Request, response: Response):
    email = str(body.get("email", "")).strip().lower()
    key = (email, request.client.host if request.client else "")
    if security.guard.blocked(key):
        raise HTTPException(429, "too many failed attempts, try again later")
    with db.tx() as c:
        u = one(c, select(users).where(users.c.email == email))
        if not u or not u["active"] or not security.verify_password(str(body.get("password", "")), u["pw_hash"]):
            security.guard.fail(key)
            services.record(c, email or "?", "login_failed", request.client.host if request.client else "")
            raise HTTPException(401, "wrong email or password")
        security.guard.ok(key)
        cfg = settings.get().security.session
        tok = security.new_token()
        c.execute(sessions.insert().values(token_hash=security.hash_token(tok), user_id=u["id"], created=now(), expires=now() + cfg.hours * 3600))
        c.execute(update(users).where(users.c.id == u["id"]).values(last_login=now()))
        services.record(c, email, "login", "", u["tenant_id"])
    response.set_cookie(cfg.cookie_name, tok, httponly=True, samesite=cfg.cookie_samesite, secure=cfg.cookie_secure, max_age=cfg.hours * 3600, path="/")
    return {"token": tok, **public_user(u)}


@router.post("/logout")
def logout(request: Request, response: Response):
    tok = _token(request)
    if tok:
        with db.tx() as c:
            c.execute(delete(sessions).where(sessions.c.token_hash == security.hash_token(tok)))
    response.delete_cookie(settings.get().security.session.cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
def me(u=Depends(any_user)):
    return public_user(u)


@router.post("/password")
def change_password(body: dict, u=Depends(any_user)):
    if not security.verify_password(str(body.get("current", "")), u["pw_hash"]):
        raise HTTPException(400, "current password is wrong")
    new = str(body.get("new", ""))
    if msg := security.check_password_rules(new):
        raise HTTPException(400, msg)
    if new == body.get("current"):
        raise HTTPException(400, "choose a different password")
    with db.tx() as c:
        c.execute(update(users).where(users.c.id == u["id"]).values(pw_hash=security.hash_password(new), must_change_pw=False))
        services.record(c, u["email"], "password_change", "", u["tenant_id"])
    return {"ok": True}
