"""Support tickets: customers open and reply; staff work the queue (internal notes stay hidden from customers)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from .. import db, services
from ..db import many, now, one, ticket_messages, tickets, tenants, users
from .deps import member, need

admin = APIRouter(prefix="/api/admin/tickets", tags=["support"])
customer = APIRouter(prefix="/api/tickets", tags=["support"])
STATUS = ("open", "pending", "solved", "closed")


@admin.get("")
def queue(status: str = "", assignee: str = "", u=Depends(need("support.read"))):
    q = select(tickets, tenants.c.name.label("tenant")).join(tenants, tenants.c.id == tickets.c.tenant_id).order_by(tickets.c.updated.desc()).limit(300)
    if status == "active":
        q = q.where(tickets.c.status.in_(("open", "pending")))
    elif status:
        q = q.where(tickets.c.status == status)
    if assignee == "me":
        q = q.where(tickets.c.assignee == u["email"])
    elif assignee == "none":
        q = q.where(tickets.c.assignee.is_(None))
    with db.tx() as c:
        return many(c, q)


@admin.get("/{tid}")
def get_ticket(tid: int, u=Depends(need("support.read"))):
    with db.tx() as c:
        t = one(c, select(tickets, tenants.c.name.label("tenant")).join(tenants, tenants.c.id == tickets.c.tenant_id).where(tickets.c.id == tid))
        if not t:
            raise HTTPException(404)
        return {"ticket": t, "messages": many(c, select(ticket_messages).where(ticket_messages.c.ticket_id == tid).order_by(ticket_messages.c.id))}


@admin.post("/{tid}/message")
def staff_reply(tid: int, body: dict, u=Depends(need("support.write"))):
    if not str(body.get("body", "")).strip():
        raise HTTPException(400, "message is empty")
    with db.tx() as c:
        if not one(c, select(tickets.c.id).where(tickets.c.id == tid)):
            raise HTTPException(404)
        services.ticket_message(c, tid, u["email"], "staff", body["body"].strip(), bool(body.get("internal")))
        c.execute(update(tickets).where(tickets.c.id == tid, tickets.c.assignee.is_(None)).values(assignee=u["email"]))
    return {"ok": True}


@admin.post("/{tid}")
def update_ticket(tid: int, body: dict, u=Depends(need("support.write"))):
    vals = {}
    if "status" in body:
        if body["status"] not in STATUS:
            raise HTTPException(400, "bad status")
        vals["status"] = body["status"]
        vals["solved_at"] = now() if body["status"] in ("solved", "closed") else None
    for k in ("priority", "assignee", "category"):
        if k in body:
            vals[k] = body[k] or None
    if vals.get("assignee"):
        with db.tx() as c:
            a = one(c, select(users).where(users.c.email == vals["assignee"], users.c.role == "staff", users.c.active == True))  # noqa: E712
            if not a or not services.can({"perms": services.effective_perms(c, a)}, "support.write"):
                raise HTTPException(400, "that person cannot work support tickets")
    if not vals:
        raise HTTPException(400, "nothing to change")
    with db.tx() as c:
        c.execute(update(tickets).where(tickets.c.id == tid).values(updated=now(), **vals))
        services.record(c, u["email"], "ticket_update", f"{tid} {body}", one(c, select(tickets.c.tenant_id).where(tickets.c.id == tid))["tenant_id"])
    return {"ok": True}


# ───── customer side ─────
@customer.get("")
def my_tickets(u=Depends(member)):
    with db.tx() as c:
        return many(c, select(tickets).where(tickets.c.tenant_id == u["tenant_id"]).order_by(tickets.c.updated.desc()).limit(100))


@customer.post("")
def open_ticket(body: dict, u=Depends(member)):
    subject, text = str(body.get("subject", "")).strip(), str(body.get("body", "")).strip()
    if not subject or not text:
        raise HTTPException(400, "subject and message are required")
    with db.tx() as c:
        tid = db.insert(c, tickets, tenant_id=u["tenant_id"], subject=subject[:240], status="open", priority=body.get("priority") if body.get("priority") in ("low", "normal", "high") else "normal",
                        category=body.get("category", "general")[:30], requester=u["email"], created=now(), updated=now())
        services.ticket_message(c, tid, u["email"], "customer", text)
        services.record(c, u["email"], "ticket_open", subject[:80], u["tenant_id"])
    return {"id": tid}


def _own(c, tid, u):
    t = one(c, select(tickets).where(tickets.c.id == tid, tickets.c.tenant_id == u["tenant_id"]))
    if not t:
        raise HTTPException(404)
    return t


@customer.get("/{tid}")
def my_ticket(tid: int, u=Depends(member)):
    with db.tx() as c:
        t = _own(c, tid, u)
        msgs = many(c, select(ticket_messages).where(ticket_messages.c.ticket_id == tid, ticket_messages.c.internal == False).order_by(ticket_messages.c.id))  # noqa: E712
        for m in msgs:
            if m["author_type"] == "staff":
                m["author"] = "Solavis support"           # staff identities are not shown to customers
        return {"ticket": {k: t[k] for k in ("id", "subject", "status", "priority", "category", "created", "updated")}, "messages": msgs}


@customer.post("/{tid}/message")
def my_reply(tid: int, body: dict, u=Depends(member)):
    if not str(body.get("body", "")).strip():
        raise HTTPException(400, "message is empty")
    with db.tx() as c:
        _own(c, tid, u)
        services.ticket_message(c, tid, u["email"], "customer", body["body"].strip())
    return {"ok": True}


@customer.post("/{tid}/close")
def my_close(tid: int, u=Depends(member)):
    with db.tx() as c:
        _own(c, tid, u)
        c.execute(update(tickets).where(tickets.c.id == tid).values(status="solved", solved_at=now(), updated=now()))
    return {"ok": True}
