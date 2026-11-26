"""The ERP's organisation: departments, roles, staff, access reviews and the security log.
The President sets each department's ceiling and appoints heads (with a fresh face check). A head hands out rights to their own
staff, never above the ceiling. Everything is audited; sensitive moves also go into the tamper-evident security log."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select, update

from .. import db, security, services, storage
from ..db import dept_roles, departments, face_vectors, many, now, one, security_log, sessions, users
from ..permissions import CATALOG, MODULES
from .deps import client_ip, fresh, need, staff, super_fresh

router = APIRouter(prefix="/api/admin/org", tags=["organisation"])


def bad(msg, code=400):
    raise HTTPException(code, msg)


def _dept(c, did):
    d = one(c, select(departments).where(departments.c.id == did))
    if not d:
        raise HTTPException(404, "department not found")
    d["ceiling"] = services._j(d["ceiling"])
    return d


def _can_manage(c, u, did):
    if not services.may_manage_dept(c, u, did):
        raise HTTPException(403, "only the President or this department's head can do this")


def _member_row(c, m, d):
    role = one(c, select(dept_roles.c.name).where(dept_roles.c.id == m["role_id"])) if m["role_id"] else None
    mm = dict(m, perms=services.effective_perms(c, m))
    return {"id": m["id"], "email": m["email"], "name": m["name"], "job_title": m["job_title"], "active": bool(m["active"]), "role_id": m["role_id"], "role": role["name"] if role else None,
            "is_head": d["head_user_id"] == m["id"], "is_super": bool(m["is_super"]), "last_login": m["last_login"], "must_change_pw": bool(m["must_change_pw"]),
            "extra_perms": services._j(m["extra_perms"]), "denied_perms": services._j(m["denied_perms"]), "perms": mm["perms"],
            "face_enrolled": bool(c.execute(select(face_vectors.c.id).where(face_vectors.c.user_id == m["id"])).first()) if m["face_required"] else None}


@router.get("/permissions")
def permissions(u=Depends(staff)):
    return {"modules": MODULES, "items": [{"perm": k, "module": v[0], "label": v[1]} for k, v in CATALOG.items()]}


@router.get("/directory")
def directory(purpose: str = "tasks", u=Depends(staff)):
    """Who can be picked in a drop-down. tasks: yourself, your department if you are its head, everyone for the President.
    tickets: active staff who can actually work tickets (hold support.write)."""
    with db.tx() as c:
        rows = many(c, select(users).where(users.c.role == "staff", users.c.active == True).order_by(users.c.email))  # noqa: E712
        if purpose == "tickets":
            rows = [r for r in rows if services.can({"perms": services.effective_perms(c, r)}, "support.write")]
        elif not u.get("is_super"):
            rows = [r for r in rows if r["id"] == u["id"] or (u.get("is_head") and r["department_id"] == u.get("department_id"))]
        return [{"id": r["id"], "email": r["email"], "name": r["name"]} for r in rows]


@router.get("/departments")
def list_departments(u=Depends(staff)):
    with db.tx() as c:
        out = []
        for d in many(c, select(departments).order_by(departments.c.id)):
            head = one(c, select(users.c.id, users.c.email, users.c.name).where(users.c.id == d["head_user_id"])) if d["head_user_id"] else None
            out.append({"id": d["id"], "code": d["code"], "name": d["name"], "description": d["description"], "active": bool(d["active"]), "ceiling": services._j(d["ceiling"]), "head": head,
                        "members": c.execute(select(func.count()).select_from(users).where(users.c.department_id == d["id"], users.c.active == True)).scalar(),  # noqa: E712
                        "roles": c.execute(select(func.count()).select_from(dept_roles).where(dept_roles.c.department_id == d["id"])).scalar(),
                        "mine": u.get("department_id") == d["id"], "can_manage": services.may_manage_dept(c, u, d["id"])})
        return out


@router.post("/departments")
def create_department(body: dict, request: Request, u=Depends(super_fresh)):
    code = str(body.get("code", "")).strip().lower().replace(" ", "-")
    name = str(body.get("name", "")).strip()
    if not code or not name:
        bad("code and name are required")
    ceiling = list(body.get("ceiling") or [])
    from ..permissions import unknown
    if unknown(ceiling):
        bad(f"unknown permission(s): {unknown(ceiling)}")
    with db.tx() as c:
        if one(c, select(departments.c.id).where(departments.c.code == code)):
            bad("a department with this code already exists")
        did = db.insert(c, departments, code=code, name=name, description=body.get("description", ""), ceiling=json.dumps(ceiling), active=True, created=now())
        services.record(c, u["email"], "department_create", f"{code} {ceiling}")
        services.sec_log(c, "department_create", True, user=u, ip=client_ip(request), detail={"code": code, "ceiling": ceiling})
    return {"id": did}


@router.post("/departments/{did}")
def update_department(did: int, body: dict, request: Request, u=Depends(super_fresh)):
    from ..permissions import unknown
    with db.tx() as c:
        d = _dept(c, did)
        vals, log = {}, {}
        for k in ("name", "description"):
            if k in body:
                vals[k] = str(body[k])
        if "active" in body:
            vals["active"] = bool(body["active"])
        if "ceiling" in body:
            ceiling = list(body["ceiling"])
            if unknown(ceiling):
                bad(f"unknown permission(s): {unknown(ceiling)}")
            vals["ceiling"] = json.dumps(ceiling)
            log["ceiling"] = {"from": d["ceiling"], "to": ceiling}
        if "head_user_id" in body:
            hid = body["head_user_id"]
            if hid is not None and not one(c, select(users.c.id).where(users.c.id == hid, users.c.department_id == did, users.c.role == "staff", users.c.active == True)):  # noqa: E712
                bad("the head must be an active member of this department")
            vals["head_user_id"] = hid
            log["head"] = {"from": d["head_user_id"], "to": hid}
        if not vals:
            bad("nothing to change")
        c.execute(update(departments).where(departments.c.id == did).values(**vals))
        if "ceiling" in body:
            services.clamp_to_ceiling(c, did)
        services.record(c, u["email"], "department_update", f"{d['code']} {list(vals)}")
        services.sec_log(c, "department_update", True, user=u, ip=client_ip(request), detail={"department": d["code"], **log})
    return {"ok": True}


@router.get("/departments/{did}")
def department_detail(did: int, u=Depends(staff)):
    with db.tx() as c:
        d = _dept(c, did)
        if not (u.get("is_super") or services.can(u, "staff.read") or u.get("department_id") == did):
            raise HTTPException(403, "you can only open your own department")
        members = [_member_row(c, m, d) for m in many(c, select(users).where(users.c.department_id == did, users.c.role == "staff").order_by(users.c.id))]
        roles = many(c, select(dept_roles).where(dept_roles.c.department_id == did).order_by(dept_roles.c.id))
        for r in roles:
            r["permissions"] = services._j(r["permissions"])
            r["members"] = sum(1 for m in members if m["role_id"] == r["id"])
        return {"department": d, "members": members, "roles": roles, "can_manage": services.may_manage_dept(c, u, did), "is_super": bool(u.get("is_super"))}


# ───── roles (head or President) ─────
@router.post("/departments/{did}/roles")
def create_role(did: int, body: dict, u=Depends(staff)):
    name, perms = str(body.get("name", "")).strip(), list(body.get("permissions") or [])
    if not name:
        bad("role name required")
    with db.tx() as c:
        _can_manage(c, u, did)
        try:
            services.check_within(c, did, perms)
        except ValueError as e:
            bad(str(e))
        if one(c, select(dept_roles.c.id).where(dept_roles.c.department_id == did, dept_roles.c.name == name)):
            bad("this department already has a role with that name")
        rid = db.insert(c, dept_roles, department_id=did, name=name, permissions=json.dumps(perms), created_by=u["email"], created=now())
        services.record(c, u["email"], "role_create", f"{name} {perms}")
    return {"id": rid}


@router.post("/roles/{rid}")
def update_role(rid: int, body: dict, request: Request, u=Depends(staff)):
    with db.tx() as c:
        r = one(c, select(dept_roles).where(dept_roles.c.id == rid))
        if not r:
            raise HTTPException(404)
        _can_manage(c, u, r["department_id"])
        vals = {}
        if "name" in body and str(body["name"]).strip():
            vals["name"] = str(body["name"]).strip()
        if "permissions" in body:
            try:
                services.check_within(c, r["department_id"], list(body["permissions"]))
            except ValueError as e:
                bad(str(e))
            vals["permissions"] = json.dumps(list(body["permissions"]))
        if not vals:
            bad("nothing to change")
        c.execute(update(dept_roles).where(dept_roles.c.id == rid).values(**vals))
        services.record(c, u["email"], "role_update", f"{r['name']} {vals}")
        if "permissions" in vals:
            services.sec_log(c, "role_permissions_changed", True, user=u, ip=client_ip(request), detail={"role": r["name"], "from": services._j(r["permissions"]), "to": json.loads(vals["permissions"])})
    return {"ok": True}


@router.delete("/roles/{rid}")
def delete_role(rid: int, u=Depends(staff)):
    with db.tx() as c:
        r = one(c, select(dept_roles).where(dept_roles.c.id == rid))
        if not r:
            raise HTTPException(404)
        _can_manage(c, u, r["department_id"])
        if c.execute(select(func.count()).select_from(users).where(users.c.role_id == rid)).scalar():
            bad("people still hold this role: move them to another role first")
        c.execute(delete(dept_roles).where(dept_roles.c.id == rid))
        services.record(c, u["email"], "role_delete", r["name"])
    return {"ok": True}


# ───── members (head or President) ─────
@router.post("/departments/{did}/members")
def add_member(did: int, body: dict, u=Depends(staff)):
    with db.tx() as c:
        _can_manage(c, u, did)
        make_head = bool(body.get("head")) and bool(u.get("is_super"))
        try:
            uid, pw = services.create_staff(c, body.get("email", ""), did, name=body.get("name", ""), job_title=body.get("job_title", ""), role_id=body.get("role_id") or None,
                                            actor=u["email"], head=make_head)
        except ValueError as e:
            bad(str(e))
    return {"id": uid, "email": body["email"].strip().lower(), "temporary_password": pw}


@router.post("/members/{uid}")
def update_member(uid: int, body: dict, request: Request, u=Depends(staff)):
    with db.tx() as c:
        m = one(c, select(users).where(users.c.id == uid, users.c.role == "staff"))
        if not m or not m["department_id"]:
            raise HTTPException(404)
        did = m["department_id"]
        _can_manage(c, u, did)
        if m["is_super"] and not u.get("is_super"):
            raise HTTPException(403, "only the President can change the President")
        d = _dept(c, did)
        if d["head_user_id"] == uid and not u.get("is_super"):
            raise HTTPException(403, "only the President can change a department head")
        if uid == u["id"] and not u.get("is_super"):
            raise HTTPException(403, "you cannot change your own rights")
        vals, log = {}, {}
        if "role_id" in body:
            rid = body["role_id"] or None
            if rid and not one(c, select(dept_roles.c.id).where(dept_roles.c.id == rid, dept_roles.c.department_id == did)):
                bad("that role does not belong to this department")
            vals["role_id"] = rid
            log["role_id"] = {"from": m["role_id"], "to": rid}
        for k, col in (("extra_perms", "extra_perms"), ("denied_perms", "denied_perms")):
            if k in body:
                perms = list(body[k] or [])
                try:
                    services.check_within(c, did, perms)
                except ValueError as e:
                    bad(str(e))
                vals[col] = json.dumps(perms)
                log[k] = {"from": services._j(m[col]), "to": perms}
        for k in ("name", "job_title"):
            if k in body:
                vals[k] = str(body[k])
        if "active" in body:
            if uid == u["id"] and not body["active"]:
                bad("you cannot disable yourself")
            vals["active"] = bool(body["active"])
            if not body["active"]:
                c.execute(delete(sessions).where(sessions.c.user_id == uid))      # sign them out everywhere
        if "department_id" in body and body["department_id"] != did:
            if not u.get("is_super"):
                raise HTTPException(403, "only the President can move people between departments")
            _dept(c, body["department_id"])
            vals.update(department_id=body["department_id"], role_id=None, extra_perms="[]", denied_perms="[]")
            if d["head_user_id"] == uid:
                c.execute(update(departments).where(departments.c.id == did).values(head_user_id=None))
            log["moved_to"] = body["department_id"]
        if not vals:
            bad("nothing to change")
        c.execute(update(users).where(users.c.id == uid).values(**vals))
        services.record(c, u["email"], "staff_update", f"{m['email']} {list(vals)}")
        if log:
            services.sec_log(c, "staff_rights_changed", True, user=u, ip=client_ip(request), detail={"member": m["email"], "department": d["code"], **log})
    return {"ok": True}


@router.post("/members/{uid}/reset-password")
def reset_member_password(uid: int, request: Request, u=Depends(staff)):
    with db.tx() as c:
        m = one(c, select(users).where(users.c.id == uid, users.c.role == "staff"))
        if not m or not m["department_id"]:
            raise HTTPException(404)
        _can_manage(c, u, m["department_id"])
        if m["is_super"]:
            if not u.get("is_super"):
                raise HTTPException(403, "only the President can reset the President's password")
            fresh(u)
        pw = security.temp_password()
        c.execute(update(users).where(users.c.id == uid).values(pw_hash=security.hash_password(pw), must_change_pw=True))
        c.execute(delete(sessions).where(sessions.c.user_id == uid))
        services.sec_log(c, "staff_password_reset", True, user=u, ip=client_ip(request), detail={"member": m["email"]})
    return {"temporary_password": pw}


@router.post("/members/{uid}/enroll-code")
def new_enroll_code(uid: int, request: Request, u=Depends(super_fresh)):
    """The President issues a one-time face-enrollment code (shown once) for a face-required account."""
    with db.tx() as c:
        m = one(c, select(users).where(users.c.id == uid, users.c.role == "staff"))
        if not m or not m["face_required"]:
            bad("this account does not use face authentication")
        code = services.issue_enroll_code(c, uid)
        services.sec_log(c, "enroll_code_issued", True, user=u, ip=client_ip(request), detail={"for": m["email"]})
    return {"code": code}


# ───── reviews, security log ─────
@router.get("/access-review")
def access_review(u=Depends(need("staff.read"))):
    """Who can do what, right now: the evidence an auditor asks for."""
    with db.tx() as c:
        out = []
        for d in many(c, select(departments).order_by(departments.c.id)):
            for m in many(c, select(users).where(users.c.department_id == d["id"], users.c.role == "staff").order_by(users.c.id)):
                row = _member_row(c, m, d)
                row.update(department=d["name"], dept_id=d["id"], stale=bool(row["active"] and (not m["last_login"] or now() - m["last_login"] > 30 * 86400)))
                out.append(row)
        return out


@router.get("/security-log")
def get_security_log(limit: int = 200, event: str = "", u=Depends(need("security.read"))):
    q = select(security_log).order_by(security_log.c.id.desc()).limit(min(limit, 1000))
    if event:
        q = q.where(security_log.c.event.like(event + "%"))
    with db.tx() as c:
        rows = many(c, q)
    for r in rows:
        try:
            r["detail"] = json.loads(r["detail"]) if r["detail"] else {}
        except Exception:
            pass
    return rows


@router.get("/security-log/verify")
def verify_security_log(u=Depends(need("security.read"))):
    with db.tx() as c:
        return services.verify_chain(c)


@router.get("/security-log/snap/{name}")
def security_snap(name: str, u=Depends(need("security.read"))):
    with db.tx() as c:
        if not c.execute(select(security_log.c.id).where(security_log.c.snap == name)).first():
            raise HTTPException(404)
    data = storage.store().get(name)
    if data is None:
        raise HTTPException(404)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
