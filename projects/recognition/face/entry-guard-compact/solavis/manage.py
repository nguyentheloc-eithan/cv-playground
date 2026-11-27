"""Command line for operators.

  python -m solavis.manage check-config
  python -m solavis.manage init-db
  python -m solavis.manage seed --package demo          # or: production, or a path to your own YAML
  python -m solavis.manage create-staff you@company.com
  python -m solavis.manage run                           # start the server using config/server.yaml
  python -m solavis.manage reset --yes                   # DROP every table (development only)
"""
import argparse
import getpass
import glob
import sys

from sqlalchemy import select

from . import db, security, settings


def cmd_check(a):
    cfg = settings.get()
    print("Config OK.")
    print(f"  environment : {cfg.server.environment}")
    print(f"  database    : {cfg.database.driver}  ({db.database_url().split('@')[-1]})")
    print(f"  storage     : {cfg.storage.driver}")
    print(f"  telegram    : {'on' if cfg.notifications.telegram.enabled else 'off'}   webhook: {'on' if cfg.notifications.webhook.enabled else 'off'}")
    db.ping()
    print("  database connection: OK")


def cmd_init(a):
    cfg = settings.get()
    db.create_tables()
    with db.tx() as c:
        db.sync_plans(c, cfg.plans.plans)
    print("Database ready (tables created, plans synced).")


