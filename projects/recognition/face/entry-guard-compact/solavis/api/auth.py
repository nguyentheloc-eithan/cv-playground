from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import delete, select, update

from .. import db, faceauth, recog, security, services, settings, storage
from ..db import face_vectors, now, one, security_log, sessions, tenants, users
from .deps import any_user, client_ip, ip_allowed, _token

router = APIRouter(prefix="/api/auth", tags=["auth"])
_face_fail = {}


def public_user(u, c=None):
    return {"id": u["id"], "email": u["email"], "name": u["name"], "role": u["role"], "tenant_id": u["tenant_id"],
            "must_change_pw": bool(u["must_change_pw"]), "perms": u.get("perms", []), "is_super": bool(u.get("is_super")), "is_head": bool(u.get("is_head")),
            "department_id": u.get("department_id"), "job_title": u.get("job_title"), "face_pending": bool(u.get("face_pending")),
            "face_required": bool(u.get("face_required"))}


@router.post("/login")
def login(body: dict, request: Request, response: Response):
    email = str(body.get("email", "")).strip().lower()
    ip, ua = client_ip(request), request.headers.get("user-agent", "")
    key = (email, ip)
    if security.guard.blocked(key):
        raise HTTPException(429, "too many failed attempts, try again later")
    cfg = settings.get().security
    with db.tx() as c:
        u = one(c, select(users).where(users.c.email == email))
        if u and u["role"] == "staff" and not ip_allowed(ip, cfg.admin_ip_allowlist):
            services.sec_log(c, "login_blocked_ip", False, user=u, ip=ip, ua=ua)
            raise HTTPException(403, "staff access is not allowed from this network address")
        if not u or not u["active"] or not security.verify_password(str(body.get("password", "")), u["pw_hash"]):
            security.guard.fail(key)
            services.record(c, email or "?", "login_failed", ip)
            if u and u["role"] == "staff":
                services.sec_log(c, "login_password_failed", False, user=u, ip=ip, ua=ua)
            raise HTTPException(401, "wrong email or password")
        security.guard.ok(key)
        pending = bool(u["role"] == "staff" and u["face_required"])
        life = cfg.super_admin.session_minutes * 60 if u["is_super"] else cfg.staff.session_hours * 3600 if u["role"] == "staff" else cfg.session.hours * 3600
        tok = security.new_token()
        c.execute(sessions.insert().values(token_hash=security.hash_token(tok), user_id=u["id"], created=now(), expires=now() + life, face_pending=pending, ip=ip, ua=ua[:200], last_seen=now()))
        c.execute(update(users).where(users.c.id == u["id"]).values(last_login=now()))
        services.record(c, email, "login", "", u["tenant_id"])
        if u["role"] == "staff":
            services.sec_log(c, "login_password_ok", True, user=u, ip=ip, ua=ua, detail={"face_next": pending, "super": bool(u["is_super"])})
        enrolled = bool(c.execute(select(face_vectors.c.id).where(face_vectors.c.user_id == u["id"])).first())
        u["perms"] = [] if pending else services.effective_perms(c, u)          # the menu is built from these
        u["is_head"] = bool(u["role"] == "staff" and u["department_id"] and services.is_head_of(c, u, u["department_id"]))
    response.set_cookie(cfg.session.cookie_name, tok, httponly=True, samesite=cfg.session.cookie_samesite, secure=cfg.session.cookie_secure, max_age=life, path="/")
    u["face_pending"] = pending
    return {"token": tok, **public_user(u), "face": {"required": pending, "enrolled": enrolled}}


@router.post("/logout")
def logout(request: Request, response: Response):
    tok = _token(request)
    if tok:
        with db.tx() as c:
            s = one(c, select(sessions, users.c.email, users.c.role, users.c.id.label("uid")).join(users, users.c.id == sessions.c.user_id).where(sessions.c.token_hash == security.hash_token(tok)))
            c.execute(delete(sessions).where(sessions.c.token_hash == security.hash_token(tok)))
            if s and s["role"] == "staff":
                services.sec_log(c, "logout", True, actor=s["email"], ip=client_ip(request))
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
        if u["role"] == "staff":
            services.sec_log(c, "password_change", True, user=u)
    return {"ok": True}


# ───────── face ─────────
async def _frames(files):
    cfg = settings.get().security.face
    out = []
    for f in files[: cfg.max_frames]:
        data = await f.read(6 * 1024 * 1024)
        out.append(recog.decode(data))
    return out


def _blocked(uid):
    cfg = settings.get().security.face
    n, until = _face_fail.get(uid, (0, 0))
    return n >= cfg.max_failures and until > now()


@router.get("/face/status")
def face_status(u=Depends(any_user)):
    with db.tx() as c:
        enrolled = bool(c.execute(select(face_vectors.c.id).where(face_vectors.c.user_id == u["id"])).first())
    return {"required": bool(u["face_required"]), "enrolled": enrolled, "pending": bool(u["face_pending"]), "verified_at": u["face_verified_at"],
            "reverify_minutes": settings.get().security.face.reverify_minutes}


