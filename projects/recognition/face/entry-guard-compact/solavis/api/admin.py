"""Staff console API: the company's CRM. Accounts, contacts, notes, tasks, staff, audit, system.
Staff see business data and device *status*. They never see faces, snapshots or people lists."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select, update, delete

from .. import db, security, services, settings, storage
from ..db import (alerts, audit, cameras, contacts, events, inventory, invoices, many, notes, now, one, people, plans, tasks, tenants,
                  tickets, users)
from .deps import need, staff

router = APIRouter(prefix="/api/admin", tags=["admin"])
PROFILE = ("name", "contact_name", "phone", "address", "tax_code", "industry", "source", "account_manager")


def bad(msg):
    raise HTTPException(400, msg)


@router.get("/summary")
def summary(u=Depends(need("accounts.read"))):
    day, t = now() - now() % 86400, settings.get().tamper
    with db.tx() as c:
        n = lambda tb, *w: c.execute(select(func.count()).select_from(tb).where(*w)).scalar()  # noqa: E731
        by = {s: n(tenants, tenants.c.status == s) for s in services.STATUSES}
        overdue = [i for i in many(c, select(invoices).where(invoices.c.status == "sent", invoices.c.due < now()))]
        mtd = now() - 30 * 86400
        out = {"mrr": services.mrr(c), "tenants": n(tenants, True), "by_status": by,
               "trials_ending": many(c, select(tenants.c.id, tenants.c.name, tenants.c.trial_end).where(tenants.c.status == "trial", tenants.c.trial_end < now() + 7 * 86400).order_by(tenants.c.trial_end)),
               "overdue_count": len(overdue), "overdue_amount": sum(i["total"] for i in overdue),
               "new_30d": n(tenants, tenants.c.created > mtd), "churn_30d": n(tenants, tenants.c.status == "closed", tenants.c.closed_at > mtd),
               "tickets_open": n(tickets, tickets.c.status.in_(("open", "pending"))), "tickets_unassigned": n(tickets, tickets.c.status == "open", tickets.c.assignee.is_(None)),
               "fleet": {"units": n(inventory, inventory.c.status == "assigned"), "in_stock": n(inventory, inventory.c.status == "in_stock"), "rma": n(inventory, inventory.c.status == "rma"),
                         "online": n(cameras, cameras.c.last_seen > now() - t.checkin_seconds * t.quiet_after_missed), "locked": n(cameras, cameras.c.state == "locked")},
               "events_today": n(events, events.c.ts >= day),
               "my_tasks": many(c, select(tasks, tenants.c.name.label("tenant")).join(tenants, tenants.c.id == tasks.c.tenant_id, isouter=True)
                                .where(tasks.c.status == "open", tasks.c.assignee == u["email"]).order_by(tasks.c.due).limit(8)),
               "recent_tickets": many(c, select(tickets, tenants.c.name.label("tenant")).join(tenants, tenants.c.id == tickets.c.tenant_id)
                                      .where(tickets.c.status.in_(("open", "pending"))).order_by(tickets.c.updated.desc()).limit(6))}
        return out


# ───────── accounts (customers) ─────────
def _row(c, tid):
    e = services.entitlement(c, tid)
    e["cameras"] = c.execute(select(func.count()).select_from(cameras).where(cameras.c.tenant_id == tid)).scalar()
    e["people"] = c.execute(select(func.count()).select_from(people).where(people.c.tenant_id == tid)).scalar()
    e["users"] = c.execute(select(func.count()).select_from(users).where(users.c.tenant_id == tid)).scalar()
    e["open_tickets"] = c.execute(select(func.count()).select_from(tickets).where(tickets.c.tenant_id == tid, tickets.c.status.in_(("open", "pending")))).scalar()
    e["unpaid"] = c.execute(select(func.coalesce(func.sum(invoices.c.total), 0)).where(invoices.c.tenant_id == tid, invoices.c.status == "sent")).scalar()
    return e


@router.get("/tenants")
def list_tenants(q: str = "", status: str = "", u=Depends(need("accounts.read"))):
    stmt = select(tenants.c.id).order_by(tenants.c.id.desc())
    if status:
        stmt = stmt.where(tenants.c.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(tenants.c.name.ilike(like), tenants.c.contact_name.ilike(like), tenants.c.phone.ilike(like)))
    keep = ("id", "name", "plan_id", "plan_name", "status", "effective_status", "trial_end", "contact_name", "phone", "account_manager", "price_vnd",
            "cameras", "max_cameras", "people", "users", "open_tickets", "unpaid", "events_today", "events_per_day", "created")
    with db.tx() as c:
        rows = [_row(c, r["id"]) for r in many(c, stmt)]
        return [{k: row.get(k) for k in keep} for row in rows]


@router.post("/tenants")
def new_tenant(body: dict, u=Depends(need("accounts.write"))):
    with db.tx() as c:
        try:
            name = str(body.get("name", "")).strip() or bad("customer name required")
            tid = services.create_tenant(c, name, body.get("plan_id"), body.get("status", "trial"), u["email"], body.get("trial_days"))
            c.execute(update(tenants).where(tenants.c.id == tid).values(**{k: body[k] for k in PROFILE[1:] if body.get(k)}, account_manager=body.get("account_manager") or u["email"]))
            out = {"id": tid}
            if body.get("owner_email"):
                _, pw = services.create_user(c, body["owner_email"], role="owner", tenant_id=tid, name=body.get("contact_name", ""), actor=u["email"])
                out.update(owner_email=body["owner_email"].strip().lower(), temporary_password=pw)
            return out
        except ValueError as e:
            raise HTTPException(400, str(e))


@router.get("/tenants/{tid}")
def tenant_detail(tid: int, u=Depends(need("accounts.read"))):
    with db.tx() as c:
        t = one(c, select(tenants).where(tenants.c.id == tid))
        if not t:
            raise HTTPException(404)
        e = _row(c, tid)
        t.update({k: e[k] for k in ("effective_status", "plan_name", "max_cameras", "max_people", "events_per_day", "events_today", "price_vnd", "watchlist")})
        can_bill, can_support = services.can(u, "billing.read"), services.can(u, "support.read")
        devices = many(c, select(inventory.c.id, inventory.c.serial, inventory.c.model, inventory.c.status, inventory.c.warranty_until,
                                 cameras.c.name, cameras.c.state, cameras.c.last_seen, cameras.c.battery, cameras.c.net, cameras.c.fw_version, cameras.c.claim_code)
                       .join(cameras, cameras.c.id == inventory.c.camera_id, isouter=True).where(inventory.c.tenant_id == tid))
        have = {d["serial"] for d in devices}
        for cam in many(c, select(cameras).where(cameras.c.tenant_id == tid)):       # cameras added without an inventory unit
            if not any(d["name"] == cam["name"] for d in devices):
                devices.append({"serial": None, "model": cam["source_type"], "status": "assigned", "name": cam["name"], "state": cam["state"], "last_seen": cam["last_seen"],
                                "battery": cam["battery"], "net": cam["net"], "fw_version": cam["fw_version"], "claim_code": cam["claim_code"], "warranty_until": None})
        for d in devices:                                 # the claim code is only meaningful until the unit is claimed
            if d.get("state") != "unclaimed":
                d["claim_code"] = None
        return {"tenant": t, "contacts": many(c, select(contacts).where(contacts.c.tenant_id == tid)),
                "users": many(c, select(users.c.id, users.c.email, users.c.name, users.c.role, users.c.active, users.c.last_login).where(users.c.tenant_id == tid)),
                "notes": many(c, select(notes).where(notes.c.tenant_id == tid).order_by(notes.c.pinned.desc(), notes.c.id.desc())),
                "tasks": many(c, select(tasks).where(tasks.c.tenant_id == tid).order_by(tasks.c.status.desc(), tasks.c.due)),
                "tickets": many(c, select(tickets).where(tickets.c.tenant_id == tid).order_by(tickets.c.id.desc()).limit(30)) if can_support else [],
                "invoices": [dict(i, state=services.invoice_state(i)) for i in many(c, select(invoices).where(invoices.c.tenant_id == tid).order_by(invoices.c.id.desc()))] if can_bill else [],
                "devices": devices, "people_count": e["people"],
                "activity": many(c, select(audit).where(audit.c.tenant_id == tid).order_by(audit.c.id.desc()).limit(40))}


@router.post("/tenants/{tid}")
def update_tenant(tid: int, body: dict, u=Depends(need("accounts.write"))):
    vals = {k: body[k] for k in PROFILE if k in body}
    if "status" in body:
        if body["status"] not in services.STATUSES:
            bad("bad status")
        vals.update(status=body["status"], past_due_since=now() if body["status"] == "past_due" else None, closed_at=None)
        if body["status"] == "trial":
            vals["trial_end"] = now() + int(body.get("trial_days") or settings.get().tenancy.trial_days) * 86400
    if "plan_id" in body:
        vals["plan_id"] = body["plan_id"]
    if not vals:
        bad("nothing to change")
    with db.tx() as c:
        if "plan_id" in vals and not one(c, select(plans.c.id).where(plans.c.id == vals["plan_id"])):
            bad("unknown plan")
        c.execute(update(tenants).where(tenants.c.id == tid).values(**vals))
        services.record(c, u["email"], "tenant_update", {k: v for k, v in body.items()}, tid)
    return {"ok": True}


@router.post("/tenants/{tid}/contacts")
def add_contact(tid: int, body: dict, u=Depends(need("accounts.write"))):
    if not str(body.get("name", "")).strip():
        bad("name required")
    with db.tx() as c:
        cid = db.insert(c, contacts, tenant_id=tid, name=body["name"].strip(), email=body.get("email", ""), phone=body.get("phone", ""), title=body.get("title", ""), created=now())
    return {"id": cid}


@router.delete("/contacts/{cid}")
def del_contact(cid: int, u=Depends(need("accounts.write"))):
    with db.tx() as c:
        c.execute(delete(contacts).where(contacts.c.id == cid))
    return {"ok": True}


@router.post("/tenants/{tid}/notes")
def add_note(tid: int, body: dict, u=Depends(need("accounts.read"))):
    if not str(body.get("text", "")).strip():
        bad("note is empty")
    with db.tx() as c:
        nid = db.insert(c, notes, tenant_id=tid, author=u["email"], text=body["text"].strip(), pinned=bool(body.get("pinned")), created=now())
    return {"id": nid}


@router.post("/notes/{nid}/pin")
def pin_note(nid: int, u=Depends(need("accounts.read"))):
    with db.tx() as c:
        c.execute(update(notes).where(notes.c.id == nid).values(pinned=~notes.c.pinned))
    return {"ok": True}


@router.delete("/notes/{nid}")
def del_note(nid: int, u=Depends(need("accounts.write"))):
    with db.tx() as c:
        c.execute(delete(notes).where(notes.c.id == nid))
    return {"ok": True}


# ───────── tasks ─────────
@router.get("/tasks")
def list_tasks(scope: str = "mine", u=Depends(need("tasks"))):
    q = select(tasks, tenants.c.name.label("tenant")).join(tenants, tenants.c.id == tasks.c.tenant_id, isouter=True).order_by(tasks.c.status.desc(), tasks.c.due)
    if scope == "mine":
        q = q.where(tasks.c.assignee == u["email"])
    with db.tx() as c:
        return many(c, q.limit(200))


@router.post("/tasks")
def add_task(body: dict, u=Depends(need("tasks"))):
    if not str(body.get("title", "")).strip():
        bad("title required")
    with db.tx() as c:
        tid = db.insert(c, tasks, tenant_id=body.get("tenant_id"), title=body["title"].strip(), due=body.get("due"), status="open",
                        assignee=body.get("assignee") or u["email"], created_by=u["email"], created=now())
    return {"id": tid}


@router.post("/tasks/{tid}/done")
def done_task(tid: int, u=Depends(need("tasks"))):
    with db.tx() as c:
        c.execute(update(tasks).where(tasks.c.id == tid).values(status="done", done_at=now()))
    return {"ok": True}


# ───────── customer users (support actions) ─────────
@router.post("/users/{uid}/{action}")
def user_action(uid: int, action: str, u=Depends(need("accounts.write"))):
    with db.tx() as c:
        usr = one(c, select(users).where(users.c.id == uid))
        if not usr:
            raise HTTPException(404)
        if usr["role"] == "staff" and not services.can(u, "staff.manage"):
            raise HTTPException(403, "your role cannot manage staff")
        if action == "reset-password":
            pw = security.temp_password()
            c.execute(update(users).where(users.c.id == uid).values(pw_hash=security.hash_password(pw), must_change_pw=True))
            services.record(c, u["email"], "password_reset", usr["email"], usr["tenant_id"])
            return {"temporary_password": pw}
        if action in ("disable", "enable"):
            if uid == u["id"]:
                bad("you cannot disable yourself")
            c.execute(update(users).where(users.c.id == uid).values(active=(action == "enable")))
            services.record(c, u["email"], f"user_{action}", usr["email"], usr["tenant_id"])
            return {"ok": True}
    bad("unknown action")


# ───────── staff ─────────
@router.get("/staff")
def list_staff(u=Depends(need("staff.manage"))):
    with db.tx() as c:
        return many(c, select(users.c.id, users.c.email, users.c.name, users.c.staff_role, users.c.active, users.c.last_login).where(users.c.role == "staff"))


@router.get("/roles")
def roles(u=Depends(staff)):
    return settings.get().staff_roles.roles


@router.post("/staff")
def add_staff(body: dict, u=Depends(need("staff.manage"))):
    role = body.get("staff_role", "support")
    if role not in settings.get().staff_roles.roles:
        bad("unknown staff role")
    with db.tx() as c:
        try:
            _, pw = services.create_user(c, body.get("email", ""), role="staff", name=body.get("name", ""), actor=u["email"], staff_role=role)
        except ValueError as e:
            bad(str(e))
    return {"email": body["email"].strip().lower(), "temporary_password": pw}


@router.post("/staff/{uid}/role")
def set_staff_role(uid: int, body: dict, u=Depends(need("staff.manage"))):
    if body.get("staff_role") not in settings.get().staff_roles.roles:
        bad("unknown staff role")
    if uid == u["id"]:
        bad("you cannot change your own role")
    with db.tx() as c:
        c.execute(update(users).where(users.c.id == uid, users.c.role == "staff").values(staff_role=body["staff_role"]))
        services.record(c, u["email"], "staff_role", f"{uid} {body['staff_role']}")
    return {"ok": True}


@router.get("/audit")
def get_audit(limit: int = 150, tenant_id: int | None = None, u=Depends(need("audit.read"))):
    q = select(audit).order_by(audit.c.id.desc()).limit(min(limit, 500))
    if tenant_id:
        q = q.where(audit.c.tenant_id == tenant_id)
    with db.tx() as c:
        return many(c, q)


@router.get("/system")
def system(u=Depends(need("system.read"))):
    checks = {}
    for name, fn in (("database", db.ping), ("storage", lambda: storage.store().healthy())):
        try:
            checks[name] = "ok" if fn() else "fail"
        except Exception as e:
            checks[name] = f"fail: {e}"[:160]
    cfg = settings.get()
    return {"checks": checks, "config": settings.masked(cfg), "warnings": settings.check(cfg)}