def cmd_seed(a):
    import random
    from . import recog, services
    from .db import contacts, events, inventory, notes, now, people, tasks, tenants, ticket_messages, tickets
    cfg = settings.get()
    pkg = settings.load_package(a.package)
    db.create_tables()
    made = {}
    bump = lambda k, n=1: made.__setitem__(k, made.get(k, 0) + n)   # noqa: E731
    rnd = random.Random(7)
    with db.tx() as c:
        db.sync_plans(c, cfg.plans.plans)
        services.sync_departments(c, cfg.org.departments)
        # heads are created after their staff exist only when listed; create everyone, then appoint heads
        for s_ in pkg.get("staff", []):
            if c.execute(select(db.users.c.id).where(db.users.c.email == s_["email"].lower())).first():
                continue
            dept = db.one(c, select(db.departments).where(db.departments.c.code == s_.get("department", "executive")))
            if not dept:
                raise SystemExit(f"package error: unknown department '{s_.get('department')}' for {s_['email']}")
            role = db.one(c, select(db.dept_roles).where(db.dept_roles.c.department_id == dept["id"], db.dept_roles.c.name == s_["role"])) if s_.get("role") else None
            if s_.get("role") and not role:
                raise SystemExit(f"package error: department '{dept['code']}' has no role '{s_['role']}'")
            uid, pw = services.create_staff(c, s_["email"], dept["id"], s_.get("password"), s_.get("name", ""), s_.get("job_title", ""), role["id"] if role else None, "seed",
                                            is_super=bool(s_.get("president")), head=bool(s_.get("head")), must_change=bool(s_.get("must_change")))
            made["staff"] = made.get("staff", 0) + 1
            if s_.get("president"):
                if s_.get("enroll_code"):          # demo packages may fix the code; production prints a random one
                    code = s_["enroll_code"]
                    c.execute(db.users.update().where(db.users.c.id == uid).values(enroll_hash=security.hash_token(code), enroll_expires=now() + 365 * 86400))
                else:
                    code = services.issue_enroll_code(c, uid)
                print(f"\n  PRESIDENT {s_['email']}: one-time face enrollment code  {code}\n  (sign in with the password, then enrol your face with this code)\n")
        inv_def = pkg.get("inventory", {})
        for t in pkg.get("tenants", []):
            row = db.one(c, select(tenants).where(tenants.c.name == t["name"]))
            if row:
                tid = row["id"]
            else:
                tid = services.create_tenant(c, t["name"], t.get("plan"), t.get("status", "trial"), "seed", t.get("trial_days"))
                set_tenant(c, tid, {k: t[k] for k in ("contact_name", "phone", "address", "tax_code", "industry", "source", "account_manager") if k in t})
                bump("tenants")
                for ct in t.get("contacts", []):
                    db.insert(c, contacts, tenant_id=tid, created=now(), **ct); bump("contacts")
                for nt in t.get("notes", []):
                    db.insert(c, notes, tenant_id=tid, author=nt.get("author", "seed"), text=nt["text"], pinned=bool(nt.get("pinned")), created=now() - nt.get("days_ago", 0) * 86400); bump("notes")
                for tk in t.get("tasks", []):
                    db.insert(c, tasks, tenant_id=tid, title=tk["title"], due=now() + tk.get("due_days", 3) * 86400, status="open", assignee=tk.get("assignee"), created_by="seed", created=now()); bump("tasks")
                for tkt in t.get("tickets", []):
                    ago = now() - tkt.get("days_ago", 1) * 86400
                    tk_id = db.insert(c, tickets, tenant_id=tid, subject=tkt["subject"], status=tkt.get("status", "open"), priority=tkt.get("priority", "normal"),
                                      category=tkt.get("category", "general"), requester=tkt.get("requester", ""), assignee=tkt.get("assignee"), created=ago, updated=ago)
                    for i, m in enumerate(tkt.get("messages", [])):
                        db.insert(c, ticket_messages, ticket_id=tk_id, author=m["author"], author_type=m["type"], body=m["body"], internal=bool(m.get("internal")), created=ago + i * 3600)
                    bump("tickets")
                for iv in t.get("invoices", []):
                    iid, num = services.create_invoice(c, tid, iv.get("months", 1), None, "seed", issued=now() - iv.get("days_ago", 0) * 86400)
                    if iv.get("paid"):
                        services.mark_paid(c, iid, "bank_transfer", "demo", "seed")
                    bump("invoices")
                set_tenant(c, tid, {"status": t.get("status", "trial")})
                if t.get("status") == "past_due":
                    set_tenant(c, tid, {"past_due_since": now() - 3 * 86400})
            for u in t.get("users", []):
                if not c.execute(select(db.users.c.id).where(db.users.c.email == u["email"].lower())).first():
                    services.create_user(c, u["email"], u.get("password"), u.get("role", "owner"), tid, name=u.get("name", ""), actor="seed", must_change=bool(u.get("must_change")))
                    bump("users")
            for cm in t.get("cameras", []):
                if not cm.get("claim_code") or not c.execute(select(db.cameras.c.id).where(db.cameras.c.claim_code == cm["claim_code"])).first():
                    serial = cm.get("serial") or f"SOL-DEMO-{cm.get('claim_code', 'X')[-4:]}"
                    if not db.one(c, select(inventory).where(inventory.c.serial == serial)):
                        db.insert(c, inventory, serial=serial, model="Solavis Cam 4G", status="in_stock", cost_vnd=2000000, warranty_until=now() + 365 * 86400, created=now())
                    services.create_camera(c, tid, cm["name"], cm.get("claim_code"), "seed", serial=serial)
                    bump("cameras")
            for p in t.get("people", []):
                if db.one(c, select(people.c.id).where(people.c.tenant_id == tid, people.c.name == p["name"])):
                    continue
                files = sorted(glob.glob(str(settings.ROOT / p["photos"])))[: int(p.get("max_photos", 3))]
                vecs = [v for v in (recog.single_face_vector(recog.decode(open(f, "rb").read())) for f in files) if v is not None]
                if not vecs:
                    print(f"  skipped person {p['name']}: no usable photo in {p['photos']}")
                    continue
                services.add_person(c, tid, p["name"], p.get("kind", "known"), p.get("consent", "seed data"), vecs, "seed")
                bump("people")
            days = int(t.get("history_days", 0))
            cams = db.many(c, select(db.cameras.c.id).where(db.cameras.c.tenant_id == tid))
            if days and cams and not c.execute(select(events.c.id).where(events.c.tenant_id == tid)).first():
                ppl = db.many(c, select(people.c.id, people.c.name, people.c.kind).where(people.c.tenant_id == tid))
                n = 0
                for d in range(days, 0, -1):
                    for _ in range(rnd.randint(3, 12)):
                        ts = now() - d * 86400 + rnd.choice([7, 8, 9, 12, 13, 17, 18, 19, 20, 22]) * 3600 + rnd.randint(0, 3000)
                        who = rnd.choice(ppl) if ppl and rnd.random() < 0.6 else None
                        wl = bool(who and who["kind"] == "watchlist")
                        if who and wl and rnd.random() < 0.7:
                            who = None
                        db.insert(c, events, tenant_id=tid, camera_id=cams[0]["id"], ts=ts, person_id=who["id"] if who else None, name=who["name"] if who else None,
                                  kind=who["kind"] if who else "unknown", score=round(rnd.uniform(0.4, 0.8), 2) if who else None,
                                  verdict="known" if who else "unknown", snap=None, review="new", idem=f"seed-{tid}-{n}")
                        n += 1
                bump("events", n)
        for item in ([inv_def] if inv_def else []):
            have = c.execute(select(inventory.c.id)).all()
            want = int(item.get("count", 0))
            if len(have) < want:
                prefix = item.get("prefix", "SOL-2611")
                for i in range(want - len(have)):
                    db.insert(c, inventory, serial=f"{prefix}-{i + 1:04d}", model=item.get("model", "Solavis Cam 4G"), status="in_stock", cost_vnd=item.get("cost_vnd"),
                              warranty_until=now() + 365 * 86400, created=now())
                    bump("inventory")
    print(f"Package '{pkg.get('name', a.package)}' loaded: " + (", ".join(f"{v} {k}" for k, v in made.items()) or "nothing new"))
    for s_ in pkg.get("staff", []):
        print(f"  staff : {s_['email']} ({s_.get('department', 'executive')}{', head' if s_.get('head') else ''}{', PRESIDENT' if s_.get('president') else ''})")
    for t in pkg.get("tenants", []):
        for u in t.get("users", []):
            print(f"  {t['name']}: {u['email']} ({u.get('role', 'owner')})")
    if pkg.get("name") == "demo":
        print("  (demo password for all demo accounts: demo1234)")


