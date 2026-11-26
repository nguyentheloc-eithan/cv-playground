"""Business rules shared by the device, customer and admin APIs."""
import hashlib
import json
import logging
import secrets
import time

from sqlalchemy import delete, func, select, text, update

from . import db, notify, security, settings, storage
from .db import (alerts, audit, cameras, dept_roles, departments, events, face_vectors, inventory, invoices, many, now, one, payments, people, plans,
                 security_log, sessions, tenants, ticket_messages, tickets, users, vectors)

log = logging.getLogger("solavis")
STATUSES = ("lead", "trial", "active", "past_due", "suspended", "closed")


def record(c, actor, action, target="", tenant_id=None):
    c.execute(audit.insert().values(ts=now(), actor=actor, action=action, target=str(target), tenant_id=tenant_id))


# ───────── subscription ─────────
def entitlement(c, tenant_id):
    """Plan + limits + effective status. 'trial' that ran out and 'past_due' beyond the grace period count as suspended."""
    t = one(c, select(tenants, plans.c.name.label("plan_name"), plans.c.max_cameras, plans.c.max_people,
                      plans.c.events_per_day, plans.c.watchlist, plans.c.price_vnd)
            .join(plans, plans.c.id == tenants.c.plan_id).where(tenants.c.id == tenant_id))
    cfg = settings.get().tenancy
    st = t["status"]
    if st == "trial" and t["trial_end"] and t["trial_end"] < now():
        st = "suspended"
    if st == "past_due" and t["past_due_since"] and now() - t["past_due_since"] > cfg.past_due_grace_days * 86400:
        st = "suspended"
    t["effective_status"] = st
    t["upload_ok"] = st in ("trial", "active", "past_due")
    day = now() - (now() % 86400)
    t["events_today"] = c.execute(select(func.count()).select_from(events).where(events.c.tenant_id == tenant_id, events.c.ts >= day)).scalar()
    return t


# ───────── alerts ─────────
def add_alert(c, tenant_id, camera_id, level, kind, text, snap=None):
    c.execute(alerts.insert().values(tenant_id=tenant_id, camera_id=camera_id, ts=now(), level=level, kind=kind, text=text, snap=snap, acked=False))
    chat = c.execute(select(tenants.c.telegram_chat).where(tenants.c.id == tenant_id)).scalar()
    notify.send(level, text, chat, tenant_id)


# ───────── tamper ─────────
def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def lock_camera(c, cam, reason, text):
    """Lock once. The update is conditional, so two workers racing cannot raise two alerts."""
    r = c.execute(update(cameras).where(cameras.c.id == cam["id"], cameras.c.state != "locked").values(state="locked", lock_reason=reason))
    if r.rowcount:
        add_alert(c, cam["tenant_id"], cam["id"], "critical", "tamper", f"{cam['name']}: {text}. The camera is locked.")
        record(c, f"camera:{cam['id']}", "lock", reason, cam["tenant_id"])
        return True
    return False


def evaluate_tamper(c, cam, tilt, heading, cover_closed, hist):
    """Compare a check-in with the armed baseline. Returns True if it locked the camera."""
    cfg = settings.get().tamper
    from . import recog
    if not cover_closed and cfg.lock_on.cover_opened:
        return lock_camera(c, cam, "cover_opened", "the cover or magnet was opened or removed")
    if cfg.lock_on.moved and abs(tilt - (cam["base_tilt"] or 0)) > cfg.tilt_limit_degrees:
        return lock_camera(c, cam, "moved", f"the camera was moved (tilt changed {abs(tilt - cam['base_tilt']):.0f} degrees)")
    if cfg.lock_on.turned and angle_diff(heading, cam["base_heading"] or 0) > cfg.heading_limit_degrees:
        return lock_camera(c, cam, "turned", f"the camera was turned ({angle_diff(heading, cam['base_heading']):.0f} degrees)")
    if cfg.lock_on.view_changed and hist is not None and cam["base_hist"]:
        if recog.correlation(json.loads(cam["base_hist"]), hist) < cfg.view_similarity_min:
            return lock_camera(c, cam, "view_changed", "the view changed or the lens was covered")
    return False