@router.post("/face/verify")
async def face_verify(request: Request, images: list[UploadFile] = File(...), u=Depends(any_user)):
    """Live face check. Used to finish sign-in and to re-confirm before sensitive actions. Every attempt is recorded."""
    if not u["face_required"]:
        raise HTTPException(400, "face check is not required for this account")
    ip, ua = client_ip(request), request.headers.get("user-agent", "")
    if _blocked(u["id"]):
        raise HTTPException(429, "too many failed face checks, try again later")
    frames = await _frames(images)
    cfg = settings.get().security.face
    with db.tx() as c:
        enrolled = faceauth.load_vectors(c, u["id"])
    ok, msg, scores, snap_jpeg = faceauth.verify(frames, enrolled)
    pose_only = (not ok) and msg != faceauth.NOT_RECOGNISED and msg != "No face is enrolled for this account"
    snap = None
    with db.tx() as c:
        if snap_jpeg and not pose_only:
            snap = "sec_" + security.new_token()[:20] + ".jpg"
            storage.store().put(snap, snap_jpeg)
        if pose_only:
            raise HTTPException(400, msg)                      # try again: not a failed identity check
        if ok:
            _face_fail.pop(u["id"], None)
            c.execute(update(sessions).where(sessions.c.token_hash == u["_sid"]).values(face_pending=False, face_verified_at=now()))
            services.sec_log(c, "face_verify_ok", True, user=u, ip=ip, ua=ua, snap=snap, detail={"scores": scores})
        else:
            n, _ = _face_fail.get(u["id"], (0, 0))
            _face_fail[u["id"]] = (n + 1, now() + cfg.lock_minutes * 60)
            services.sec_log(c, "face_verify_failed", False, user=u, ip=ip, ua=ua, snap=snap, detail={"scores": scores, "reason": msg, "failures": n + 1})
    if not ok:
        raise HTTPException(401, "Face not recognised" if msg == faceauth.NOT_RECOGNISED else msg)
    return {"ok": True, "verified_at": now()}


@router.post("/face/enroll")
async def face_enroll(request: Request, images: list[UploadFile] = File(...), code: str = Form(""), u=Depends(any_user)):
    """Enroll the President's face. Allowed with a one-time code (printed by the CLI) or after a fresh face check (re-enrollment)."""
    code = code.strip().upper()
    if not u["face_required"]:
        raise HTTPException(400, "face check is not required for this account")
    ip, ua = client_ip(request), request.headers.get("user-agent", "")
    frames = await _frames(images)
    cfg = settings.get().security.face
    with db.tx() as c:
        have = bool(c.execute(select(face_vectors.c.id).where(face_vectors.c.user_id == u["id"])).first())
        row = one(c, select(users).where(users.c.id == u["id"]))
        code_ok = bool(code and row["enroll_hash"] and row["enroll_expires"] and row["enroll_expires"] > now() and security.hash_token(code) == row["enroll_hash"])
        fresh_ok = bool(have and u["face_verified_at"] and now() - u["face_verified_at"] <= cfg.reverify_minutes * 60)
        if not (code_ok or fresh_ok):
            services.sec_log(c, "face_enroll_denied", False, user=u, ip=ip, ua=ua, detail={"had_code": bool(code), "enrolled": have})
            raise HTTPException(403, "an enrollment code from your administrator is required" if not have else "verify your face first")
        msg, vecs, snap_jpeg = faceauth.enrollment_vectors(frames)
        if msg:
            raise HTTPException(400, msg)
        snap = "sec_" + security.new_token()[:20] + ".jpg"
        storage.store().put(snap, snap_jpeg)
        c.execute(delete(face_vectors).where(face_vectors.c.user_id == u["id"]))
        for v in vecs:
            c.execute(face_vectors.insert().values(user_id=u["id"], vec=v.astype("float32").tobytes(), created=now()))
        c.execute(update(users).where(users.c.id == u["id"]).values(enroll_hash=None, enroll_expires=None))
        c.execute(update(sessions).where(sessions.c.token_hash == u["_sid"]).values(face_pending=False, face_verified_at=now()))
        services.sec_log(c, "face_enrolled", True, user=u, ip=ip, ua=ua, snap=snap, detail={"frames": len(vecs), "method": "code" if code_ok else "reverify"})
    return {"ok": True, "frames": len(vecs)}


# ───────── my sessions ─────────
@router.get("/sessions")
def my_sessions(u=Depends(any_user)):
    with db.tx() as c:
        rows = db.many(c, select(sessions).where(sessions.c.user_id == u["id"], sessions.c.expires > now()).order_by(sessions.c.created.desc()))
    return [{"id": r["token_hash"][:12], "ip": r["ip"], "ua": r["ua"], "created": r["created"], "last_seen": r["last_seen"], "current": r["token_hash"] == u["_sid"]} for r in rows]


@router.post("/sessions/{sid}/revoke")
def revoke_session(sid: str, u=Depends(any_user)):
    with db.tx() as c:
        c.execute(delete(sessions).where(sessions.c.user_id == u["id"], sessions.c.token_hash.like(sid + "%"), sessions.c.token_hash != u["_sid"]))
        if u["role"] == "staff":
            services.sec_log(c, "session_revoked", True, user=u, detail={"id": sid})
    return {"ok": True}
