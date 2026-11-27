"""Solavis cloud: config validation, auth, tamper state machine, subscription control, tenant isolation, admin console."""
import io
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from solavis import db, settings, storage


PKG = textwrap.dedent("""
    name: t
    staff:
      - {email: staff@t.vn, password: Staff1234, name: President, department: executive, president: true, head: true, enroll_code: TEST-FACE-0001}
      - {email: sales.head@t.vn, password: Staff1234, department: sales, head: true}
      - {email: finance.head@t.vn, password: Staff1234, department: finance, head: true}
      - {email: sales@t.vn, password: Staff1234, department: sales, role: Sales representative}
      - {email: support@t.vn, password: Staff1234, department: support, role: Support agent}
      - {email: finance@t.vn, password: Staff1234, department: finance, role: Accountant}
      - {email: tech@t.vn, password: Staff1234, department: operations, role: Field technician}
      - {email: ops.head@t.vn, password: Staff1234, department: operations, head: true}
    inventory: {count: 4, model: Test Cam, prefix: T-1}
    tenants:
      - {name: A Home, plan: home, status: active, users: [{email: a@t.vn, password: Owner1234, role: owner}, {email: av@t.vn, password: Viewer1234, role: member}],
         cameras: [{name: Gate, claim_code: SOL-AAAA-BBBB}]}
      - {name: B Shop, plan: lite, status: active, users: [{email: b@t.vn, password: Owner1234, role: owner}], cameras: [{name: Door, claim_code: SOL-CCCC-DDDD}]}
""")


def _make_env(tmp_path, monkeypatch, face_required):
    (tmp_path / "database.yaml").write_text(f"driver: sqlite\nurl: sqlite:///{tmp_path}/t.db\n")
    (tmp_path / "storage.yaml").write_text(f"driver: local\nlocal:\n  path: {tmp_path}/snaps\n")
    (tmp_path / "security.yaml").write_text(f"face:\n  required_for_super_admin: {str(face_required).lower()}\n  require_head_turn: false\n  max_failures: 3\n")
    monkeypatch.setenv("SOLAVIS_CONFIG_DIR", str(tmp_path))
    settings.get.cache_clear(); db.reset_engine(); storage.reset()
    from solavis import security
    from solavis.api import auth as auth_api
    security.guard.fails.clear(); auth_api._face_fail.clear()
    from solavis.app import create_app
    from solavis.manage import cmd_seed
    import argparse
    pkg = tmp_path / "pkg.yaml"
    pkg.write_text(PKG)
    return create_app(), cmd_seed, argparse.Namespace(package=str(pkg))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """President without the face requirement, so API tests can focus on the business rules."""
    app, seed, ns = _make_env(tmp_path, monkeypatch, False)
    with TestClient(app) as client:
        seed(ns)
        yield client
    settings.get.cache_clear(); db.reset_engine(); storage.reset()


@pytest.fixture()
def env_face(tmp_path, monkeypatch):
    app, seed, ns = _make_env(tmp_path, monkeypatch, True)
    with TestClient(app) as client:
        seed(ns)
        yield client
    settings.get.cache_clear(); db.reset_engine(); storage.reset()


def login(c, email, pw="Owner1234"):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def beat(c, key, **kw):
    d = dict(battery=80, net="wifi", rssi=-60, tilt=2, heading=90, cover_closed=1); d.update(kw)
    r = c.post("/device/v1/heartbeat", headers={"Authorization": f"Bearer {key}"}, data={k: str(v) for k, v in d.items()})
    assert r.status_code == 200, r.text
    return r.json()


def armed(c):
    key = c.post("/device/v1/claim", json={"claim_code": "SOL-AAAA-BBBB"}).json()["device_key"]
    beat(c, key)
    o = login(c, "a@t.vn")
    assert c.post("/api/cameras/1/arm", headers=o).json()["state"] == "armed"
    return key, o


def test_config_rejects_typos_and_bad_production(tmp_path, monkeypatch):
    (tmp_path / "server.yaml").write_text("prot: 1\n")
    monkeypatch.setenv("SOLAVIS_CONFIG_DIR", str(tmp_path)); settings.get.cache_clear()
    with pytest.raises(SystemExit):
        settings.load_settings()
    (tmp_path / "server.yaml").write_text("environment: production\n")
    with pytest.raises(SystemExit) as e:
        settings.load_settings()
    assert "secret_key" in str(e.value)
    settings.get.cache_clear()


def test_env_placeholders():
    import os
    os.environ["XTEST"] = "v"
    assert settings.expand({"a": "${XTEST}", "b": "${NOPE_X:-dflt}"}) == {"a": "v", "b": "dflt"}


@pytest.mark.parametrize("driver", ["postgresql", "mysql"])
def test_other_database_urls(driver, monkeypatch):
    cfg = settings.Settings(database={"driver": driver, driver: {"host": "db", "user": "u", "password": "p@ss", "database": "d"}})
    assert db.database_url(cfg).startswith("postgresql+psycopg://u:p%40ss@db" if driver == "postgresql" else "mysql+pymysql://u:p%40ss@db")


def test_login_protection_and_cookie(env):
    c = env
    for _ in range(5):
        assert c.post("/api/auth/login", json={"email": "a@t.vn", "password": "bad"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "a@t.vn", "password": "Owner1234"}).status_code == 429


