"""Database layer (SQLAlchemy Core). One schema for SQLite, PostgreSQL and MySQL; the driver comes from config/database.yaml."""
import time
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import (Boolean, Column, Float, ForeignKey, Index, Integer, LargeBinary, MetaData, String, Table, Text,
                        create_engine, event, select, text)

from . import settings

md = MetaData()
S = lambda n=255: String(n)   # noqa: E731  (short text, needs a length on MySQL)

plans = Table("plans", md,
              Column("id", S(40), primary_key=True), Column("name", S(80)), Column("max_cameras", Integer),
              Column("max_people", Integer), Column("events_per_day", Integer), Column("watchlist", Boolean, default=False), Column("price_vnd", Integer, default=0))
tenants = Table("tenants", md,
                Column("id", Integer, primary_key=True, autoincrement=True), Column("name", S(160)),
                Column("plan_id", S(40), ForeignKey("plans.id")), Column("status", S(20), default="trial"),
                Column("trial_end", Float), Column("past_due_since", Float), Column("telegram_chat", S(80)),
                Column("notes", Text), Column("created", Float), Column("closed_at", Float),
                Column("contact_name", S(160)), Column("phone", S(40)), Column("address", S(300)), Column("tax_code", S(40)),
                Column("industry", S(80)), Column("source", S(60)), Column("account_manager", S(190)))
users = Table("users", md,
              Column("staff_role", S(20)),
              Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, ForeignKey("tenants.id")),
              Column("email", S(190), unique=True), Column("name", S(120)), Column("pw_hash", S(300)),
              Column("role", S(20)), Column("active", Boolean, default=True), Column("must_change_pw", Boolean, default=False),
              Column("created", Float), Column("last_login", Float))
sessions = Table("sessions", md,
                 Column("token_hash", S(64), primary_key=True), Column("user_id", Integer, ForeignKey("users.id")),
                 Column("created", Float), Column("expires", Float))
cameras = Table("cameras", md,
                Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, ForeignKey("tenants.id")),
                Column("name", S(120)), Column("claim_code", S(40), unique=True), Column("key_hash", S(64), index=True),
                Column("state", S(20), default="unclaimed"), Column("source_type", S(30), default="solavis_cam"),
                Column("capabilities", Text, default="[]"), Column("last_seen", Float), Column("battery", Integer),
                Column("net", S(20)), Column("rssi", Integer), Column("tilt", Float), Column("heading", Float),
                Column("base_tilt", Float), Column("base_heading", Float), Column("base_hist", Text),
                Column("lock_reason", S(40)), Column("service_until", Float), Column("quiet_alerted", Boolean, default=False),
                Column("created", Float), Column("fw_version", S(40)))
people = Table("people", md,
               Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, ForeignKey("tenants.id"), index=True),
               Column("name", S(160)), Column("kind", S(20)), Column("consent", Text), Column("created", Float))
vectors = Table("vectors", md,
                Column("id", Integer, primary_key=True, autoincrement=True), Column("person_id", Integer, ForeignKey("people.id")),
                Column("tenant_id", Integer, index=True), Column("vec", LargeBinary))
events = Table("events", md,
               Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, index=True),
               Column("camera_id", Integer), Column("ts", Float), Column("person_id", Integer), Column("name", S(160)),
               Column("kind", S(20)), Column("score", Float), Column("verdict", S(20)), Column("snap", S(120)),
               Column("review", S(20), default="new"), Column("idem", S(64), unique=True))
alerts = Table("alerts", md,
               Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, index=True),
               Column("camera_id", Integer), Column("ts", Float), Column("level", S(12)), Column("kind", S(20)),
               Column("text", Text), Column("snap", S(120)), Column("acked", Boolean, default=False))
audit = Table("audit", md,
              Column("id", Integer, primary_key=True, autoincrement=True), Column("ts", Float), Column("actor", S(190)),
              Column("tenant_id", Integer), Column("action", S(60)), Column("target", Text))
contacts = Table("contacts", md,
                 Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, ForeignKey("tenants.id"), index=True),
                 Column("name", S(160)), Column("email", S(190)), Column("phone", S(40)), Column("title", S(80)), Column("created", Float))
notes = Table("notes", md,
              Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, ForeignKey("tenants.id"), index=True),
              Column("author", S(190)), Column("text", Text), Column("pinned", Boolean, default=False), Column("created", Float))
tasks = Table("tasks", md,
              Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer),
              Column("title", S(240)), Column("due", Float), Column("status", S(12), default="open"), Column("assignee", S(190)),
              Column("created_by", S(190)), Column("created", Float), Column("done_at", Float))
tickets = Table("tickets", md,
                Column("id", Integer, primary_key=True, autoincrement=True), Column("tenant_id", Integer, ForeignKey("tenants.id"), index=True),
                Column("subject", S(240)), Column("status", S(12), default="open"), Column("priority", S(12), default="normal"),
                Column("category", S(30), default="general"), Column("requester", S(190)), Column("assignee", S(190)),
                Column("created", Float), Column("updated", Float), Column("first_reply_at", Float), Column("solved_at", Float))