def set_tenant(c, tid, vals):
    from .db import tenants
    if vals:
        c.execute(tenants.update().where(tenants.c.id == tid).values(**vals))


def cmd_staff(a):
    from . import services
    pw = a.password or getpass.getpass("Password (empty = generate): ") or None
    db.create_tables()
    with db.tx() as c:
        services.sync_departments(c, settings.get().org.departments)
        dept = db.one(c, select(db.departments).where(db.departments.c.code == a.department))
        if not dept:
            sys.exit(f"unknown department '{a.department}'")
        role = db.one(c, select(db.dept_roles).where(db.dept_roles.c.department_id == dept["id"], db.dept_roles.c.name == a.role)) if a.role else None
        uid, pw2 = services.create_staff(c, a.email, dept["id"], pw, a.name or "", "", role["id"] if role else None, "cli", is_super=a.president, head=a.head, must_change=True if not a.password else None)
        code = services.issue_enroll_code(c, uid) if a.president else None
    print(f"Staff user created: {a.email} ({dept['name']}{', PRESIDENT' if a.president else ''}{', head' if a.head else ''})")
    if not pw:                              # only show a password we generated; never echo one the operator typed
        print(f"Temporary password: {pw2}  (must be changed at first sign-in)")
    if code:
        print(f"One-time face enrollment code: {code}  (valid {settings.get().security.face.enroll_code_hours} h)")


def cmd_reset(a):
    if not a.yes:
        sys.exit("Refusing to drop tables without --yes")
    if settings.get().server.environment == "production":
        sys.exit("Refusing to reset a production environment")
    db.md.drop_all(db.engine())
    print("All tables dropped.")


def cmd_openapi(a):
    """Write the API contract so a mobile app (or any client) can generate its client code from it."""
    import json
    from pathlib import Path
    from .app import create_app
    spec = create_app().openapi()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, sort_keys=True))
    print(f"wrote {out} ({len(spec['paths'])} paths)")


def cmd_run(a):
    import uvicorn
    s = settings.get().server
    uvicorn.run("solavis.app:create_app", factory=True, host=s.host, port=s.port, workers=s.workers, log_level="warning", proxy_headers=True)


def main():
    p = argparse.ArgumentParser(prog="solavis.manage")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-config").set_defaults(fn=cmd_check)
    sub.add_parser("init-db").set_defaults(fn=cmd_init)
    s = sub.add_parser("seed"); s.add_argument("--package", required=True); s.set_defaults(fn=cmd_seed)
    s = sub.add_parser("create-staff"); s.add_argument("email"); s.add_argument("--name"); s.add_argument("--department", default="executive"); s.add_argument("--role")
    s.add_argument("--head", action="store_true"); s.add_argument("--president", action="store_true"); s.add_argument("--password"); s.set_defaults(fn=cmd_staff)
    s = sub.add_parser("reset"); s.add_argument("--yes", action="store_true"); s.set_defaults(fn=cmd_reset)
    s = sub.add_parser("export-openapi"); s.add_argument("--out", default="docs/api/openapi.json"); s.set_defaults(fn=cmd_openapi)
    sub.add_parser("run").set_defaults(fn=cmd_run)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