# ───────── provisioning (used by admin API and seed packages) ─────────
def create_tenant(c, name, plan_id=None, status="trial", actor="system", trial_days=None):
    cfg = settings.get().tenancy
    plan_id = plan_id or cfg.default_plan
    if not c.execute(select(plans.c.id).where(plans.c.id == plan_id)).first():
        raise ValueError(f"unknown plan {plan_id}")
    if status not in STATUSES:
        raise ValueError(f"bad status {status}")
    trial_end = now() + (trial_days if trial_days is not None else cfg.trial_days) * 86400 if status == "trial" else None
    tid = db.insert(c, tenants, name=name, plan_id=plan_id, status=status, trial_end=trial_end, created=now())
    record(c, actor, "tenant_create", name, tid)
    return tid


def create_user(c, email, password=None, role="owner", tenant_id=None, name="", actor="system", must_change=None, staff_role=None):
    """Returns (user_id, password). A random password is generated when none is given."""
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("invalid email")
    if c.execute(select(users.c.id).where(users.c.email == email)).first():
        raise ValueError(f"{email} already exists")
    if role not in ("owner", "member", "staff"):
        raise ValueError("role must be owner, member or staff")
    if role != "staff":
        n = c.execute(select(func.count()).select_from(users).where(users.c.tenant_id == tenant_id)).scalar()
        if n >= settings.get().tenancy.max_users_per_tenant:
            raise ValueError("user limit of this customer reached")
    generated = password is None
    password = password or security.temp_password()
    if not generated and (msg := security.check_password_rules(password)):
        raise ValueError(msg)
    if must_change is None:
        must_change = generated and settings.get().security.password.must_change_on_first_login
    uid = db.insert(c, users, tenant_id=tenant_id if role != "staff" else None, email=email, name=name or email.split("@")[0],
                    pw_hash=security.hash_password(password), role=role, active=True, must_change_pw=must_change, created=now(),
                    staff_role=None)
    record(c, actor, "user_create", f"{email}/{role}", tenant_id)
    return uid, password


def create_camera(c, tenant_id, name, claim_code=None, actor="system", source_type="solavis_cam", serial=None):
    t = entitlement(c, tenant_id)
    n = c.execute(select(func.count()).select_from(cameras).where(cameras.c.tenant_id == tenant_id)).scalar()
    if n >= t["max_cameras"]:
        raise ValueError(f"plan {t['plan_name']} allows {t['max_cameras']} camera(s)")
    code = claim_code or security.claim_code()
    cid = db.insert(c, cameras, tenant_id=tenant_id, name=name, claim_code=code, state="unclaimed", source_type=source_type, created=now())
    record(c, actor, "camera_create", f"{name} {code}", tenant_id)
    if serial:
        row = one(c, select(inventory).where(inventory.c.serial == serial))
        if row:
            c.execute(update(inventory).where(inventory.c.id == row["id"]).values(status="assigned", tenant_id=tenant_id, camera_id=cid, assigned_at=now()))
    return cid, code


def add_person(c, tenant_id, name, kind, consent, vecs, actor):
    pid = db.insert(c, people, tenant_id=tenant_id, name=name, kind=kind, consent=consent, created=now())
    for v in vecs:
        c.execute(vectors.insert().values(person_id=pid, tenant_id=tenant_id, vec=v.astype("float32").tobytes()))
    record(c, actor, "person_add", f"{name}/{kind}", tenant_id)
    return pid


# ───────── background jobs ─────────
def quiet_check():
    """Armed cameras that missed check-ins raise one alert (power cut, jamming, theft)."""
    cfg = settings.get().tamper
    limit = cfg.checkin_seconds * cfg.quiet_after_missed
    with db.tx() as c:
        for cam in many(c, select(cameras).where(cameras.c.state.in_(("armed", "locked")), cameras.c.last_seen.isnot(None),
                                                 cameras.c.quiet_alerted == False)):  # noqa: E712
            if now() - cam["last_seen"] > limit:
                r = c.execute(update(cameras).where(cameras.c.id == cam["id"], cameras.c.quiet_alerted == False).values(quiet_alerted=True))  # noqa: E712
                if r.rowcount:
                    add_alert(c, cam["tenant_id"], cam["id"], "high", "offline",
                              f"{cam['name']} has not checked in for {int(now() - cam['last_seen'])} s. Power cut, jamming or theft?")