ticket_messages = Table("ticket_messages", md,
                        Column("id", Integer, primary_key=True, autoincrement=True), Column("ticket_id", Integer, ForeignKey("tickets.id"), index=True),
                        Column("author", S(190)), Column("author_type", S(10)), Column("body", Text), Column("internal", Boolean, default=False),
                        Column("created", Float))
invoices = Table("invoices", md,
                 Column("id", Integer, primary_key=True, autoincrement=True), Column("number", S(40), unique=True),
                 Column("tenant_id", Integer, ForeignKey("tenants.id"), index=True), Column("plan_id", S(40)),
                 Column("description", S(300)), Column("period_start", Float), Column("period_end", Float),
                 Column("subtotal", Integer), Column("tax", Integer), Column("total", Integer), Column("status", S(12), default="sent"),
                 Column("issued", Float), Column("due", Float), Column("paid_at", Float))
payments = Table("payments", md,
                 Column("id", Integer, primary_key=True, autoincrement=True), Column("invoice_id", Integer, ForeignKey("invoices.id"), index=True),
                 Column("amount", Integer), Column("method", S(30)), Column("ref", S(120)), Column("ts", Float), Column("recorded_by", S(190)))
inventory = Table("inventory", md,
                  Column("id", Integer, primary_key=True, autoincrement=True), Column("serial", S(60), unique=True), Column("model", S(60)),
                  Column("status", S(12), default="in_stock"), Column("tenant_id", Integer, index=True), Column("camera_id", Integer),
                  Column("warranty_until", Float), Column("cost_vnd", Integer), Column("notes", Text), Column("created", Float), Column("assigned_at", Float))
Index("ix_events_tenant_ts", events.c.tenant_id, events.c.ts)
Index("ix_alerts_tenant_ts", alerts.c.tenant_id, alerts.c.ts)

_engine = None


def database_url(cfg=None):
    d = (cfg or settings.get()).database
    if d.url:
        return d.url
    if d.driver == "sqlite":
        path = settings.ROOT / d.sqlite.path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"
    n = getattr(d, d.driver)
    scheme = "postgresql+psycopg" if d.driver == "postgresql" else "mysql+pymysql"
    url = f"{scheme}://{quote_plus(n.user)}:{quote_plus(n.password)}@{n.host}:{n.port}/{n.database}"
    if d.driver == "postgresql" and n.sslmode:
        url += f"?sslmode={n.sslmode}"
    return url


def engine():
    global _engine
    if _engine is None:
        cfg = settings.get().database
        url = database_url()
        kw = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kw["connect_args"] = {"check_same_thread": False, "timeout": 30}
        else:
            kw.update(pool_size=cfg.pool.size, max_overflow=cfg.pool.max_overflow, pool_recycle=cfg.pool.recycle_seconds)
        _engine = create_engine(url, **kw)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _pragmas(con, _):
                cur = con.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()
    return _engine


def reset_engine():
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


@contextmanager
def tx():
    """One transaction. Commits on success, rolls back on error."""
    with engine().begin() as c:
        yield c


def create_tables():
    md.create_all(engine())
    add_missing_columns()


def add_missing_columns():
    """Stop-gap until real migrations (Alembic): add columns that newer code expects to tables that already exist."""
    from sqlalchemy import inspect
    insp = inspect(engine())
    with engine().begin() as c:
        for t in md.sorted_tables:
            have = {col["name"] for col in insp.get_columns(t.name)}
            for col in t.columns:
                if col.name not in have:
                    ddl = col.type.compile(dialect=engine().dialect)
                    c.execute(text(f'ALTER TABLE {t.name} ADD COLUMN {col.name} {ddl}'))


def ping():
    with engine().connect() as c:
        c.execute(text("select 1"))
    return True


def now():
    return time.time()


def one(c, stmt):
    r = c.execute(stmt).mappings().first()
    return dict(r) if r else None


def many(c, stmt):
    return [dict(r) for r in c.execute(stmt).mappings().all()]


def insert(c, table, **vals):
    """Insert and return the new id (works on every driver)."""
    return c.execute(table.insert().values(**vals)).inserted_primary_key[0]


def sync_plans(c, plan_list):
    """Copy plans from config into the database when missing (never overwrites what admins edited)."""
    have = {r[0] for r in c.execute(select(plans.c.id))}
    for p in plan_list:
        if p.id not in have:
            c.execute(plans.insert().values(**p.model_dump()))
        else:   # fill a price on plans created before prices existed (never overwrites an admin's value)
            c.execute(plans.update().where(plans.c.id == p.id, plans.c.price_vnd.is_(None)).values(price_vnd=p.price_vnd))
