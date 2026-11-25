"""Device inventory: stock, assignment to customers, returns. Assets, not live control."""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update

from .. import db, services
from ..db import cameras, inventory, many, now, one, tenants
from .deps import need

router = APIRouter(prefix="/api/admin/inventory", tags=["inventory"])


@router.get("")
def list_items(status: str = "", u=Depends(need("inventory.read"))):
    q = (select(inventory, tenants.c.name.label("tenant"), cameras.c.state.label("camera_state"), cameras.c.last_seen)
         .join(tenants, tenants.c.id == inventory.c.tenant_id, isouter=True).join(cameras, cameras.c.id == inventory.c.camera_id, isouter=True)
         .order_by(inventory.c.id.desc()).limit(500))
    if status:
        q = q.where(inventory.c.status == status)
    with db.tx() as c:
        rows = many(c, q)
    if not services.can(u, "inventory.write") and not services.can(u, "*"):
        for r in rows:
            r["cost_vnd"] = None                      # unit cost is internal (finance/admin)
    return rows


@router.post("")
def add_units(body: dict, u=Depends(need("inventory.write"))):
    n = int(body.get("count", 1))
    if not 1 <= n <= 200:
        raise HTTPException(400, "count must be 1-200")
    prefix = (body.get("prefix") or "SOL-" + time.strftime("%y%m")).strip()
    with db.tx() as c:
        last = c.execute(select(inventory.c.serial).where(inventory.c.serial.like(f"{prefix}-%")).order_by(inventory.c.id.desc())).scalar()
        start = int(last.rsplit("-", 1)[1]) + 1 if last else 1
        for i in range(n):
            db.insert(c, inventory, serial=f"{prefix}-{start + i:04d}", model=body.get("model", "Solavis Cam 4G"), status="in_stock", cost_vnd=body.get("cost_vnd"),
                      warranty_until=now() + 365 * 86400, created=now())
        services.record(c, u["email"], "inventory_add", f"{n} x {body.get('model', 'Solavis Cam 4G')}")
    return {"added": n}


@router.post("/{iid}/assign")
def assign(iid: int, body: dict, u=Depends(need("inventory.write"))):
    with db.tx() as c:
        it = one(c, select(inventory).where(inventory.c.id == iid))
        if not it or it["status"] != "in_stock":
            raise HTTPException(400, "unit is not in stock")
        try:
            cid, code = services.create_camera(c, int(body["tenant_id"]), body.get("name") or "Front gate", actor=u["email"], serial=it["serial"])
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e))
    return {"claim_code": code, "camera_id": cid}


@router.post("/{iid}/{action}")
def change(iid: int, action: str, body: dict, u=Depends(need("devices.revoke"))):
    """rma (returned/faulty or lost) and retire both kill the camera's key. A reason is required and audited."""
    if action not in ("rma", "retire", "restock"):
        raise HTTPException(400, "unknown action")
    reason = str(body.get("reason", "")).strip()
    if action != "restock" and len(reason) < 5:
        raise HTTPException(400, "a reason is required (e.g. customer reported theft, ticket #12)")
    with db.tx() as c:
        it = one(c, select(inventory).where(inventory.c.id == iid))
        if not it:
            raise HTTPException(404)
        if it["camera_id"] and action != "restock":
            c.execute(update(cameras).where(cameras.c.id == it["camera_id"]).values(state="revoked", key_hash=None))
        new = {"rma": "rma", "retire": "retired", "restock": "in_stock"}[action]
        c.execute(update(inventory).where(inventory.c.id == iid).values(status=new, **({"notes": reason} if reason else {}),
                                                                         **({"tenant_id": None, "camera_id": None} if action == "restock" else {})))
        services.record(c, u["email"], f"device_{action}", f"{it['serial']}: {reason}", it["tenant_id"])
    return {"ok": True}