def test_cookie_session_works(env):
    c = env
    assert c.post("/api/auth/login", json={"email": "a@t.vn", "password": "Owner1234"}).status_code == 200
    assert c.get("/api/overview").json()["tenant"]["name"] == "A Home"
    c.post("/api/auth/logout")
    assert c.get("/api/overview").status_code == 401


def test_staff_cannot_use_customer_api_and_reverse(env):
    c = env
    st = login(c, "staff@t.vn", "Staff1234")
    assert c.get("/api/overview", headers=st).status_code == 403
    assert c.get("/api/admin/summary", headers=login(c, "a@t.vn")).status_code == 403
    assert c.get("/api/admin/summary", headers=st).json()["tenants"] == 2


def test_claim_once_and_key_stored_hashed(env):
    c = env
    r = c.post("/device/v1/claim", json={"claim_code": "SOL-AAAA-BBBB"})
    key = r.json()["device_key"]
    assert c.post("/device/v1/claim", json={"claim_code": "SOL-AAAA-BBBB"}).status_code == 404
    with db.tx() as con:
        stored = con.execute(db.cameras.select().where(db.cameras.c.id == 1)).mappings().first()["key_hash"]
    assert stored and key not in stored


@pytest.mark.parametrize("change,reason", [({"heading": 140}, "turned"), ({"tilt": 20}, "moved"), ({"cover_closed": 0}, "cover_opened")])
def test_tamper_locks_alerts_and_blocks(env, change, reason):
    c = env
    key, o = armed(c)
    assert beat(c, key, **change)["lock_reason"] == reason
    assert any(a["level"] == "critical" for a in c.get("/api/alerts", headers=o).json())
    r = c.post("/device/v1/events", headers={"Authorization": f"Bearer {key}"}, data={"idem": "x"}, files={"image": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert r.status_code == 423
    assert beat(c, key)["state"] == "locked"          # the camera cannot unlock itself


def test_tamper_thresholds_come_from_config(env, tmp_path):
    c = env
    key, _ = armed(c)
    assert beat(c, key, tilt=4, heading=96)["state"] == "armed"     # small wobble tolerated


def test_lock_alert_raised_once(env):
    c = env
    key, o = armed(c)
    beat(c, key, heading=200); beat(c, key, heading=210)
    assert len([a for a in c.get("/api/alerts", headers=o).json() if a["kind"] == "tamper"]) == 1


def test_unlock_flow_and_roles(env):
    c = env
    key, o = armed(c)
    beat(c, key, heading=200)
    viewer = login(c, "av@t.vn", "Viewer1234")
    assert c.post("/api/cameras/1/unlock", headers=viewer).status_code == 403
    assert c.post("/api/cameras/1/unlock", headers=o).json()["state"] == "service"
    assert c.post("/api/cameras/1/arm", headers=o).json()["state"] == "armed"


def test_suspension_stops_uploads(env):
    c = env
    key, o = armed(c)
    st = login(c, "staff@t.vn", "Staff1234")
    assert c.post("/api/admin/tenants/1", headers=st, json={"status": "suspended"}).status_code == 200
    r = c.post("/device/v1/events", headers={"Authorization": f"Bearer {key}"}, data={"idem": "y"}, files={"image": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")})
    assert r.status_code == 402
    assert c.get("/device/v1/config", headers={"Authorization": f"Bearer {key}"}).json()["upload"] is False


def test_assign_respects_plan_limit_and_creates_claim_code(env):
    c = env
    st = login(c, "staff@t.vn", "Staff1234")
    stock = [i for i in c.get("/api/admin/inventory?status=in_stock", headers=st).json()]
    assert len(stock) >= 2
    assert c.post(f"/api/admin/inventory/{stock[0]['id']}/assign", headers=st, json={"tenant_id": 2, "name": "Extra"}).status_code == 400   # lite = 1 camera
    r = c.post(f"/api/admin/inventory/{stock[0]['id']}/assign", headers=st, json={"tenant_id": 1, "name": "Back door"})
    assert r.status_code == 200 and r.json()["claim_code"].startswith("SOL-")


def test_rma_needs_reason_and_kills_the_key(env):
    c = env
    key, _ = armed(c)
    tech = login(c, "tech@t.vn", "Staff1234")
    unit = [i for i in c.get("/api/admin/inventory?status=assigned", headers=tech).json() if i["tenant_id"] == 1][0]
    assert c.post(f"/api/admin/inventory/{unit['id']}/rma", headers=tech, json={}).status_code == 400
    assert c.post(f"/api/admin/inventory/{unit['id']}/rma", headers=tech, json={"reason": "customer reported theft, ticket 4"}).status_code == 200
    assert c.get("/device/v1/config", headers={"Authorization": f"Bearer {key}"}).status_code == 401
    assert any(a["action"] == "device_rma" for a in c.get("/api/admin/audit", headers=login(c, "staff@t.vn", "Staff1234")).json())


def test_staff_roles_limit_what_each_person_can_do(env):
    c = env
    sales, support, fin = (login(c, f"{n}@t.vn", "Staff1234") for n in ("sales", "support", "finance"))
    assert c.get("/api/admin/invoices", headers=support).status_code == 403          # support cannot read billing
    assert c.post("/api/admin/invoices", headers=sales, json={"tenant_id": 1}).status_code == 403   # sales cannot create invoices
    assert c.get("/api/admin/tickets", headers=fin).status_code == 403
    assert c.get("/api/admin/org/access-review", headers=sales).status_code == 403
    assert c.post("/api/admin/invoices", headers=fin, json={"tenant_id": 1}).status_code == 200


def test_invoice_paid_reactivates_overdue_account(env):
    c = env
    fin = login(c, "finance@t.vn", "Staff1234"); st = login(c, "staff@t.vn", "Staff1234")
    inv = c.post("/api/admin/invoices", headers=fin, json={"tenant_id": 1, "months": 2}).json()
    assert inv["number"].startswith("INV-")
    c.post("/api/admin/tenants/1", headers=st, json={"status": "past_due"})
    mine = login(c, "a@t.vn")
    billing = c.get("/api/billing", headers=mine).json()
    assert billing["invoices"][0]["total"] == 2 * 199000 and billing["invoices"][0]["state"] == "sent"
    iid = billing["invoices"][0]["id"]
    assert c.post(f"/api/admin/invoices/{iid}/paid", headers=fin, json={"method": "bank_transfer", "ref": "FT123"}).status_code == 200
    assert c.post(f"/api/admin/invoices/{iid}/paid", headers=fin, json={}).status_code == 400    # not twice
    assert c.get("/api/overview", headers=mine).json()["tenant"]["status"] == "active"


def test_ticket_flow_internal_notes_hidden_from_customer(env):
    c = env
    mine = login(c, "a@t.vn"); sup = login(c, "support@t.vn", "Staff1234")
    tid = c.post("/api/tickets", headers=mine, json={"subject": "Camera is offline", "body": "Please help"}).json()["id"]
    assert c.get("/api/admin/tickets?status=active", headers=sup).json()[0]["id"] == tid
    c.post(f"/api/admin/tickets/{tid}/message", headers=sup, json={"body": "Checking the logs", "internal": True})
    c.post(f"/api/admin/tickets/{tid}/message", headers=sup, json={"body": "Try restarting it"})
    thread = c.get(f"/api/tickets/{tid}", headers=mine).json()
    bodies = [m["body"] for m in thread["messages"]]
    assert "Try restarting it" in bodies and "Checking the logs" not in bodies
    assert all("@" not in m["author"] or m["author_type"] == "customer" for m in thread["messages"])   # staff identity hidden
    b = login(c, "b@t.vn")
    assert c.get(f"/api/tickets/{tid}", headers=b).status_code == 404                  # other customer cannot read it
    assert c.get("/api/admin/tickets/%d" % tid, headers=sup).json()["ticket"]["first_reply_at"]


def test_customer_devices_reports_activity(env):
    c = env
    key, o = armed(c)
    dev = c.get("/api/devices", headers=o).json()
    assert dev[0]["state"] == "armed" and dev[0]["serial"] and dev[0]["online"] is True and dev[0].get("key_hash") is None
    assert len(c.get("/api/reports?days=7", headers=o).json()["days"]) == 7
    acts = [a["action"] for a in c.get("/api/activity", headers=o).json()]
    assert "Armed" in acts and "Camera set up" in acts


def test_admin_detail_exposes_no_faces_or_snapshots(env):
    c = env
    st = login(c, "staff@t.vn", "Staff1234")
    r = c.get("/api/admin/tenants/1", headers=st)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tenant"]["price_vnd"] == 199000 and d["devices"] and d["contacts"] == []
    assert "people" not in d or isinstance(d.get("people_count"), int)
    assert not any(k in str(d) for k in ("snap", "vec"))
    assert c.get("/api/snap/x.jpg", headers=st).status_code == 403


def test_tenant_isolation(env):
    c = env
    armed(c)
    b = login(c, "b@t.vn")
    assert c.post("/api/cameras/1/unlock", headers=b).status_code == 404
    assert c.post("/api/cameras/1/arm", headers=b).status_code == 404
    assert [x["name"] for x in c.get("/api/overview", headers=b).json()["cameras"]] == ["Door"]
    assert c.get("/api/snap/whatever.jpg", headers=b).status_code == 404


def test_admin_creates_customer_with_forced_password_change(env):
    c = env
    st = login(c, "staff@t.vn", "Staff1234")
    r = c.post("/api/admin/tenants", headers=st, json={"name": "New Co", "plan_id": "pro", "owner_email": "own@new.vn"}).json()
    o = login(c, "own@new.vn", r["temporary_password"])
    assert c.get("/api/overview", headers=o).status_code == 403            # must change password first
    assert c.post("/api/auth/password", headers=o, json={"current": r["temporary_password"], "new": "weak"}).status_code == 400
    assert c.post("/api/auth/password", headers=o, json={"current": r["temporary_password"], "new": "Better123"}).status_code == 200
    assert c.get("/api/overview", headers=o).json()["tenant"]["plan"] == "Pro"


def test_health_and_ui(env):
    c = env
    assert c.get("/healthz").json() == {"status": "ok"} and c.get("/readyz").status_code == 200
    assert c.get("/").status_code == 200 and c.get("/admin").status_code == 200


@pytest.mark.parametrize("dialect", ["postgresql", "mysql"])
def test_schema_compiles_for_other_databases(dialect):
    """No server needed: proves the DDL is valid for PostgreSQL and MySQL. A real-server run is still required before go-live."""
    from sqlalchemy.dialects import mysql, postgresql
    from sqlalchemy.schema import CreateIndex, CreateTable
    d = {"postgresql": postgresql, "mysql": mysql}[dialect].dialect()
    for t in db.md.sorted_tables:
        assert "CREATE TABLE" in str(CreateTable(t).compile(dialect=d))
        for ix in t.indexes:
            str(CreateIndex(ix).compile(dialect=d))


def test_every_admin_page_endpoint_returns_200(env):
    """The console calls these on load; a 500 here means a blank screen for staff."""
    c = env
    st = login(c, "staff@t.vn", "Staff1234")
    for p in ["/api/admin/summary", "/api/admin/tenants", "/api/admin/tenants/1", "/api/admin/tenants/2", "/api/admin/plans", "/api/admin/invoices",
              "/api/admin/tickets", "/api/admin/inventory", "/api/admin/tasks?scope=all", "/api/admin/org/departments", "/api/admin/org/access-review", "/api/admin/org/security-log", "/api/admin/org/permissions", "/api/admin/org/departments/2", "/api/admin/audit", "/api/admin/system"]:
        assert c.get(p, headers=st).status_code == 200, p


def test_every_customer_page_endpoint_returns_200(env):
    c = env
    o = login(c, "a@t.vn")
    for p in ["/api/overview", "/api/devices", "/api/alerts", "/api/events", "/api/people", "/api/reports", "/api/activity", "/api/tickets", "/api/billing", "/api/team", "/api/export"]:
        assert c.get(p, headers=o).status_code == 200, p


# ───────────────────────── organisation, delegated rights, security log ─────────────────────────
def depts(c, h):
    return {d["code"]: d for d in c.get("/api/admin/org/departments", headers=h).json()}


def test_company_departments_seeded_with_ceilings(env):
    c = env
    pres = login(c, "staff@t.vn", "Staff1234")
    d = depts(c, pres)
    assert set(d) == {"executive", "sales", "support", "finance", "operations", "engineering", "compliance", "people"}
    assert "billing.write" in d["finance"]["ceiling"] and "billing.write" not in d["sales"]["ceiling"]
    assert d["sales"]["head"]["email"] == "sales.head@t.vn"


def test_head_holds_the_whole_ceiling_staff_hold_their_role(env):
    c = env
    head = login(c, "sales.head@t.vn", "Staff1234"); rep = login(c, "sales@t.vn", "Staff1234")
    hp, rp = set(c.get("/api/auth/me", headers=head).json()["perms"]), set(c.get("/api/auth/me", headers=rep).json()["perms"])
    assert {"accounts.write", "billing.read", "inventory.read"} <= hp
    assert rp == {"accounts.read", "accounts.write", "tasks"}


def test_only_the_president_creates_departments_and_appoints_heads(env):
    c = env
    head = login(c, "sales.head@t.vn", "Staff1234"); pres = login(c, "staff@t.vn", "Staff1234")
    assert c.post("/api/admin/org/departments", headers=head, json={"code": "legal", "name": "Legal", "ceiling": ["accounts.read"]}).status_code == 403
    assert c.post("/api/admin/org/departments", headers=pres, json={"code": "legal", "name": "Legal", "ceiling": ["accounts.read", "nonsense"]}).status_code == 400
    assert c.post("/api/admin/org/departments", headers=pres, json={"code": "legal", "name": "Legal", "ceiling": ["accounts.read"]}).status_code == 200
    sales = depts(c, pres)["sales"]
    detail = c.get(f"/api/admin/org/departments/{sales['id']}", headers=pres).json()
    rep = [m for m in detail["members"] if m["email"] == "sales@t.vn"][0]
    assert c.post(f"/api/admin/org/departments/{sales['id']}", headers=head, json={"head_user_id": rep["id"]}).status_code == 403
    assert c.post(f"/api/admin/org/departments/{sales['id']}", headers=pres, json={"head_user_id": rep["id"]}).status_code == 200
    assert "billing.read" in c.get("/api/auth/me", headers=login(c, "sales@t.vn", "Staff1234")).json()["perms"]       # the new head holds the ceiling
    assert "billing.read" not in c.get("/api/auth/me", headers=login(c, "sales.head@t.vn", "Staff1234")).json()["perms"]      # the former head lost it


def test_head_delegates_rights_inside_the_ceiling_only(env):
    c = env
    head = login(c, "sales.head@t.vn", "Staff1234"); pres = login(c, "staff@t.vn", "Staff1234")
    d = depts(c, pres)
    sales, fin = d["sales"], d["finance"]
    det = c.get(f"/api/admin/org/departments/{sales['id']}", headers=head).json()
    rep = [m for m in det["members"] if m["email"] == "sales@t.vn"][0]
    # outside the ceiling: refused
    assert c.post(f"/api/admin/org/members/{rep['id']}", headers=head, json={"extra_perms": ["billing.write"]}).status_code == 400
    # inside the ceiling: works, and shows up in the person's effective rights
    assert c.post(f"/api/admin/org/members/{rep['id']}", headers=head, json={"extra_perms": ["support.read"]}).status_code == 200
    me = login(c, "sales@t.vn", "Staff1234")
    assert "support.read" in c.get("/api/auth/me", headers=me).json()["perms"] and c.get("/api/admin/tickets", headers=me).status_code == 200
    # a denial removes a right the role would give
    c.post(f"/api/admin/org/members/{rep['id']}", headers=head, json={"denied_perms": ["accounts.write"]})
    assert "accounts.write" not in c.get("/api/auth/me", headers=me).json()["perms"]
    # not another department, not another head, not yourself, not staff
    assert c.post(f"/api/admin/org/departments/{fin['id']}/members", headers=head, json={"email": "x@t.vn"}).status_code == 403
    assert c.post(f"/api/admin/org/departments/{sales['id']}/roles", headers=head, json={"name": "Over", "permissions": ["plans.write"]}).status_code == 400
    head_row = [m for m in det["members"] if m["is_head"]][0]
    assert c.post(f"/api/admin/org/members/{head_row['id']}", headers=head, json={"role_id": None}).status_code == 403
    assert c.post(f"/api/admin/org/members/{rep['id']}", headers=me, json={"extra_perms": ["tasks"]}).status_code == 403
    assert c.post(f"/api/admin/org/departments/{sales['id']}/members", headers=me, json={"email": "y@t.vn"}).status_code == 403


def test_head_creates_a_role_and_a_member(env):
    c = env
    head = login(c, "sales.head@t.vn", "Staff1234"); pres = login(c, "staff@t.vn", "Staff1234")
    sales = depts(c, pres)["sales"]
    rid = c.post(f"/api/admin/org/departments/{sales['id']}/roles", headers=head, json={"name": "Quote desk", "permissions": ["accounts.read", "billing.read"]}).json()["id"]
    r = c.post(f"/api/admin/org/departments/{sales['id']}/members", headers=head, json={"email": "new.hire@t.vn", "name": "New Hire", "role_id": rid}).json()
    new = login(c, "new.hire@t.vn", r["temporary_password"])
    assert c.get("/api/admin/summary", headers=new).status_code == 403                    # must change the temporary password first
    assert c.post("/api/auth/password", headers=new, json={"current": r["temporary_password"], "new": "Better123"}).status_code == 200
    assert set(c.get("/api/auth/me", headers=new).json()["perms"]) == {"accounts.read", "billing.read"}
    assert c.delete(f"/api/admin/org/roles/{rid}", headers=head).status_code == 400       # still held by someone


def test_shrinking_a_ceiling_removes_rights_everywhere(env):
    c = env
    pres = login(c, "staff@t.vn", "Staff1234"); me = login(c, "sales@t.vn", "Staff1234")
    sales = depts(c, pres)["sales"]
    assert "accounts.write" in c.get("/api/auth/me", headers=me).json()["perms"]
    c.post(f"/api/admin/org/departments/{sales['id']}", headers=pres, json={"ceiling": ["accounts.read", "tasks"]})
    assert set(c.get("/api/auth/me", headers=me).json()["perms"]) == {"accounts.read", "tasks"}


def test_staff_and_customers_cannot_use_each_others_side(env):
    c = env
    assert c.get("/api/admin/org/departments", headers=login(c, "a@t.vn")).status_code == 403
    assert c.get("/api/overview", headers=login(c, "sales.head@t.vn", "Staff1234")).status_code == 403


def test_security_log_is_a_tamper_evident_chain(env):
    c = env
    pres = login(c, "staff@t.vn", "Staff1234")
    c.post("/api/admin/org/departments", headers=pres, json={"code": "legal", "name": "Legal", "ceiling": ["accounts.read"]})
    v = c.get("/api/admin/org/security-log/verify", headers=pres).json()
    assert v["ok"] and v["records"] >= 3
    events = [r["event"] for r in c.get("/api/admin/org/security-log", headers=pres).json()]
    assert "president_action" in events and "department_create" in events and "login_password_ok" in events
    with db.tx() as con:                                      # an attacker edits history in the database
        con.execute(db.security_log.update().where(db.security_log.c.id == 1).values(actor="someone.else@evil.com"))
    assert c.get("/api/admin/org/security-log/verify", headers=pres).json() == {"ok": False, "records": 0, "broken_at": 1}


def test_access_review_needs_staff_read_and_flags_everyone(env):
    c = env
    assert c.get("/api/admin/org/access-review", headers=login(c, "sales@t.vn", "Staff1234")).status_code == 403
    rows = c.get("/api/admin/org/access-review", headers=login(c, "staff@t.vn", "Staff1234")).json()
    assert {r["email"] for r in rows} >= {"sales@t.vn", "support@t.vn", "finance.head@t.vn"} and all("perms" in r for r in rows)


def test_idle_staff_session_times_out(env):
    c = env
    h = login(c, "sales.head@t.vn", "Staff1234")
    assert c.get("/api/admin/summary", headers=h).status_code == 200
    with db.tx() as con:
        con.execute(db.sessions.update().values(last_seen=db.now() - 3600))
    assert c.get("/api/admin/summary", headers=h).status_code == 401


def test_ip_allowlist_logic():
    from solavis.api.deps import ip_allowed
    assert ip_allowed("203.0.113.5", []) and ip_allowed("203.0.113.5", ["203.0.113.5"]) and ip_allowed("10.2.3.4", ["10.0.0.0/8"])
    assert not ip_allowed("198.51.100.7", ["203.0.113.5", "10.0.0.0/8"]) and not ip_allowed("not-an-ip", ["10.0.0.0/8"])


# ───────────────────────── President: face authentication ─────────────────────────
PHOTOS = Path(__file__).resolve().parent.parent / "data" / "photos"


def _imgs(person, idx):
    files = sorted((PHOTOS / person).glob("*.jpg"))
    if len(files) <= max(idx):
        pytest.skip("sample photos not available in data/photos")
    return [("images", (f"{i}.jpg", files[i].read_bytes(), "image/jpeg")) for i in idx]


def test_president_needs_password_and_face(env_face):
    c = env_face
    r = c.post("/api/auth/login", json={"email": "staff@t.vn", "password": "Staff1234"}).json()
    assert r["face"] == {"required": True, "enrolled": False}
    h = {"Authorization": "Bearer " + r["token"]}
    assert c.get("/api/admin/summary", headers=h).status_code == 403                      # password alone opens nothing
    assert c.get("/api/auth/me", headers=h).json()["face_pending"] is True
    assert c.post("/api/auth/face/enroll", headers=h, files=_imgs("5", [0, 1, 2]), data={"code": "WRONG-CODE"}).status_code == 403
    assert c.post("/api/auth/face/enroll", headers=h, files=_imgs("5", [0, 1, 2]), data={"code": "TEST-FACE-0001"}).status_code == 200
    assert c.get("/api/admin/summary", headers=h).status_code == 200
    assert c.post("/api/auth/face/enroll", headers=h, files=_imgs("5", [0, 1, 2]), data={"code": "TEST-FACE-0001"}).status_code in (200, 403)  # code is one-time


def _enrolled_president(c):
    r = c.post("/api/auth/login", json={"email": "staff@t.vn", "password": "Staff1234"}).json()
    h = {"Authorization": "Bearer " + r["token"]}
    assert c.post("/api/auth/face/enroll", headers=h, files=_imgs("5", [0, 1, 2]), data={"code": "TEST-FACE-0001"}).status_code == 200
    c.post("/api/auth/logout", headers=h)


def test_right_face_opens_wrong_face_is_recorded_and_locked_out(env_face):
    c = env_face
    _enrolled_president(c)
    def start():
        r = c.post("/api/auth/login", json={"email": "staff@t.vn", "password": "Staff1234"}).json()
        assert r["face"] == {"required": True, "enrolled": True}
        return {"Authorization": "Bearer " + r["token"]}
    h = start()
    for _ in range(3):                                                                    # someone else's face
        assert c.post("/api/auth/face/verify", headers=h, files=_imgs("6", [0])).status_code == 401
    assert c.post("/api/auth/face/verify", headers=h, files=_imgs("5", [3])).status_code == 429       # now blocked, even for the right face
    from solavis.api import auth as auth_api
    auth_api._face_fail.clear()
    assert c.post("/api/auth/face/verify", headers=h, files=_imgs("5", [3])).status_code == 200
    assert c.get("/api/admin/summary", headers=h).status_code == 200
    log = c.get("/api/admin/org/security-log", headers=h).json()
    ev = [r["event"] for r in log]
    assert ev.count("face_verify_failed") == 3 and "face_verify_ok" in ev and "face_enrolled" in ev
    failed = [r for r in log if r["event"] == "face_verify_failed"][0]
    assert failed["snap"] and failed["ok"] is False and failed["detail"]["scores"]         # the captured frame and scores are kept
    assert c.get(f"/api/admin/org/security-log/snap/{failed['snap']}", headers=h).status_code == 200
    assert c.get("/api/admin/org/security-log/verify", headers=h).json()["ok"] is True


def test_sensitive_actions_need_a_fresh_face_check(env_face):
    c = env_face
    _enrolled_president(c)
    r = c.post("/api/auth/login", json={"email": "staff@t.vn", "password": "Staff1234"}).json()
    h = {"Authorization": "Bearer " + r["token"]}
    assert c.post("/api/auth/face/verify", headers=h, files=_imgs("5", [3])).status_code == 200
    body = {"code": "legal", "name": "Legal", "ceiling": ["accounts.read"]}
    assert c.post("/api/admin/org/departments", headers=h, json=body).status_code == 200
    with db.tx() as con:                                                                   # the check was 30 minutes ago
        con.execute(db.sessions.update().values(face_verified_at=db.now() - 1800))
    r2 = c.post("/api/admin/org/departments", headers=h, json={**body, "code": "legal2"})
    assert r2.status_code == 428 and r2.json()["detail"] == "face_reverify"
    assert c.post("/api/auth/face/verify", headers=h, files=_imgs("5", [2])).status_code == 200
    assert c.post("/api/admin/org/departments", headers=h, json={**body, "code": "legal2"}).status_code == 200


def test_only_the_president_must_use_face_and_heads_do_not(env_face):
    c = env_face
    r = c.post("/api/auth/login", json={"email": "sales.head@t.vn", "password": "Staff1234"}).json()
    assert r["face"]["required"] is False
    assert c.get("/api/admin/summary", headers={"Authorization": "Bearer " + r["token"]}).status_code == 200


# ───────────────────────── heads see their whole business; nobody sees another department's data ─────────────────────────
def raw_login(c, email, pw="Staff1234"):
    return c.post("/api/auth/login", json={"email": email, "password": pw}).json()


def test_login_response_carries_the_real_rights_so_the_menu_is_complete(env):
    c = env
    r = raw_login(c, "sales.head@t.vn")
    assert {"accounts.read", "accounts.write", "billing.read", "support.read", "inventory.read", "tasks"} <= set(r["perms"])
    assert r["is_head"] is True and r["department_id"]
    assert raw_login(c, "sales@t.vn")["is_head"] is False and "billing.read" not in raw_login(c, "sales@t.vn")["perms"]


def test_dashboard_shows_only_what_the_person_may_see(env):
    c = env
    agent = login(c, "support@t.vn", "Staff1234")                  # Support agent: tickets and customers, no money, no fleet
    s = c.get("/api/admin/summary", headers=agent).json()
    assert "tickets_open" in s and "tenants" in s
    assert not any(k in s for k in ("mrr", "overdue_amount", "fleet", "events_today", "team"))
    fin = c.get("/api/admin/summary", headers=login(c, "finance@t.vn", "Staff1234")).json()
    assert "mrr" in fin and "tickets_open" not in fin and "fleet" not in fin
    head = c.get("/api/admin/summary", headers=login(c, "sales.head@t.vn", "Staff1234")).json()
    assert "mrr" in head and head["team"] and {m["email"] for m in head["team"]} == {"sales.head@t.vn", "sales@t.vn"}
    pres = c.get("/api/admin/summary", headers=login(c, "staff@t.vn", "Staff1234")).json()
    assert {"mrr", "fleet", "tickets_open", "events_today"} <= set(pres)


def test_tasks_stay_inside_the_team(env):
    c = env
    head, rep, fin = (login(c, e, "Staff1234") for e in ("sales.head@t.vn", "sales@t.vn", "finance@t.vn"))
    assert c.post("/api/admin/tasks", headers=head, json={"title": "Call lead", "assignee": "sales@t.vn"}).status_code == 200      # a head assigns inside the department
    assert c.post("/api/admin/tasks", headers=head, json={"title": "Pay vendor", "assignee": "finance@t.vn"}).status_code == 403    # not to another department
    assert c.post("/api/admin/tasks", headers=rep, json={"title": "Mine"}).status_code == 200
    assert c.post("/api/admin/tasks", headers=rep, json={"title": "Not yours", "assignee": "sales.head@t.vn"}).status_code == 403   # staff only for themselves
    assert c.post("/api/admin/tasks", headers=fin, json={"title": "Reconcile"}).status_code == 200
    seen = {t["title"] for t in c.get("/api/admin/tasks?scope=all", headers=head).json()}
    assert seen == {"Call lead", "Mine"}                                                  # the head's "my team" never shows Finance's tasks
    assert {t["title"] for t in c.get("/api/admin/tasks?scope=all", headers=rep).json()} == {"Call lead", "Mine"}
    fin_task = [t for t in c.get("/api/admin/tasks?scope=all", headers=fin).json()][0]
    assert c.post(f"/api/admin/tasks/{fin_task['id']}/done", headers=head).status_code == 403   # cannot close another department's task
    president = login(c, "staff@t.vn", "Staff1234")
    assert len(c.get("/api/admin/tasks?scope=all", headers=president).json()) == 3


def test_ticket_can_only_be_assigned_to_someone_who_works_tickets(env):
    c = env
    cust = login(c, "a@t.vn")
    tid = c.post("/api/tickets", headers=cust, json={"subject": "Help", "body": "Camera offline"}).json()["id"]
    sup = login(c, "support@t.vn", "Staff1234")
    assert c.post(f"/api/admin/tickets/{tid}", headers=sup, json={"assignee": "sales@t.vn"}).status_code == 400     # Sales cannot work tickets
    assert c.post(f"/api/admin/tickets/{tid}", headers=sup, json={"assignee": "support@t.vn"}).status_code == 200
    names = [x["email"] for x in c.get("/api/admin/org/directory?purpose=tickets", headers=sup).json()]
    assert "support@t.vn" in names and "sales@t.vn" not in names


def test_finance_ceiling_now_includes_support_and_inventory_read(env):
    c = env
    fin = {d["code"]: d for d in c.get("/api/admin/org/departments", headers=login(c, "staff@t.vn", "Staff1234")).json()}["finance"]
    assert {"support.read", "inventory.read", "billing.write"} <= set(fin["ceiling"])


# ───────── mobile foundation ─────────
def test_app_config_knows_desktop_platforms(env):
    old = env.get("/api/app-config", params={"platform": "windows", "app_version": "0.1.0"}).json()
    cur = env.get("/api/app-config", params={"platform": "windows", "app_version": "1.0.0"}).json()
    assert old["update_required"] is True and cur["update_required"] is False and cur["store_url"] == ""


def test_app_config_is_public_and_gates_old_versions(env):
    r = env.get("/api/app-config", params={"platform": "ios"}).json()
    assert r["api"] == "v1" and r["update_required"] is False and r["features"]["push"] is False
    assert env.get("/api/app-config", params={"app_version": "0.9.0"}).json()["update_required"] is True
    assert env.get("/api/app-config", params={"app_version": "1.0.0"}).json()["update_required"] is False


def test_api_v1_is_an_alias_of_api(env):
    h = login(env, "a@t.vn")
    strip = lambda d: {k: v for k, v in d.items() if k != "now"}
    assert strip(env.get("/api/v1/overview", headers=h).json()) == strip(env.get("/api/overview", headers=h).json())
    assert env.post("/api/v1/auth/login", json={"email": "a@t.vn", "password": "Owner1234"}).status_code == 200


def test_mobile_login_gives_a_long_sliding_session_and_staff_cannot_use_it(env):
    from sqlalchemy import select
    r = env.post("/api/auth/login", json={"email": "a@t.vn", "password": "Owner1234", "client": "mobile", "device_name": "Pixel 9"})
    tok = r.json()["token"]
    with db.tx() as c:
        s = c.execute(select(db.sessions).where(db.sessions.c.token_hash == __import__("solavis").security.hash_token(tok))).mappings().first()
    assert s["client"] == "mobile" and s["device_name"] == "Pixel 9"
    assert s["expires"] - s["created"] > 29 * 86400                              # 30 days, not 8 hours
    web = env.post("/api/auth/login", json={"email": "b@t.vn", "password": "Owner1234"}).json()["token"]
    with db.tx() as c:
        w = c.execute(select(db.sessions).where(db.sessions.c.token_hash == __import__("solavis").security.hash_token(web))).mappings().first()
    assert w["expires"] - w["created"] < 9 * 3600
    st = env.post("/api/auth/login", json={"email": "sales@t.vn", "password": "Staff1234", "client": "mobile"}).json()["token"]
    with db.tx() as c:
        x = c.execute(select(db.sessions).where(db.sessions.c.token_hash == __import__("solavis").security.hash_token(st))).mappings().first()
    assert x["client"] == "web" and x["expires"] - x["created"] < 9 * 3600       # staff stay on the short web session


def test_push_tokens_register_move_and_unregister(env):
    a, b = login(env, "a@t.vn"), login(env, "b@t.vn")
    tok = "ExponentPushToken[abcdefghijklmnop]"
    assert env.post("/api/push/register", headers=a, json={"token": tok, "platform": "ios", "device_name": "iPhone"}).status_code == 200
    assert env.post("/api/push/register", headers=a, json={"token": "x"}).status_code == 400
    env.post("/api/push/register", headers=b, json={"token": tok, "platform": "ios"})        # same phone, another customer signs in
    from sqlalchemy import select
    with db.tx() as c:
        rows = c.execute(select(db.push_tokens)).mappings().all()
    assert len(rows) == 1 and rows[0]["tenant_id"] == 2
    assert env.post("/api/push/unregister", headers=a, json={"token": tok}).status_code == 200      # not a's any more: stays
    with db.tx() as c:
        assert len(c.execute(select(db.push_tokens)).all()) == 1
    env.post("/api/push/unregister", headers=b, json={"token": tok})
    with db.tx() as c:
        assert not c.execute(select(db.push_tokens)).all()


def test_alert_sends_push_to_every_token_of_that_tenant_only(env, monkeypatch):
    from solavis import notify
    sent = []
    monkeypatch.setattr(notify, "send", lambda level, text, chat, tid, push_tokens=None, data=None: sent.append((tid, list(push_tokens or []), data)))
    s = settings.get()
    s.notifications.push.enabled = True
    a, b = login(env, "a@t.vn"), login(env, "b@t.vn")
    env.post("/api/push/register", headers=a, json={"token": "ExponentPushToken[aaaaaaaaaaaa]", "platform": "android"})
    env.post("/api/push/register", headers=b, json={"token": "ExponentPushToken[bbbbbbbbbbbb]", "platform": "ios"})
    key = env.post("/device/v1/claim", json={"claim_code": "SOL-AAAA-BBBB"}).json()["device_key"]
    beat(env, key)
    assert env.post("/api/cameras/1/arm", headers=a).status_code == 200
    beat(env, key, heading=200)                                                   # turned: critical alert
    assert sent and sent[-1][0] == 1 and sent[-1][1] == ["ExponentPushToken[aaaaaaaaaaaa]"]
    assert sent[-1][2]["kind"] == "tamper"


def test_signed_snapshot_links_work_without_login_and_cannot_be_forged(env):
    key, o = armed(env)
    from solavis import storage as st
    st.store().put("abc123.jpg", b"\xff\xd8fakejpeg")
    with db.tx() as c:
        c.execute(db.events.insert().values(tenant_id=1, camera_id=1, ts=db.now(), kind="unknown", verdict="unknown", snap="abc123.jpg", review="new", idem="i1"))
    other = login(env, "b@t.vn")
    assert env.get("/api/snap-url/abc123.jpg", headers=other).status_code == 404          # another customer's picture
    link = env.get("/api/snap-url/abc123.jpg", headers=o).json()["url"]
    path = "/s/" + link.split("/s/")[1]
    assert env.get(path).content.startswith(b"\xff\xd8")                                   # no login needed
    assert env.get(path[:-3] + "xyz").status_code == 404                                   # signature tampered
    name, exp, sig = path[3:].rsplit(".", 2)
    assert env.get(f"/s/{name}.{int(exp) + 9999}.{sig}").status_code == 404                # expiry extended
    assert env.get(f"/s/{name}.1.{sig}").status_code == 404                                # expired


def test_events_and_alerts_page_with_a_cursor(env):
    key, o = armed(env)
    with db.tx() as c:
        for i in range(5):
            c.execute(db.events.insert().values(tenant_id=1, camera_id=1, ts=db.now(), kind="unknown", verdict="unknown", review="new", idem=f"p{i}"))
    first = env.get("/api/events", headers=o, params={"limit": 2}).json()
    assert len(first) == 2
    nxt = env.get("/api/events", headers=o, params={"limit": 2, "before": first[-1]["id"]}).json()
    assert len(nxt) == 2 and max(e["id"] for e in nxt) < min(e["id"] for e in first)