def retention():
    cfg = settings.get().tenancy.retention_days
    store = storage.store()
    with db.tx() as c:
        for kind_filter, days in (((events.c.verdict == "unknown") | (events.c.verdict == "uncertain"), cfg.unknown_events),
                                  (events.c.verdict == "known", cfg.known_events)):
            old = many(c, select(events.c.id, events.c.snap).where(kind_filter, events.c.ts < now() - days * 86400))
            for e in old:
                if e["snap"]:
                    try:
                        store.delete(e["snap"])
                    except Exception:
                        pass
            if old:
                c.execute(delete(events).where(events.c.id.in_([e["id"] for e in old])))
        c.execute(delete(alerts).where(alerts.c.ts < now() - cfg.alerts * 86400))
        # captured frames of sign-in attempts are biometric data: keep them only as long as configured (the log record stays)
        keep = settings.get().security.face.snapshot_retention_days * 86400
        for r in many(c, select(security_log.c.snap).where(security_log.c.snap.isnot(None), security_log.c.ts < now() - keep)):
            try:
                store.delete(r["snap"])
            except Exception:
                pass
        # a suspended customer is closed after the configured number of days
        limit = settings.get().tenancy.closed_after_days * 86400
        for t in many(c, select(tenants).where(tenants.c.status == "suspended")):
            if t["closed_at"] is None:
                c.execute(update(tenants).where(tenants.c.id == t["id"]).values(closed_at=now()))
            elif now() - t["closed_at"] > limit:
                c.execute(update(tenants).where(tenants.c.id == t["id"]).values(status="closed"))
                record(c, "system", "tenant_closed", t["name"], t["id"])


def session_cleanup():
    with db.tx() as c:
        c.execute(delete(sessions).where(sessions.c.expires < now()))


# ───────── permissions (dynamic: department ceiling, role, per-person grants) ─────────
def _j(text):
    try:
        return list(json.loads(text)) if text else []
    except Exception:
        return []


def effective_perms(c, u):
    """What this staff member may do right now. The President holds everything ("*").
    Everyone else: (role + personal grants - personal denials), limited to the department ceiling.
    A department head holds the whole ceiling."""
    if u["role"] != "staff":
        return []
    if u.get("is_super"):
        return ["*"]
    d = one(c, select(departments).where(departments.c.id == u.get("department_id")))
    if not d or not d["active"]:
        return []
    ceiling = set(_j(d["ceiling"]))
    if d["head_user_id"] == u["id"]:
        base = set(ceiling)
    else:
        base = set()
        if u.get("role_id"):
            r = one(c, select(dept_roles).where(dept_roles.c.id == u["role_id"], dept_roles.c.department_id == d["id"]))
            if r:
                base = set(_j(r["permissions"]))
    base |= set(_j(u.get("extra_perms")))
    base -= set(_j(u.get("denied_perms")))
    return sorted(base & ceiling)


def perms_for(user):
    return user.get("perms", [])


def can(user, perm):
    p = user.get("perms", [])
    return "*" in p or perm in p


def is_head_of(c, u, dept_id):
    return bool(one(c, select(departments.c.id).where(departments.c.id == dept_id, departments.c.head_user_id == u["id"])))


def may_manage_dept(c, u, dept_id):
    """The President manages every department; a head manages only their own."""
    return bool(u.get("is_super")) or is_head_of(c, u, dept_id)


# ───────── tamper-evident security log (hash chain) ─────────
def _chain_payload(r):
    return json.dumps({"ts": r["ts"], "user_id": r["user_id"], "actor": r["actor"], "event": r["event"], "ok": bool(r["ok"]),
                       "detail": r["detail"], "ip": r["ip"], "snap": r["snap"]}, sort_keys=True, separators=(",", ":"))


