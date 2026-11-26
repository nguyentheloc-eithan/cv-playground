"""Application factory: wires config, database, API routers, background jobs and the two web apps."""
import json
import logging
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db, services, settings

HERE = Path(__file__).resolve().parent
log = logging.getLogger("solavis")


class JsonFormatter(logging.Formatter):
    def format(self, r):
        d = {"ts": round(time.time(), 3), "level": r.levelname, "logger": r.name, "msg": r.getMessage()}
        for k in ("request_id", "path", "status", "ms"):
            if hasattr(r, k):
                d[k] = getattr(r, k)
        return json.dumps(d)


def setup_logging(cfg):
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter() if cfg.server.log_format == "json" else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(cfg.server.log_level.upper())


def run_jobs(cfg, stop):
    jobs = [("quiet_check", services.quiet_check, cfg.server.jobs.quiet_check_seconds),
            ("retention", services.retention, cfg.server.jobs.retention_seconds),
            ("session_cleanup", services.session_cleanup, cfg.server.jobs.session_cleanup_seconds)]
    last = {n: 0.0 for n, _, _ in jobs}
    while not stop.wait(1):
        for name, fn, every in jobs:
            if time.time() - last[name] >= every:
                last[name] = time.time()
                try:
                    fn()
                except Exception:
                    log.exception("job %s failed", name)


def create_app() -> FastAPI:
    cfg = settings.get()
    setup_logging(cfg)
    stop = threading.Event()

    @asynccontextmanager
    async def lifespan(app):
        if cfg.database.auto_create_tables:
            db.create_tables()
        with db.tx() as c:
            db.sync_plans(c, cfg.plans.plans)
            services.sync_departments(c, cfg.org.departments)
        t = threading.Thread(target=run_jobs, args=(cfg, stop), daemon=True, name="jobs")
        t.start()
        log.info("Solavis started: env=%s db=%s storage=%s", cfg.server.environment, cfg.database.driver, cfg.storage.driver)
        yield
        stop.set()

    app = FastAPI(title="Solavis", version="1.0", lifespan=lifespan,
                  docs_url="/docs" if cfg.server.api_docs else None, redoc_url=None, openapi_url="/openapi.json" if cfg.server.api_docs else None)
    if cfg.server.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=cfg.server.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def wrap(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        t0 = time.time()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"request_id": rid, "path": request.url.path})
            return JSONResponse({"detail": "internal error", "request_id": rid}, status_code=500)
        u = getattr(request.state, "user", None)
        if u and u.get("is_super") and request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.url.path.startswith("/api/auth/"):
            try:                                  # everything the President changes is written to the tamper-evident log
                with db.tx() as c:
                    services.sec_log(c, "president_action", response.status_code < 400, user=u, ip=request.client.host if request.client else "",
                                     ua=request.headers.get("user-agent", ""), detail={"method": request.method, "path": request.url.path, "status": response.status_code})
            except Exception:
                log.exception("could not write the president action log")
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api") or request.url.path.startswith("/device"):
            response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
            log.info("%s %s", request.method, request.url.path, extra={"request_id": rid, "path": request.url.path, "status": response.status_code, "ms": int((time.time() - t0) * 1000)})
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        try:
            db.ping()
            return {"status": "ready"}
        except Exception as e:
            return JSONResponse({"status": "not ready", "error": str(e)[:120]}, status_code=503)

    from .api import admin, auth, billing, customer, device, inventory, org, support
    for r in (auth.router, customer.router, admin.router, device.router, billing.admin, billing.customer,
              support.admin, support.customer, inventory.router, org.router):
        app.include_router(r)

    if cfg.server.serve_ui:
        web = HERE / "web"
        app.mount("/assets", StaticFiles(directory=web / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def customer_app():
            return FileResponse(web / "customer.html")

        @app.get("/admin", include_in_schema=False)
        @app.get("/erp", include_in_schema=False)
        def admin_app():
            return FileResponse(web / "admin.html")

    return app
