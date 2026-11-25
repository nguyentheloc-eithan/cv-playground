"""Configuration: one YAML file per topic, validated at start-up.

Files live in solavis/config/. Point SOLAVIS_CONFIG_DIR at your own folder to override them file by file
(a file missing there falls back to the shipped default). Values may use ${ENV} or ${ENV:-default}.
A typo in a key or a wrong type stops the server with a clear message instead of failing later.
"""
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent                       # the repository root
DEFAULT_DIR = PKG / "config"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Jobs(Strict):
    quiet_check_seconds: int = 5
    retention_seconds: int = 3600
    session_cleanup_seconds: int = 3600


class Server(Strict):
    host: str = "127.0.0.1"
    port: int = 8100
    workers: int = 1
    base_url: str = "http://127.0.0.1:8100"
    environment: Literal["development", "production"] = "development"
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    log_format: Literal["text", "json"] = "text"
    cors_origins: list[str] = []
    api_docs: bool = True
    max_upload_mb: int = 8
    serve_ui: bool = True
    jobs: Jobs = Jobs()


class SqliteCfg(Strict):
    path: str = "data/solavis/solavis.db"


class NetDb(Strict):
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "solavis"
    password: str = ""
    database: str = "solavis"
    sslmode: str = "prefer"


class Pool(Strict):
    size: int = 5
    max_overflow: int = 10
    recycle_seconds: int = 1800


class Database(Strict):
    driver: Literal["sqlite", "postgresql", "mysql"] = "sqlite"
    url: str = ""
    sqlite: SqliteCfg = SqliteCfg()
    postgresql: NetDb = NetDb()
    mysql: NetDb = NetDb(port=3306)
    pool: Pool = Pool()
    auto_create_tables: bool = True


class LocalStore(Strict):
    path: str = "data/solavis/snaps"


class S3Store(Strict):
    bucket: str = ""
    region: str = "auto"
    endpoint_url: str = ""
    access_key: str = ""
    secret_key: str = ""
    prefix: str = "snaps/"


class Storage(Strict):
    driver: Literal["local", "s3"] = "local"
    local: LocalStore = LocalStore()
    s3: S3Store = S3Store()


class Session(Strict):
    hours: int = 8
    cookie_name: str = "solavis_session"
    cookie_secure: bool = False
    cookie_samesite: Literal["strict", "lax"] = "strict"


class Password(Strict):
    min_length: int = 8
    must_change_on_first_login: bool = True


class LoginProtection(Strict):
    max_failures: int = 5
    lock_minutes: int = 5


class DeviceSec(Strict):
    key_bytes: int = 24
    clock_skew_seconds: int = 0


class Security(Strict):
    secret_key: str = "dev-only-change-me"
    session: Session = Session()
    password: Password = Password()
    login_protection: LoginProtection = LoginProtection()
    device: DeviceSec = DeviceSec()


class Telegram(Strict):
    enabled: bool = False
    bot_token: str = ""


class Webhook(Strict):
    enabled: bool = False
    url: str = ""
    secret: str = ""


class Notifications(Strict):
    telegram: Telegram = Telegram()
    webhook: Webhook = Webhook()
    min_level: Literal["info", "high", "critical"] = "info"
    timeout_seconds: int = 5


class Models(Strict):
    detector_file: str = "models/yunet.onnx"
    recognizer_file: str = "models/sface.onnx"
    detect_score_threshold: float = 0.8


class Thresholds(Strict):
    accept: float = 0.363
    reject: float = 0.30
    watchlist_confirm: float = 0.45


class Registration(Strict):
    max_photos: int = 10
    require_consent_note: bool = True


class Recognition(Strict):
    models: Models = Models()
    thresholds: Thresholds = Thresholds()
    min_face_px: int = 40
    registration: Registration = Registration()


class LockOn(Strict):
    moved: bool = True
    turned: bool = True
    cover_opened: bool = True
    view_changed: bool = True


class Tamper(Strict):
    tilt_limit_degrees: float = 8
    heading_limit_degrees: float = 15
    view_similarity_min: float = 0.55
    lock_on: LockOn = LockOn()
    checkin_seconds: int = 30
    quiet_after_missed: int = 3
    service_window_minutes: int = 15


class Retention(Strict):
    unknown_events: int = 30
    known_events: int = 90
    alerts: int = 180


class Tenancy(Strict):
    default_plan: str = "lite"
    trial_days: int = 14
    past_due_grace_days: int = 7
    closed_after_days: int = 30
    retention_days: Retention = Retention()
    claim_code_prefix: str = "SOL"
    max_users_per_tenant: int = 10


class PlanCfg(Strict):
    id: str
    name: str
    max_cameras: int
    max_people: int
    events_per_day: int
    watchlist: bool = False
    price_vnd: int = 0


