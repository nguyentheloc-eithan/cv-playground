"""Business rules shared by the device, customer and admin APIs."""
import json
import logging
import time

from sqlalchemy import delete, func, select, update

from . import db, notify, security, settings, storage
from .db import (alerts, audit, cameras, events, inventory, invoices, many, now, one, payments, people, plans, sessions, tenants,
                 ticket_messages, tickets, users, vectors)

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
                    staff_role=(staff_role or "admin") if role == "staff" else None)
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


# ───────── permissions ─────────
def perms_for(user):
    if user["role"] != "staff":
        return []
    allowed = settings.get().staff_roles.roles.get(user.get("staff_role") or "admin", [])
    return ["*"] if "*" in allowed else list(allowed)


def can(user, perm):
    p = perms_for(user)
    return "*" in p or perm in p


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