def sec_log(c, event, ok=True, user=None, actor=None, detail=None, ip="", ua="", snap=None):
    """Append one record. Each record's hash covers the previous hash, so editing or deleting history breaks the chain."""
    if c.dialect.name == "postgresql":
        c.execute(text("select pg_advisory_xact_lock(7001)"))         # one writer at a time keeps the chain linear
    prev = c.execute(select(security_log.c.hash).order_by(security_log.c.id.desc()).limit(1)).scalar() or "0" * 64
    row = {"ts": round(now(), 3), "user_id": user["id"] if user else None, "actor": actor or (user["email"] if user else "?"), "event": event, "ok": bool(ok),
           "detail": json.dumps(detail, sort_keys=True, default=str) if detail is not None else "", "ip": ip or "", "snap": snap}
    h = hashlib.sha256((prev + _chain_payload(row)).encode()).hexdigest()
    c.execute(security_log.insert().values(prev_hash=prev, hash=h, ua=(ua or "")[:200], **row))


def verify_chain(c):
    prev, n = "0" * 64, 0
    for r in c.execute(select(security_log).order_by(security_log.c.id)).mappings():
        r = dict(r)
        if r["prev_hash"] != prev or hashlib.sha256((prev + _chain_payload(r)).encode()).hexdigest() != r["hash"]:
            return {"ok": False, "records": n, "broken_at": r["id"]}
        prev, n = r["hash"], n + 1
    return {"ok": True, "records": n, "broken_at": None}


# ───────── departments, roles, staff ─────────
def sync_departments(c, cfg_departments):
    """Copy the shipped departments and their starter roles into the database when missing (never overwrites edits)."""
    for d in cfg_departments:
        row = one(c, select(departments).where(departments.c.code == d.code))
        did = row["id"] if row else db.insert(c, departments, code=d.code, name=d.name, description=d.description, ceiling=json.dumps(d.ceiling), active=True, created=now())
        if not row:
            for r in d.roles:
                db.insert(c, dept_roles, department_id=did, name=r.name, permissions=json.dumps(r.permissions), created_by="system", created=now())


def clamp_to_ceiling(c, dept_id):
    """After a ceiling shrinks, drop rights above it from roles and personal grants so stored data matches reality."""
    d = one(c, select(departments).where(departments.c.id == dept_id))
    ceiling = set(_j(d["ceiling"]))
    for r in many(c, select(dept_roles).where(dept_roles.c.department_id == dept_id)):
        keep = [p for p in _j(r["permissions"]) if p in ceiling]
        c.execute(update(dept_roles).where(dept_roles.c.id == r["id"]).values(permissions=json.dumps(keep)))
    for u in many(c, select(users).where(users.c.department_id == dept_id)):
        c.execute(update(users).where(users.c.id == u["id"]).values(extra_perms=json.dumps([p for p in _j(u["extra_perms"]) if p in ceiling])))


def check_within(c, dept_id, perms):
    from .permissions import unknown
    d = one(c, select(departments).where(departments.c.id == dept_id))
    if not d:
        raise ValueError("department not found")
    bad = unknown(perms)
    if bad:
        raise ValueError(f"unknown permission(s): {bad}")
    over = [p for p in perms if p not in set(_j(d["ceiling"]))]
    if over:
        raise ValueError(f"outside this department's ceiling: {over}")


def issue_enroll_code(c, user_id):
    """A one-time code (shown once) that allows a first face enrollment. Stored only as a hash."""
    a = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "-".join("".join(secrets.choice(a) for _ in range(4)) for _ in range(3))
    c.execute(update(users).where(users.c.id == user_id).values(enroll_hash=security.hash_token(code), enroll_expires=now() + settings.get().security.face.enroll_code_hours * 3600))
    return code


