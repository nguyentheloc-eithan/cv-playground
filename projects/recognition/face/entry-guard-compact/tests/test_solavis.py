"""Solavis cloud: config validation, auth, tamper state machine, subscription control, tenant isolation, admin console."""
import io
import textwrap

import pytest
from fastapi.testclient import TestClient

from solavis import db, settings, storage


@pytest.fixture()
def env(tmp_path, monkeypatch):
    (tmp_path / "database.yaml").write_text(f"driver: sqlite\nurl: sqlite:///{tmp_path}/t.db\n")
    (tmp_path / "storage.yaml").write_text(f"driver: local\nlocal:\n  path: {tmp_path}/snaps\n")
    monkeypatch.setenv("SOLAVIS_CONFIG_DIR", str(tmp_path))
    settings.get.cache_clear(); db.reset_engine(); storage.reset()
    from solavis import security
    security.guard.fails.clear()
    from solavis.app import create_app
    from solavis.manage import cmd_seed
    import argparse
    pkg = tmp_path / "pkg.yaml"
    pkg.write_text(textwrap.dedent("""
        name: t
        staff:
          - {email: staff@t.vn, password: Staff1234, staff_role: admin}
          - {email: sales@t.vn, password: Staff1234, staff_role: sales}
          - {email: support@t.vn, password: Staff1234, staff_role: support}
          - {email: finance@t.vn, password: Staff1234, staff_role: finance}
        inventory: {count: 4, model: Test Cam, prefix: T-1}
        tenants:
          - {name: A Home, plan: home, status: active, users: [{email: a@t.vn, password: Owner1234, role: owner}, {email: av@t.vn, password: Viewer1234, role: member}],
             cameras: [{name: Gate, claim_code: SOL-AAAA-BBBB}]}
          - {name: B Shop, plan: lite, status: active, users: [{email: b@t.vn, password: Owner1234, role: owner}], cameras: [{name: Door, claim_code: SOL-CCCC-DDDD}]}
    """))
    with TestClient(create_app()) as client:
        cmd_seed(argparse.Namespace(package=str(pkg)))
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
    sup = login(c, "support@t.vn", "Staff1234")
    unit = [i for i in c.get("/api/admin/inventory?status=assigned", headers=sup).json() if i["tenant_id"] == 1][0]
    assert c.post(f"/api/admin/inventory/{unit['id']}/rma", headers=sup, json={}).status_code == 400
    assert c.post(f"/api/admin/inventory/{unit['id']}/rma", headers=sup, json={"reason": "customer reported theft, ticket 4"}).status_code == 200
    assert c.get("/device/v1/config", headers={"Authorization": f"Bearer {key}"}).status_code == 401
    assert any(a["action"] == "device_rma" for a in c.get("/api/admin/audit", headers=login(c, "staff@t.vn", "Staff1234")).json())


def test_staff_roles_limit_what_each_person_can_do(env):
    c = env
    sales, support, fin = (login(c, f"{n}@t.vn", "Staff1234") for n in ("sales", "support", "finance"))
    assert c.get("/api/admin/invoices", headers=support).status_code == 403          # support cannot read billing
    assert c.post("/api/admin/invoices", headers=sales, json={"tenant_id": 1}).status_code == 403   # sales cannot create invoices
    assert c.get("/api/admin/tickets", headers=fin).status_code == 403
    assert c.get("/api/admin/staff", headers=sales).status_code == 403
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
              "/api/admin/tickets", "/api/admin/inventory", "/api/admin/tasks?scope=all", "/api/admin/staff", "/api/admin/roles", "/api/admin/audit", "/api/admin/system"]:
        assert c.get(p, headers=st).status_code == 200, p


def test_every_customer_page_endpoint_returns_200(env):
    c = env
    o = login(c, "a@t.vn")
    for p in ["/api/overview", "/api/devices", "/api/alerts", "/api/events", "/api/people", "/api/reports", "/api/activity", "/api/tickets", "/api/billing", "/api/team", "/api/export"]:
        assert c.get(p, headers=o).status_code == 200, p
