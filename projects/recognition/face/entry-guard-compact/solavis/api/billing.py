"""Plans and invoices (staff) and the customer's billing page."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from .. import db, services, settings
from ..db import invoices, many, now, one, payments, plans, tenants
from .deps import need, owner

admin = APIRouter(prefix="/api/admin", tags=["billing"])
customer = APIRouter(prefix="/api", tags=["billing"])


@admin.get("/plans")
def list_plans(u=Depends(need("accounts.read"))):
    with db.tx() as c:
        return many(c, select(plans).order_by(plans.c.price_vnd))


@admin.post("/plans")
def save_plan(body: dict, u=Depends(need("plans.write"))):
    try:
        vals = dict(name=str(body["name"]), max_cameras=int(body["max_cameras"]), max_people=int(body["max_people"]),
                    events_per_day=int(body["events_per_day"]), watchlist=bool(body.get("watchlist")), price_vnd=int(body.get("price_vnd") or 0))
        pid = str(body["id"]).strip().lower()
    except (KeyError, ValueError):
        raise HTTPException(400, "id, name, max_cameras, max_people, events_per_day (numbers) are required")
    with db.tx() as c:
        if one(c, select(plans.c.id).where(plans.c.id == pid)):
            c.execute(update(plans).where(plans.c.id == pid).values(**vals))
        else:
            c.execute(plans.insert().values(id=pid, **vals))
        services.record(c, u["email"], "plan_save", f"{pid} {vals['price_vnd']}")
    return {"ok": True}


@admin.get("/invoices")
def list_invoices(status: str = "", tenant_id: int | None = None, u=Depends(need("billing.read"))):
    q = select(invoices, tenants.c.name.label("tenant")).join(tenants, tenants.c.id == invoices.c.tenant_id).order_by(invoices.c.id.desc()).limit(300)
    if tenant_id:
        q = q.where(invoices.c.tenant_id == tenant_id)
    with db.tx() as c:
        rows = [dict(i, state=services.invoice_state(i)) for i in many(c, q)]
    return [r for r in rows if not status or r["state"] == status]


@admin.post("/invoices")
def new_invoice(body: dict, u=Depends(need("billing.write"))):
    with db.tx() as c:
        try:
            iid, number = services.create_invoice(c, int(body["tenant_id"]), body.get("months", 1), body.get("description"), u["email"])
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e))
    return {"id": iid, "number": number}


@admin.post("/invoices/{iid}/paid")
def pay(iid: int, body: dict, u=Depends(need("billing.write"))):
    with db.tx() as c:
        try:
            services.mark_paid(c, iid, body.get("method"), body.get("ref"), u["email"])
        except ValueError as e:
            raise HTTPException(400, str(e))
    return {"ok": True}


@admin.post("/invoices/{iid}/void")
def void(iid: int, u=Depends(need("billing.write"))):
    with db.tx() as c:
        inv = one(c, select(invoices).where(invoices.c.id == iid))
        if not inv or inv["status"] == "paid":
            raise HTTPException(400, "cannot void this invoice")
        c.execute(update(invoices).where(invoices.c.id == iid).values(status="void"))
        services.record(c, u["email"], "invoice_void", inv["number"], inv["tenant_id"])
    return {"ok": True}


@customer.get("/billing")
def my_billing(u=Depends(owner)):
    cfg = settings.get().billing
    with db.tx() as c:
        t = services.entitlement(c, u["tenant_id"])
        plan = one(c, select(plans).where(plans.c.id == t["plan_id"]))
        invs = [dict(i, state=services.invoice_state(i)) for i in
                many(c, select(invoices).where(invoices.c.tenant_id == u["tenant_id"], invoices.c.status != "draft").order_by(invoices.c.id.desc()))]
    for i in invs:
        i["qr_url"] = (f"https://img.vietqr.io/image/{cfg.bank.bank_code}-{cfg.bank.account_no}-compact2.png?amount={i['total']}&addInfo={i['number']}"
                       if cfg.qr_enabled and cfg.bank.bank_code and i["state"] in ("sent", "overdue") else None)
    return {"plan": {"name": plan["name"], "price_vnd": plan["price_vnd"], "max_cameras": plan["max_cameras"], "max_people": plan["max_people"],
                     "events_per_day": plan["events_per_day"], "watchlist": bool(plan["watchlist"])},
            "status": t["effective_status"], "trial_end": t["trial_end"], "currency": cfg.currency, "invoices": invs,
            "pay_to": {"bank": cfg.bank.name, "account_no": cfg.bank.account_no, "account_name": cfg.bank.account_name, "note": "Put the invoice number in the transfer note."},
            "seller": {"name": cfg.company.name, "address": cfg.company.address, "tax_code": cfg.company.tax_code}}