class Plans(Strict):
    plans: list[PlanCfg] = Field(default_factory=list)


class Company(Strict):
    name: str = "Solavis Co., Ltd"
    address: str = ""
    tax_code: str = ""


class Bank(Strict):
    name: str = ""
    bank_code: str = ""
    account_no: str = ""
    account_name: str = ""


class Billing(Strict):
    currency: str = "VND"
    invoice_prefix: str = "INV"
    due_days: int = 7
    tax_rate_percent: float = 0
    company: Company = Company()
    bank: Bank = Bank()
    qr_enabled: bool = False


class Roles(Strict):
    roles: dict[str, list[str]] = Field(default_factory=lambda: {"admin": ["*"]})


class Settings(Strict):
    server: Server = Server()
    database: Database = Database()
    storage: Storage = Storage()
    security: Security = Security()
    notifications: Notifications = Notifications()
    recognition: Recognition = Recognition()
    tamper: Tamper = Tamper()
    tenancy: Tenancy = Tenancy()
    plans: Plans = Plans()
    billing: Billing = Billing()
    staff_roles: Roles = Roles()


_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand(value):
    """Replace ${NAME} / ${NAME:-default} with environment values, recursively."""
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v) for v in value]
    if isinstance(value, str):
        def sub(m):
            got = os.environ.get(m.group(1))
            if got is not None:
                return got
            if m.group(2) is not None:
                return m.group(2)
            raise SystemExit(f"Config error: environment variable {m.group(1)} is required but not set")
        return _ENV.sub(sub, value)          # pydantic turns "true" / "5432" into bool / int
    return value


def config_dir():
    return Path(os.environ.get("SOLAVIS_CONFIG_DIR", DEFAULT_DIR))


def read_yaml(name, directory=None):
    """Read one config file. A custom config dir wins, then the shipped default."""
    for d in ([Path(directory)] if directory else []) + [config_dir(), DEFAULT_DIR]:
        p = d / name
        if p.exists():
            return expand(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
    return {}


def load_settings() -> Settings:
    raw = {s: read_yaml(f"{s}.yaml") for s in
           ("server", "database", "storage", "security", "notifications", "recognition", "tamper", "tenancy", "plans", "billing")}
    raw["staff_roles"] = {"roles": read_yaml("roles.yaml")}
    try:
        cfg = Settings(**raw)
    except ValidationError as e:
        lines = [f"  {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise SystemExit("Config error in solavis/config:\n" + "\n".join(lines))
    problems = check(cfg)
    if problems:
        raise SystemExit("Config error:\n" + "\n".join("  - " + p for p in problems))
    return cfg


def check(cfg: Settings):
    """Cross-field rules, stricter in production."""
    out = []
    if cfg.recognition.thresholds.reject > cfg.recognition.thresholds.accept:
        out.append("recognition.thresholds.reject must not be higher than accept")
    if cfg.server.environment == "production":
        if cfg.security.secret_key in ("", "dev-only-change-me") or len(cfg.security.secret_key) < 32:
            out.append("security.secret_key must be a random value of 32+ characters in production (set SOLAVIS_SECRET)")
        if not cfg.security.session.cookie_secure:
            out.append("security.session.cookie_secure must be true in production (serve over HTTPS)")
        if cfg.database.driver == "sqlite" and not cfg.database.url:
            out.append("production should use PostgreSQL or MySQL, not SQLite (database.driver)")
        if cfg.server.api_docs:
            out.append("server.api_docs should be false in production")
    if cfg.storage.driver == "s3" and not cfg.storage.s3.bucket:
        out.append("storage.s3.bucket is required when storage.driver is s3")
    if cfg.notifications.telegram.enabled and not cfg.notifications.telegram.bot_token:
        out.append("notifications.telegram.bot_token is required when telegram is enabled")
    if cfg.notifications.webhook.enabled and not cfg.notifications.webhook.url:
        out.append("notifications.webhook.url is required when webhook is enabled")
    return out


def load_package(name):
    """A package is a YAML file in config/packages/ (demo, production, or your own)."""
    p = Path(name)
    if not p.suffix:
        p = config_dir() / "packages" / f"{name}.yaml"
        if not p.exists():
            p = DEFAULT_DIR / "packages" / f"{name}.yaml"
    if not p.exists():
        raise SystemExit(f"Package not found: {p}")
    return expand(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


@lru_cache
def get() -> Settings:
    return load_settings()


def masked(cfg: Settings):
    """The effective config with secrets hidden (for the admin System page)."""
    d = cfg.model_dump()
    hide = ("password", "secret", "token", "secret_key", "access_key")
    def walk(x):
        if isinstance(x, dict):
            return {k: ("********" if any(h in k for h in hide) and x[k] else walk(v)) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(i) for i in x]
        return x
    return walk(d)