def create_staff(c, email, department_id, password=None, name="", job_title="", role_id=None, actor="system", is_super=False, head=False, must_change=None, face_required=None):
    """Create a staff account inside a department. Returns (user_id, password)."""
    d = one(c, select(departments).where(departments.c.id == department_id))
    if not d or not d["active"]:
        raise ValueError("department not found or inactive")
    if role_id and not one(c, select(dept_roles.c.id).where(dept_roles.c.id == role_id, dept_roles.c.department_id == department_id)):
        raise ValueError("that role does not belong to this department")
    uid, pw = create_user(c, email, password, "staff", None, name, actor, must_change)
    face = settings.get().security.face
    c.execute(update(users).where(users.c.id == uid).values(department_id=department_id, role_id=role_id, job_title=job_title, is_super=bool(is_super),
              face_required=bool(is_super and face.required_for_super_admin) if face_required is None else bool(face_required)))
    if head:
        c.execute(update(departments).where(departments.c.id == department_id).values(head_user_id=uid))
    record(c, actor, "staff_create", f"{email} dept={d['code']}{' head' if head else ''}{' PRESIDENT' if is_super else ''}")
    return uid, pw


# ───────── billing ─────────
def invoice_state(inv):
    """'overdue' is computed, never stored."""
    if inv["status"] == "sent" and inv["due"] and inv["due"] < now():
        return "overdue"
    return inv["status"]


def create_invoice(c, tenant_id, months=1, description=None, actor="system", issued=None, status="sent"):
    t = entitlement(c, tenant_id)
    plan = one(c, select(plans).where(plans.c.id == t["plan_id"]))
    cfg = settings.get().billing
    months = max(1, int(months))
    sub = int(plan["price_vnd"] or 0) * months
    tax = round(sub * cfg.tax_rate_percent / 100)
    issued = issued or now()
    iid = db.insert(c, invoices, number="tmp", tenant_id=tenant_id, plan_id=plan["id"],
                    description=description or f"Solavis {plan['name']} plan, {months} month(s)",
                    period_start=issued, period_end=issued + months * 30 * 86400, subtotal=sub, tax=tax, total=sub + tax,
                    status=status, issued=issued, due=issued + cfg.due_days * 86400)
    number = f"{cfg.invoice_prefix}-{time.strftime('%y%m', time.localtime(issued))}-{iid:04d}"
    c.execute(update(invoices).where(invoices.c.id == iid).values(number=number))
    record(c, actor, "invoice_create", f"{number} {sub + tax}", tenant_id)
    return iid, number


def mark_paid(c, invoice_id, method, ref, actor):
    inv = one(c, select(invoices).where(invoices.c.id == invoice_id))
    if not inv:
        raise ValueError("invoice not found")
    if inv["status"] in ("paid", "void"):
        raise ValueError(f"invoice is already {inv['status']}")
    db.insert(c, payments, invoice_id=invoice_id, amount=inv["total"], method=method or "bank_transfer", ref=ref or "", ts=now(), recorded_by=actor)
    c.execute(update(invoices).where(invoices.c.id == invoice_id).values(status="paid", paid_at=now()))
    # paying an overdue account brings it back
    t = one(c, select(tenants).where(tenants.c.id == inv["tenant_id"]))
    if t["status"] in ("past_due", "suspended", "trial", "lead"):
        c.execute(update(tenants).where(tenants.c.id == t["id"]).values(status="active", past_due_since=None, closed_at=None))
        record(c, actor, "tenant_activated_by_payment", inv["number"], t["id"])
    record(c, actor, "invoice_paid", f"{inv['number']} {method} {ref}", inv["tenant_id"])


def mrr(c):
    return c.execute(select(func.coalesce(func.sum(plans.c.price_vnd), 0)).select_from(tenants.join(plans, plans.c.id == tenants.c.plan_id))
                     .where(tenants.c.status.in_(("active", "past_due")))).scalar()


# ───────── tickets ─────────
def ticket_message(c, ticket_id, author, author_type, body, internal=False):
    c.execute(ticket_messages.insert().values(ticket_id=ticket_id, author=author, author_type=author_type, body=body, internal=internal, created=now()))
    vals = {"updated": now()}
    t = one(c, select(tickets).where(tickets.c.id == ticket_id))
    if author_type == "staff" and not internal and not t["first_reply_at"]:
        vals["first_reply_at"] = now()
    if author_type == "customer" and t["status"] in ("pending", "solved"):
        vals["status"] = "open"
    if author_type == "staff" and not internal and t["status"] == "open":
        vals["status"] = "pending"          # waiting for the customer
    c.execute(update(tickets).where(tickets.c.id == ticket_id).values(**vals))
