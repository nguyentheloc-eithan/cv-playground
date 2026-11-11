"""Step 5: the web API (FastAPI). The browser page talks to these URLs.

Every URL starts with /api. Roles:  viewer = can look,  admin = can also change things.
Errors always look like  {"error": {"code": "...", "message": "...", "field": "..."}}.
"""
import base64
import csv
import io
import logging
import re
import secrets
import time
from datetime import datetime

import cv2
import numpy as np
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import access, alerts, auth, cameras, privacy, stepup
from .config import ROOT
from .recognize import RegisterError
from .scan import Scanner
from .worker import WorkerManager

COOKIE = "session"
STATIC = ROOT / "app" / "static"


# ---- request bodies (what the browser sends) -------------------------------
class Login(BaseModel):
    username: str
    password: str


class NewPerson(BaseModel):
    name: str
    phone: str = ""
    person_type: str = "resident"
    unit: str = ""
    valid_from: str | None = None      # YYYY-MM-DD
    valid_until: str | None = None
    notes: str = ""
    watch: dict = {}                   # watch-list details: reason, source, reference, instructions, review_by
    fields: dict = {}                  # the extra fields of person_fields (email, vehicle plate...)
    images: list[str]                  # data URLs: camera captures or uploaded files
    consent: bool = False              # consent of the person; for watch-list types: "I am authorised to record this"


class PersonEdit(BaseModel):
    """Every field is optional. "" clears a date. Sending only `status` just enables or disables."""
    name: str | None = None
    phone: str | None = None
    person_type: str | None = None
    unit: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    notes: str | None = None
    watch: dict | None = None
    fields: dict | None = None
    status: str | None = None          # active | disabled


class PinBody(BaseModel):
    pin: str
    current_password: str = ""


class FaceEnrol(BaseModel):
    images: list[str]
    current_password: str = ""


class FaceLogin(BaseModel):
    username: str
    images: list[str]


class SecurityToggle(BaseModel):
    face_enabled: bool | None = None
    pin_enabled: bool | None = None
    current_password: str = ""


class PasswordOnly(BaseModel):
    current_password: str = ""


class StepUpPin(BaseModel):
    action: str
    pin: str


class StepUpFace(BaseModel):
    action: str
    images: list[str]


class StepUpPassword(BaseModel):
    action: str
    password: str


class PhotosBody(BaseModel):
    images: list[str]
    replace: bool = True            # True: these photos REPLACE the old ones. False: they are added.


class AckBody(BaseModel):
    note: str = ""


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UserEdit(BaseModel):
    role: str | None = None
    active: bool | None = None
    password: str | None = None


class PasswordChange(BaseModel):
    current: str
    new: str


class CheckRequest(BaseModel):
    image: str


class ScanRequest(BaseModel):
    image: str
    camera_id: str | None = None


class ReviewRequest(BaseModel):
    reviewed: bool = True


class EnrollFromEvent(BaseModel):
    name: str
    phone: str = ""
    person_type: str = "resident"
    unit: str = ""
    valid_from: str | None = None
    valid_until: str | None = None
    notes: str = ""
    watch: dict = {}
    fields: dict = {}
    consent: bool = False


class TemplateBody(BaseModel):
    name: str
    path: str = ""
    port: int = 554
    username: str = ""
    transport: str = "tcp"
    note: str = ""


class CameraBody(BaseModel):
    """Form fields of an IP camera. Every field is optional so the same body serves add and edit."""
    id: str | None = None          # used by "test" to test a saved camera
    name: str | None = None
    location: str | None = None
    direction: str | None = None
    host: str | None = None
    port: int | str | None = None
    path: str | None = None
    username: str | None = None
    password: str | None = None
    transport: str | None = None
    fps: float | str | None = None
    enabled: bool | None = None


class ApiError(Exception):
    """An error with an HTTP status and a stable code the page can react to."""
    def __init__(self, status, code, message, field=None, extra=None):
        super().__init__(message)
        self.status, self.code, self.field, self.extra = status, code, field, extra or {}


def date_text(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d") if timestamp else ""


CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


def decode_image(data_url):
    """Browser sends 'data:image/jpeg;base64,....'  ->  OpenCV image."""
    try:
        raw = base64.b64decode(data_url.split(",", 1)[-1])
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    except ValueError:
        image = None
    if image is None:
        raise RegisterError("BAD_IMAGE", "Cannot read the image")
    return image


def create_app(cfg, recognizer, db, secret, opener=None, reachable=cameras.tcp_reachable, notify_sender=None):
    app = FastAPI(title="Entry Guard", docs_url="/api/docs", openapi_url="/api/openapi.json")
    hours = cfg["auth"]["session_hours"]
    alert_service = alerts.AlertService(cfg, db, sender=notify_sender or alerts.http_send)
    scanner = Scanner(cfg, recognizer, db, recognizer.engine, alert_service)
    app.state.alerts = alert_service
    workers = WorkerManager(db, scanner, cfg, **({"opener": opener} if opener else {}))
    app.state.workers = workers

    # ---- turn problems into the one error shape ---------------------------
    def error(status, code, message, field=None, extra=None):
        return JSONResponse(status_code=status,
                            content={"error": {"code": code, "message": message, "field": field, **(extra or {})}})

    @app.exception_handler(RegisterError)
    async def register_error(request, e):
        return error(400, e.code, str(e), e.field)

    @app.exception_handler(Exception)
    async def unexpected_error(request, e):
        # Always answer with JSON so the page can show a readable message. The traceback is
        # still printed in the terminal by the server.
        logging.getLogger("uvicorn.error").exception("Unhandled error on %s", request.url.path)
        return error(500, "SERVER_ERROR", "Something went wrong on the server. See the terminal.")

    @app.exception_handler(HTTPException)
    async def http_error(request, e):
        return error(e.status_code, str(e.detail).upper().replace(" ", "_"), str(e.detail))

    @app.exception_handler(ApiError)
    async def api_error(request, e):
        return error(e.status, e.code, str(e), e.field, e.extra)

    # ---- security layer for every request ------------------------------------
    @app.middleware("http")
    async def security_layer(request: Request, call_next):
        """1) CSRF defence: a change request must carry a custom header (a web page on another site
        cannot add one without our permission) and, if the browser says where it came from, it must be us.
        2) Security headers on every answer."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if request.headers.get("x-requested-with") != "entryguard" or (
                    origin and origin.split("://", 1)[-1] != request.headers.get("host")):
                return error(403, "CSRF_BLOCKED", "Request blocked (cross-site protection)")
        response = await call_next(request)
        response.headers.update({
            "Content-Security-Policy": CSP, "X-Frame-Options": "DENY", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "Permissions-Policy": "camera=(self), microphone=(), geolocation=()"})
        if request.url.path.startswith("/api/") and "stream" not in request.url.path:
            response.headers["Cache-Control"] = "no-store"
        return response

    # ---- who is calling? --------------------------------------------------
    def session_user(request: Request):
        """Any signed-in user, including residents (who may only read alerts)."""
        token = auth.read_token(secret, request.cookies.get(COOKIE, ""))
        user = db.get_user(user_id=token[0]) if token else None
        # the epoch check signs a user out everywhere after a password change, disable or role change
        if not user or not user["active"] or user["epoch"] != token[1]:
            raise HTTPException(401, "Not logged in")
        return user

    def current_user(user=Depends(session_user)):
        """Staff only (admin or viewer). Residents are refused everywhere except the alerts."""
        if user["role"] == "resident":
            raise HTTPException(403, "Staff only")
        return user

    def admin_only(user=Depends(current_user)):
        if user["role"] != "admin":
            raise HTTPException(403, "Admin only")
        return user

    # ---- public ------------------------------------------------------------
    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.get("/api/config")
    def public_config():
        keep = ("id", "label", "needs_unit", "needs_expiry", "default_days", "can_enter", "hours", "days", "watchlist", "severity")
        return {"customer": cfg["customer"]["name"], "fields": cfg["person_fields"],
                "site": cfg["site"],
                "person_types": [{k: t[k] for k in keep if k in t} for t in cfg["person_types"]],
                "require_phone": cfg["registration"]["require_phone"],
                "watchlist_basis_text": " ".join(cfg["alerts"]["watchlist_basis_text"].split()),
                "confirm_score": cfg["alerts"]["watchlist_confirm_score"],
                "consent_text": cfg["registration"]["consent_text"],
                "recommended_photos": cfg["registration"]["recommended_photos"],
                "scan_width": cfg["scan"]["max_width"],
                "accept_threshold": cfg["policy"]["accept_threshold"],
                "min_password_length": cfg["security"]["min_password_length"],
                "face_login": cfg["security"]["face_login"]["enabled"],
                "head_turn": cfg["security"]["step_up"]["require_head_turn"],
                "head_turn_min_yaw": cfg["security"]["step_up"]["head_turn_min_yaw"],
                "needs_setup": db.count_users() == 0}

    security = cfg["security"]

    def locked_for(username, ip):
        """Seconds the caller must still wait, or 0. Too many wrong passwords for one user name (or
        from one address) lock it for `lockout_minutes`."""
        window, now = security["lockout_minutes"] * 60, time.time()
        limit = security["max_failed_logins"]
        for fails, allowed in ((db.failed_logins(username=username, since=now - window), limit),
                               (db.failed_logins(ip=ip, since=now - window), limit * 4)):
            if len(fails) >= allowed:
                return int(fails[-allowed] + window - now) + 1
        return 0

    step_up = security["step_up"]

    def check_step_up(request, user, action):
        """Banking-style confirmation. If this action is protected, the request must carry a fresh,
        unused confirmation token for this user and action (header X-Step-Up); otherwise answer 403 with
        the list of ways the user can confirm."""
        if not step_up["enabled"] or action not in step_up["actions"]:
            return
        token = request.headers.get("x-step-up")
        if token and db.consume_grant(stepup.token_hash(token), user["id"], action):
            return
        methods = stepup.available_methods(db.get_security(user["id"]))
        raise ApiError(403, "STEP_UP_REQUIRED", "Confirm it is you to continue", extra={
            "action": action, "label": step_up["actions"][action], "methods": methods, "preferred": methods[0],
            "pin_length": step_up["pin_length"], "head_turn": step_up["require_head_turn"]})

    def watchlist_type(type_id):
        return bool(access.person_type(cfg, type_id).get("watchlist"))

    @app.post("/api/login")
    def login(body: Login, request: Request, response: Response):
        username = body.username.strip()
        ip = request.client.host if request.client else ""
        wait = locked_for(username, ip)
        if wait:
            db.audit(username or "?", "login_blocked", {"ip": ip})
            raise ApiError(429, "ACCOUNT_LOCKED",
                           f"Too many failed attempts. Try again in {max(1, round(wait / 60))} minute(s).")
        user = db.get_user(username=username)
        # Same answer for "no such user" and "wrong password": do not reveal which.
        if not user or not user["active"] or not auth.verify_password(body.password, user["pw_hash"]):
            db.record_login(username, ip, False)
            db.audit(username or "?", "login_failed", {"ip": ip})
            raise HTTPException(401, "Wrong username or password")
        db.record_login(username, ip, True)
        response.set_cookie(COOKIE, auth.make_token(secret, user["id"], hours, user["epoch"]),
                            max_age=int(hours * 3600), httponly=True, samesite="strict",
                            secure=cfg["auth"]["secure_cookie"])
        db.audit(user["username"], "login", {"ip": ip})
        return {"username": user["username"], "role": user["role"]}

    # ---- sign in with the face ----------------------------------------------------
    quality_hits = {}                                    # ip -> recent times (a small rate limit on the public endpoint)

    def face_login_on():
        if not security["face_login"]["enabled"]:
            raise HTTPException(404, "Face sign-in is not available")

    @app.post("/api/login/face/quality")
    def login_face_quality(body: CheckRequest, request: Request):
        """Live feedback for the sign-in camera (is a face visible, how far is the head turned). Public, so it is
        rate limited and only answers about the picture, never about any account."""
        face_login_on()
        ip, now = (request.client.host if request.client else ""), time.time()
        hits = [t for t in quality_hits.get(ip, []) if now - t < 5] + [now]
        quality_hits[ip] = hits
        if len(hits) > 25:
            raise ApiError(429, "SLOW_DOWN", "Too many requests, slow down")
        return recognizer.assess(decode_image(body.image))

    @app.post("/api/login/face")
    def login_face(body: FaceLogin, request: Request, response: Response):
        face_login_on()
        username = body.username.strip()
        ip = request.client.host if request.client else ""
        lock_key = f"face:{username}"                  # a separate counter from the password login
        wait = locked_for(lock_key, ip)
        if wait:
            db.audit(username or "?", "login_blocked", {"ip": ip, "method": "face"})
            raise ApiError(429, "ACCOUNT_LOCKED",
                           f"Too many failed attempts. Try again in {max(1, round(wait / 60))} minute(s).")
        images = [decode_image(i) for i in body.images[:3]]
        user = db.get_user(username=username)
        sec = db.get_security(user["id"]) if user else None
        eligible = bool(user and user["active"] and sec["face_enabled"])
        scores = []
        why = "face_not_matching"
        if eligible:
            ok, reason = stepup.verify_face(recognizer, cfg, images, db.face_vectors(user["id"]), scores)
        else:   # same pose checks as everyone, so the answer does not reveal whether this account uses face sign-in
            reason = stepup.pose_check(recognizer, cfg, images)
            ok = False
            why = "no_such_user" if not user else "account_disabled" if not user["active"] else "face_authentication_not_switched_on"
            # (the reason is written to the audit log for administrators; the person at the login screen never sees it)
        if not ok and reason and reason != stepup.NOT_RECOGNISED:
            raise ApiError(400, "FACE_POSE", reason)             # only a pose problem: try again, not a failed login
        if not ok:
            db.record_login(lock_key, ip, False)
            db.audit(username or "?", "login_failed", {"ip": ip, "method": "face", "reason": why, "scores": scores})
            raise HTTPException(401, "Face sign-in failed. Your face did not match, or Face authentication is not switched on "
                                     "for this account (Settings). Use your password instead.")
        db.record_login(lock_key, ip, True)
        response.set_cookie(COOKIE, auth.make_token(secret, user["id"], hours, user["epoch"]),
                            max_age=int(hours * 3600), httponly=True, samesite="strict",
                            secure=cfg["auth"]["secure_cookie"])
        db.audit(user["username"], "login", {"ip": ip, "method": "face"})
        return {"username": user["username"], "role": user["role"]}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE)
        return {"ok": True}

    # ---- logged-in users ---------------------------------------------------
    @app.get("/api/me")
    def me(user=Depends(session_user)):
        return {"username": user["username"], "role": user["role"]}

    @app.post("/api/me/password")
    def change_own_password(body: PasswordChange, response: Response, user=Depends(session_user)):
        if not auth.verify_password(body.current, user["pw_hash"]):
            raise ApiError(400, "WRONG_PASSWORD", "Current password is wrong", "current")
        problem = auth.password_problem(body.new, user["username"], security["min_password_length"])
        if problem:
            raise ApiError(400, "WEAK_PASSWORD", problem, "new")
        db.update_user(user["id"], pw_hash=auth.hash_password(body.new))
        fresh = db.get_user(user_id=user["id"])      # new epoch: every other session of this user is now signed out
        response.set_cookie(COOKIE, auth.make_token(secret, fresh["id"], hours, fresh["epoch"]),
                            max_age=int(hours * 3600), httponly=True, samesite="strict",
                            secure=cfg["auth"]["secure_cookie"])
        db.audit(user["username"], "password_changed")
        return {"ok": True}

    def person_view(person, user):
        """A person as the browser should see it: masked for viewers, plus their current access status."""
        out = privacy.visible(person, cfg, user["role"])
        out["status_label"] = access.status_label(person, cfg)
        out["access"] = access.evaluate(person, cfg)
        out["type_label"] = access.person_type(cfg, person["person_type"]).get("label", person["person_type"])
        return out

    @app.get("/api/people")
    def list_people(user=Depends(current_user)):
        return [person_view(p, user) for p in db.list_people()]

    @app.get("/api/people/{person_id}")
    def get_person(person_id: int, user=Depends(current_user)):
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(404, "No such person")
        events, total = db.list_events(person_id=person_id, limit=15)
        return {**person_view(person, user), "scans_total": total, "photos": [{"id": p["id"]} for p in db.list_photos(person_id)],
                "recent_events": [privacy.visible(e, cfg, user["role"]) for e in events]}

    @app.get("/api/people/{person_id}/photo")
    def person_photo(person_id: int, user=Depends(current_user)):
        path = db.first_photo(person_id)
        if not path or not path.exists():
            raise HTTPException(404, "No photo")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/api/people/{person_id}/photos/{photo_id}")
    def person_photo_file(person_id: int, photo_id: int, user=Depends(current_user)):
        path = db.photo_path(person_id, photo_id)
        if not path or not path.exists():
            raise HTTPException(404, "No photo")
        return FileResponse(path, media_type="image/jpeg")

    @app.post("/api/quality")
    def quality(body: CheckRequest, user=Depends(current_user)):
        return recognizer.assess(decode_image(body.image))

    # ---- security console: scan, events -----------------------------------
    @app.post("/api/scan")
    def scan(body: ScanRequest, user=Depends(current_user)):
        """One camera picture in; recognition results out; finished recognitions are logged."""
        if body.camera_id and not db.get_camera(body.camera_id):
            raise HTTPException(404, "No such camera")
        return scanner.scan(decode_image(body.image), body.camera_id)

    @app.get("/api/events")
    def list_events(decision: str | None = None, person_id: int | None = None,
                    since: float | None = None, until: float | None = None,
                    q: str | None = None, reviewed: bool | None = None, after_id: int | None = None,
                    limit: int = 25, offset: int = 0, access_result: str | None = None,
                    user=Depends(current_user)):
        events, total = db.list_events(decision, person_id, since, until, q, reviewed, after_id,
                                       min(max(limit, 1), 200), max(offset, 0), access_result)
        return {"events": [privacy.visible(e, cfg, user["role"]) for e in events], "total": total}

    @app.get("/api/events/stats")
    def event_stats(since: float | None = None, user=Depends(current_user)):
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return db.event_stats(since if since is not None else midnight)

    @app.get("/api/events/export.csv")
    def export_events(request: Request, decision: str | None = None, since: float | None = None,
                      until: float | None = None, q: str | None = None, user=Depends(admin_only)):
        check_step_up(request, user, "events_export")
        events, _ = db.list_events(decision, None, since, until, q, None, None, 100000, 0)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["time", "camera", "decision", "access", "reason", "person", "id", "unit",
                         "score", "reviewed"])
        for e in events:
            writer.writerow([datetime.fromtimestamp(e["ts"]).isoformat(timespec="seconds"),
                             e["camera_id"], e["decision"], e["access"] or "", e["reason"],
                             e["person"] or "", e["code"] or "", e["unit"] or "", e["score"],
                             "yes" if e["reviewed"] else "no"])
        db.audit(user["username"], "events_exported", {"rows": len(events)})
        return Response(out.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=scan-log.csv"})

    @app.get("/api/events/{event_id}/snapshot")
    def event_snapshot(event_id: int, user=Depends(current_user)):
        path = db.snapshot_path(event_id)
        if not path or not path.exists():
            raise HTTPException(404, "No snapshot")
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/api/events/{event_id}")
    def get_event(event_id: int, user=Depends(current_user)):
        event = db.get_event(event_id)
        if not event:
            raise HTTPException(404, "No such event")
        return privacy.visible(event, cfg, user["role"])

    @app.patch("/api/events/{event_id}")
    def review_event(event_id: int, body: ReviewRequest, user=Depends(current_user)):
        if not db.get_event(event_id):
            raise HTTPException(404, "No such event")
        db.set_reviewed(event_id, body.reviewed)
        db.audit(user["username"], "event_reviewed", {"id": event_id, "reviewed": body.reviewed})
        return privacy.visible(db.get_event(event_id), cfg, user["role"])

    @app.post("/api/events/{event_id}/enroll", status_code=201)
    def enroll_from_event(event_id: int, body: EnrollFromEvent, request: Request, user=Depends(admin_only)):
        """Turn an unknown person in the log into a registered resident, using the snapshot."""
        if watchlist_type(body.person_type):
            check_step_up(request, user, "watchlist_change")
        path = db.snapshot_path(event_id)
        image = cv2.imread(str(path)) if path and path.exists() else None
        if image is None:
            raise HTTPException(404, "This event has no snapshot")
        created = recognizer.register(body.model_dump(exclude={"consent"}), [image], body.consent)
        db.set_reviewed(event_id, True)
        db.audit(user["username"], "person_created",
                 {"id": created["id"], "code": created["code"], "name": body.name.strip(), "from_event": event_id})
        return {**created, "name": body.name.strip()}

    # ---- my security settings (PIN / face confirmation) -------------------------
    def need_password(user, password):
        if not auth.verify_password(password or "", user["pw_hash"]):
            raise ApiError(400, "WRONG_PASSWORD", "Your password is wrong", "current_password")

    @app.get("/api/me/security")
    def my_security(user=Depends(session_user)):
        sec = db.get_security(user["id"])
        return {"enabled": step_up["enabled"], "pin_length": step_up["pin_length"], "head_turn": step_up["require_head_turn"],
                "face": {"enrolled": sec["face_enrolled"], "enabled": sec["face_enabled"]},
                "face_login": {"available": security["face_login"]["enabled"]},      # sign-in follows the Face authentication switch
                "pin": {"set": sec["pin_set"], "enabled": sec["pin_enabled"]},
                "last_method": sec["last_method"], "actions": step_up["actions"],
                "methods": stepup.available_methods(sec)}

    @app.post("/api/me/security/pin")
    def set_my_pin(body: PinBody, user=Depends(session_user)):
        need_password(user, body.current_password)
        problem = stepup.pin_problem(body.pin, step_up["pin_length"])
        if problem:
            raise ApiError(400, "WEAK_PIN", problem, "pin")
        db.set_pin(user["id"], auth.hash_password(body.pin))
        db.audit(user["username"], "pin_set")
        return my_security(user)

    @app.post("/api/me/security/face")
    def enrol_my_face(body: FaceEnrol, user=Depends(session_user)):
        need_password(user, body.current_password)
        if len(body.images) < 3:
            raise ApiError(400, "PHOTO_COUNT", "Take 3 photos of your face", "images")
        vectors = recognizer.face_template([decode_image(i) for i in body.images[:5]])
        db.save_face(user["id"], vectors)
        db.audit(user["username"], "face_enrolled", {"photos": len(vectors)})
        return my_security(user)

    @app.patch("/api/me/security")
    def toggle_my_security(body: SecurityToggle, user=Depends(session_user)):
        """The switches. Turning a method ON needs it to be set up; turning one OFF needs your password
        (weakening your own security is a risky action too)."""
        sec = db.get_security(user["id"])
        changes = {}
        for key, ready, label in (("face_enabled", sec["face_enrolled"], "face"), ("pin_enabled", sec["pin_set"], "PIN")):
            wanted = getattr(body, key)
            if wanted is None:
                continue
            if wanted and not ready:
                raise ApiError(400, "NOT_SET_UP", f"Set up your {label} first", key)
            if not wanted:                              # weakening your own security needs the password
                need_password(user, body.current_password)
            changes[key] = wanted
        db.set_security_flags(user["id"], **changes)
        db.audit(user["username"], "security_setting_changed", changes)
        return my_security(user)

    @app.delete("/api/me/security/pin")
    def remove_my_pin(body: PasswordOnly, user=Depends(session_user)):
        need_password(user, body.current_password)
        db.remove_pin(user["id"])
        db.audit(user["username"], "pin_removed")
        return my_security(user)

    @app.delete("/api/me/security/face")
    def remove_my_face(body: PasswordOnly, user=Depends(session_user)):
        need_password(user, body.current_password)
        db.delete_face(user["id"])
        db.audit(user["username"], "face_removed")
        return my_security(user)

    # ---- confirm a risky action: returns a one-time token ------------------------
    def grant_after(request, user, action, method, ok, reason="wrong", detail=None):
        """Shared tail of the three confirmation endpoints: lockout, audit, grant."""
        if action not in step_up["actions"]:
            raise ApiError(400, "UNKNOWN_ACTION", "Unknown action")
        key, ip = f"stepup:{user['username']}", request.client.host if request.client else ""
        if not ok:
            db.record_login(key, ip, False)
            db.audit(user["username"], "step_up_failed", {"action": action, "method": method, **(detail or {})})
            raise ApiError(401, "STEP_UP_FAILED", reason)
        db.record_login(key, ip, True)
        db.set_security_flags(user["id"], last_method=method if method != "password" else None)
        db.audit(user["username"], "step_up_ok", {"action": action, "method": method})
        return {"token": stepup.new_grant(db, user["id"], action, method, step_up["grant_seconds"]),
                "expires_in": step_up["grant_seconds"]}

    def step_up_guard(request, user):
        wait = locked_for(f"stepup:{user['username']}", request.client.host if request.client else "")
        if wait:
            db.audit(user["username"], "step_up_locked")
            raise ApiError(429, "ACCOUNT_LOCKED", f"Too many failed confirmations. Try again in {max(1, round(wait / 60))} minute(s).")

    @app.post("/api/step-up/pin")
    def step_up_pin(body: StepUpPin, request: Request, user=Depends(current_user)):
        step_up_guard(request, user)
        sec = db.get_security(user["id"])
        ok = sec["pin_enabled"] and auth.verify_password(body.pin, db.get_pin_hash(user["id"]) or "")
        return grant_after(request, user, body.action, "pin", ok, "Wrong PIN")

    @app.post("/api/step-up/password")
    def step_up_password(body: StepUpPassword, request: Request, user=Depends(current_user)):
        step_up_guard(request, user)
        return grant_after(request, user, body.action, "password", auth.verify_password(body.password, user["pw_hash"]), "Wrong password")

    @app.post("/api/step-up/face")
    def step_up_face(body: StepUpFace, request: Request, user=Depends(current_user)):
        step_up_guard(request, user)
        sec = db.get_security(user["id"])
        if not sec["face_enabled"]:
            raise ApiError(400, "NOT_SET_UP", "Face confirmation is not turned on for this account")
        scores = []
        ok, reason = stepup.verify_face(recognizer, cfg, [decode_image(i) for i in body.images[:3]], db.face_vectors(user["id"]), scores)
        return grant_after(request, user, body.action, "face", ok, reason, {"scores": scores})

    # ---- alerts ---------------------------------------------------------------
    def alert_view(a, user):
        """Staff see who and why. Residents see only that a dangerous person was detected, where and when:
        no name, no offence, no ID."""
        camera = (db.get_camera(a["camera_id"]) or {}).get("name", a["camera_id"])
        base = {"id": a["id"], "ts": a["ts"], "last_ts": a["last_ts"], "level": a["level"], "confidence": a["confidence"],
                "count": a["count"], "status": a["status"], "camera": camera, "has_snapshot": a["has_snapshot"],
                "ack_by": a["ack_by"], "ack_at": a["ack_at"], "ack_note": a["ack_note"]}
        if user["role"] == "resident":
            return {**base, "message": alerts.residents_text(a, camera)}
        return {**base, "event_id": a["event_id"], "score": a["score"], "person_id": a["person_id"], "person": a["person"],
                "code": a["code"], "person_type": a["person_type"], "unit": a["unit"],
                "reason": a["watch"].get("reason", ""), "instructions": a["watch"].get("instructions", ""),
                "message": alerts.residents_text(a, camera)}

    @app.get("/api/alerts")
    def list_alerts(status: str | None = None, limit: int = 50, user=Depends(session_user)):
        if status not in (None, "open", "acknowledged"):
            raise HTTPException(400, "Bad status")
        return [alert_view(a, user) for a in db.list_alerts(status, min(max(limit, 1), 200))]

    @app.get("/api/alerts/{alert_id}/snapshot")
    def alert_snapshot(alert_id: int, user=Depends(session_user)):
        path = db.alert_snapshot_path(alert_id)
        if not path or not path.exists():
            raise HTTPException(404, "No snapshot")
        return FileResponse(path, media_type="image/jpeg")

    @app.post("/api/alerts/{alert_id}/ack")
    def acknowledge(alert_id: int, body: AckBody, user=Depends(current_user)):
        alert = db.get_alert(alert_id)
        if not alert:
            raise HTTPException(404, "No such alert")
        if alert["status"] == "open":
            db.acknowledge_alert(alert_id, user["username"], body.note.strip()[:300])
            db.audit(user["username"], "alert_acknowledged", {"alert": alert_id, "note": body.note.strip()[:300]})
        return alert_view(db.get_alert(alert_id), user)

    # ---- cameras -------------------------------------------------------------
    @app.get("/api/cameras")
    def list_cameras(user=Depends(current_user)):
        return [cameras.public(c) for c in db.list_cameras()]

    @app.get("/api/camera-presets")
    def camera_presets(user=Depends(current_user)):
        """Brands with typical stream paths (from config/camera_presets.yaml) and the user's own templates."""
        return {"brands": cfg["camera_presets"], "templates": db.list_templates()}

    @app.post("/api/camera-templates", status_code=201)
    def save_template(body: TemplateBody, user=Depends(admin_only)):
        name = body.name.strip()[:60]
        if not name:
            raise RegisterError("MISSING_FIELD", "Template name is required", "template_name")
        cleaned = cameras.clean({"name": name, "host": "x", "path": body.path, "port": body.port,
                                 "username": body.username, "transport": body.transport})
        db.save_template(name, cleaned.get("path", ""), cleaned["port"], cleaned.get("username", ""),
                         cleaned["transport"], body.note.strip()[:200])
        db.audit(user["username"], "camera_template_saved", {"name": name})
        return {"templates": db.list_templates()}

    @app.delete("/api/camera-templates/{template_id}", status_code=204)
    def delete_template(template_id: int, user=Depends(admin_only)):
        db.delete_template(template_id)
        db.audit(user["username"], "camera_template_deleted", {"id": template_id})
        return Response(status_code=204)

    @app.post("/api/cameras/discover")
    def discover(body: CameraBody, channel: int = 1, user=Depends(admin_only)):
        """Try the known stream paths on a camera and list the ones that give a picture."""
        sent = {k: v for k, v in body.model_dump().items() if v is not None and k not in ("id", "name")}
        saved = db.get_camera(body.id) if body.id else None
        if sent.get("password") == "":
            sent.pop("password")
        cam = {"transport": "tcp", "port": 554, "path": "", "username": "", "password": "",
               **(saved or {}), **cameras.clean({"name": "x", **sent}, partial=bool(saved))}
        candidates = cameras.candidate_paths(cfg["camera_presets"], db.list_templates(), channel)
        db.audit(user["username"], "camera_path_search", {"host": cam["host"], "paths": len(candidates)})
        return cameras.discover_paths(cam, candidates, opener=opener, reachable=reachable)

    @app.post("/api/cameras", status_code=201)
    def add_camera(body: CameraBody, user=Depends(admin_only)):
        data = cameras.clean({k: v for k, v in body.model_dump().items() if v is not None and k != "id"})
        data = {"location": "", "direction": "in", "port": 554, "path": "", "username": "",
                "password": "", "transport": "tcp", "fps": 10.0, "enabled": 1, **data}
        camera_id = "cam-" + secrets.token_hex(3)
        db.add_camera(camera_id, data)
        db.audit(user["username"], "camera_added", {"id": camera_id, "name": data["name"],
                                                    "host": data["host"]})
        return cameras.public(db.get_camera(camera_id))

    # ---- live IP camera view -------------------------------------------------
    def live_worker(camera_id):
        worker = workers.ensure(camera_id)
        if not worker:
            raise HTTPException(404, "No enabled IP camera with this id")
        return worker

    @app.get("/api/cameras/{camera_id}/status")
    def camera_status(camera_id: str, since: int = 0, user=Depends(current_user)):
        """State of the live view: connecting / live / reconnecting, fps, latest results."""
        return live_worker(camera_id).status(since)

    @app.get("/api/cameras/{camera_id}/stream")
    def camera_stream(camera_id: str, user=Depends(current_user)):
        """The camera as a live picture with face boxes (MJPEG: use it as an <img> source)."""
        worker = live_worker(camera_id)

        def frames():
            last = None
            while worker.alive():
                worker.touch()
                jpeg = worker.jpeg
                if jpeg is not last:
                    last = jpeg
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                           + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                time.sleep(0.08)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                                 headers={"Cache-Control": "no-store"})

    @app.patch("/api/cameras/{camera_id}")
    def edit_camera(camera_id: str, body: CameraBody, user=Depends(admin_only)):
        cam = db.get_camera(camera_id)
        if not cam:
            raise HTTPException(404, "No such camera")
        sent = {k: v for k, v in body.model_dump().items() if v is not None and k != "id"}
        if cam["builtin"]:                       # the laptop camera: only name, location, enabled
            sent = {k: v for k, v in sent.items() if k in ("name", "location", "enabled")}
        if sent.get("password") == "":           # empty password box on edit = keep the old one
            sent.pop("password")
        data = cameras.clean(sent, partial=True)
        db.update_camera(camera_id, data)
        workers.stop(camera_id)      # reconnect with the new settings next time it is viewed
        db.audit(user["username"], "camera_edited",
                 {"id": camera_id, **{k: v for k, v in data.items() if k != "password"}})
        return cameras.public(db.get_camera(camera_id))

    @app.delete("/api/cameras/{camera_id}", status_code=204)
    def delete_camera(camera_id: str, request: Request, user=Depends(admin_only)):
        cam = db.get_camera(camera_id)
        if not cam:
            raise HTTPException(404, "No such camera")
        if cam["builtin"]:
            raise HTTPException(400, "The laptop camera cannot be deleted")
        check_step_up(request, user, "camera_delete")
        workers.stop(camera_id)
        db.delete_camera(camera_id)
        db.audit(user["username"], "camera_deleted", {"id": camera_id, "name": cam["name"]})
        return Response(status_code=204)

    @app.post("/api/cameras/test")
    def test_camera(body: CameraBody, user=Depends(admin_only)):
        """Try a camera before (or after) saving it. Uses the saved password if none is typed."""
        saved = db.get_camera(body.id) if body.id else None
        sent = {k: v for k, v in body.model_dump().items() if v is not None and k not in ("id", "name")}
        if sent.get("password") == "":
            sent.pop("password")
        cam = {"transport": "tcp", "port": 554, "path": "", "username": "", "password": "",
               **(saved or {}), **cameras.clean({"name": "test", **sent}, partial=bool(saved))}
        if cam.get("kind") == "browser":
            raise RegisterError("NOT_IP", "The laptop camera is tested in the browser, not here")
        cam["kind"] = "rtsp"
        db.audit(user["username"], "camera_tested", {"host": cam["host"]})
        return cameras.test_connection(cam, opener=opener)

    @app.post("/api/check")
    def check(body: CheckRequest, user=Depends(current_user)):
        return recognizer.check(decode_image(body.image))

    # ---- admin only --------------------------------------------------------
    @app.post("/api/people", status_code=201)
    def register(body: NewPerson, request: Request, user=Depends(admin_only)):
        if watchlist_type(body.person_type):
            check_step_up(request, user, "watchlist_change")
        images = [decode_image(i) for i in body.images]
        data = body.model_dump(exclude={"images", "consent"})
        data["watch"] = {**(body.watch or {}), "added_by": user["username"]}
        created = recognizer.register(data, images, body.consent)
        db.audit(user["username"], "person_created", {"id": created["id"], "code": created["code"],
                                                      "name": body.name.strip(), "type": body.person_type,
                                                      "unit": body.unit.strip(), "photos": len(images)})
        if access.person_type(cfg, body.person_type).get("watchlist"):
            db.audit(user["username"], "watchlist_added", {"code": created["code"], "type": body.person_type})
        return {**created, "name": body.name.strip()}

    @app.patch("/api/people/{person_id}")
    def edit_person(person_id: int, body: PersonEdit, request: Request, user=Depends(admin_only)):
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(404, "No such person")
        if body.status not in (None, "active", "disabled"):
            raise HTTPException(400, "Bad status")
        # any change to a watch-list person, or turning someone INTO one, needs a confirmation
        if watchlist_type(person["person_type"]) or (body.person_type and watchlist_type(body.person_type)):
            check_step_up(request, user, "watchlist_change")
        sent = body.model_dump(exclude_none=True)
        status = sent.pop("status", None)
        core = {}
        if sent:   # details changed: check the whole record again (a status switch alone skips this)
            merged = {"name": person["name"], "phone": person["phone"], "person_type": person["person_type"],
                      "unit": person["unit"], "valid_from": date_text(person["valid_from"]),
                      "valid_until": date_text(person["valid_until"]), "notes": person["notes"],
                      "fields": person["fields"],
                      "watch": {**person["watch"], "review_by": date_text(person["watch"].get("review_by"))}, **sent}
            if "watch" in sent:
                merged["watch"] = {**merged["watch"], **sent["watch"], "added_by": person["watch"].get("added_by", "")}
            cleaned = recognizer.clean_profile(merged, existing=person)
            fields = cleaned.pop("fields")
            core = cleaned
            if cleaned["watch"] or person["watch"]:
                db.audit(user["username"], "watchlist_edited", {"code": person["code"]})
        else:
            fields = None
        db.update_person(person_id, fields=fields, status=status, **core)
        db.audit(user["username"], "person_edited", {"id": person_id, "code": person["code"],
                                                     "changed": sorted(body.model_dump(exclude_none=True))})
        return person_view(db.get_person(person_id), user)

    @app.post("/api/people/{person_id}/photos")
    def change_person_photos(person_id: int, body: PhotosBody, request: Request, user=Depends(admin_only)):
        """Replace (or add to) the photos of a registered person, for example after a wrong photo was uploaded.
        Changing the face that opens the door is an identity change, so it needs a confirmation."""
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(404, "No such person")
        if not body.images:
            raise ApiError(400, "PHOTO_COUNT", "Send at least one photo", "photos")
        # check the photos first, so a wrong file does not use up the one-time confirmation
        vectors, jpegs = recognizer.process_photos([decode_image(i) for i in body.images[:10]], for_person=person_id)
        check_step_up(request, user, "person_photos")
        total = db.change_photos(person_id, vectors, jpegs, body.replace)
        db.audit(user["username"], "person_photos_changed", {"id": person_id, "code": person["code"],
                                                              "mode": "replace" if body.replace else "add",
                                                              "added": len(vectors), "total": total})
        return {"photos": [{"id": p["id"]} for p in db.list_photos(person_id)]}

    @app.delete("/api/people/{person_id}/photos/{photo_id}")
    def delete_person_photo(person_id: int, photo_id: int, request: Request, user=Depends(admin_only)):
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(404, "No such person")
        check_step_up(request, user, "person_photos")
        if not db.delete_photo(person_id, photo_id):
            raise ApiError(400, "LAST_PHOTO", "A person needs at least one photo. Add the new photo first, then remove this one.")
        db.audit(user["username"], "person_photo_removed", {"id": person_id, "code": person["code"]})
        return {"photos": [{"id": p["id"]} for p in db.list_photos(person_id)]}

    @app.delete("/api/people/{person_id}", status_code=204)
    def delete_person(person_id: int, request: Request, user=Depends(admin_only)):
        person = db.get_person(person_id)
        if not person:
            raise HTTPException(404, "No such person")
        check_step_up(request, user, "person_delete")
        db.delete_person(person_id)
        db.audit(user["username"], "person_deleted", {"id": person_id, "name": person["name"]})
        return Response(status_code=204)

    @app.get("/api/audit")
    def audit_log(limit: int = 100, offset: int = 0, user=Depends(admin_only)):
        return db.list_audit(min(limit, 500), offset)

    @app.get("/api/audit/verify")
    def audit_verify(user=Depends(admin_only)):
        """Check that nobody changed or removed old audit lines (each line is chained to the one before)."""
        return db.verify_audit()

    # ---- user accounts (admin) ------------------------------------------------
    def user_view(u):
        return {"id": u["id"], "username": u["username"], "role": u["role"], "active": u["active"]}

    @app.get("/api/users")
    def list_users(user=Depends(admin_only)):
        return [user_view(u) for u in db.list_users()]

    @app.post("/api/users", status_code=201)
    def create_user(body: UserCreate, request: Request, user=Depends(admin_only)):
        check_step_up(request, user, "user_manage")
        name = body.username.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{3,32}", name):
            raise ApiError(400, "BAD_USERNAME", "User name: 3 to 32 letters, digits, dot, dash or underscore", "username")
        if body.role not in ("admin", "viewer", "resident"):
            raise ApiError(400, "BAD_ROLE", "Role must be admin, viewer or resident", "role")
        problem = auth.password_problem(body.password, name, security["min_password_length"])
        if problem:
            raise ApiError(400, "WEAK_PASSWORD", problem, "password")
        if db.get_user(username=name):
            raise ApiError(400, "USER_EXISTS", "This user name is already taken", "username")
        user_id = db.add_user(name, auth.hash_password(body.password), body.role)
        db.audit(user["username"], "user_created", {"username": name, "role": body.role})
        return user_view(db.get_user(user_id=user_id))

    @app.patch("/api/users/{user_id}")
    def edit_user(user_id: int, body: UserEdit, request: Request, user=Depends(admin_only)):
        target = db.get_user(user_id=user_id)
        if not target:
            raise HTTPException(404, "No such user")
        check_step_up(request, user, "user_manage")
        if body.role not in (None, "admin", "viewer", "resident"):
            raise ApiError(400, "BAD_ROLE", "Role must be admin, viewer or resident", "role")
        losing_admin = target["role"] == "admin" and target["active"] and (
            body.active is False or body.role in ("viewer", "resident"))
        if losing_admin and db.count_active_admins() <= 1:
            raise ApiError(400, "LAST_ADMIN", "There must always be one active administrator")
        if user_id == user["id"] and (body.active is False or body.role in ("viewer", "resident")):
            raise ApiError(400, "SELF_LOCKOUT", "You cannot disable or demote your own account")
        pw_hash = None
        if body.password is not None:
            problem = auth.password_problem(body.password, target["username"], security["min_password_length"])
            if problem:
                raise ApiError(400, "WEAK_PASSWORD", problem, "password")
            pw_hash = auth.hash_password(body.password)
        db.update_user(user_id, role=body.role, active=body.active, pw_hash=pw_hash)
        db.audit(user["username"], "user_edited", {"username": target["username"],
                                                   "changed": sorted(k for k, v in body.model_dump().items() if v is not None)})
        return user_view(db.get_user(user_id=user_id))

    # ---- the web page ------------------------------------------------------
    @app.get("/")
    @app.get("/tf-check")          # the realtime scan page: same single page, the script picks the view
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
