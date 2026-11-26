# System architecture

```
ESP32-S3 camera --HTTPS, bearer key--> Device API /device/v1 --> recognition (YuNet+SFace) + tamper evaluator
                                              |                       |
                                         SQL database  <--------- storage (local or S3-compatible)
                                              |
        Customer app (/)  <--- same FastAPI --->  Solavis ERP (/erp)   +  Telegram/webhook alerts
```
Diagram sources: `diagrams/architecture.mmd`.

## Stack
Python, FastAPI, SQLAlchemy Core, SQLite (default) / PostgreSQL / MySQL by config, S3-compatible storage option, OpenCV ONNX models, vanilla JS front ends (no framework, own design system), Docker + compose for production style, pytest. Firmware target: C++ on ESP32-S3 (not written).

## Device API v1
| Endpoint | Job |
|---|---|
| POST /claim | swap the printed claim code for a device key (shown once, stored as hash) |
| GET /config | state, lock reason, subscription, `upload` allowed?, check-in period, tamper limits |
| POST /heartbeat | battery, net, rssi, tilt, heading, cover, fw, tiny frame; server evaluates tamper; returns fresh config |
| POST /events | face crop + idempotency key; 423 if locked, 402 if subscription not active, 429 if daily plan limit; returns verdict |
| POST /tamper | immediate report from accelerometer/reed wake |

**Server is the authority:** every rule is checked server-side, so modified firmware gains nothing.

## Camera state machine
`unclaimed -> mounting -> armed -> locked -> service -> armed`, plus `revoked`. See `diagrams/tamper-states.mmd`. Lock is a conditional UPDATE so two racing workers raise only one alert.

## Data model (22 tables, highlights)
tenants, users (customer and staff), sessions, plans, cameras, people, vectors, events, alerts, audit, tickets/messages, invoices/payments, inventory units, tasks, departments, dept_roles, face_vectors, security_log.

## Multi-tenancy
Every row is scoped by `tenant_id`; customer endpoints derive the tenant from the session, never from input; tests attempt cross-tenant reads and writes.

## Subscription control
`entitlement()` computes an effective status from plan, trial end, grace days. Limits (cameras, people, events/day, watch-list) are plan data edited in the ERP without deploy. Suspended means the next wake-up gets `upload:false`.

## Configuration
One YAML per topic (server, database, storage, security, notifications, recognition, tamper, tenancy, plans, billing, departments), `${ENV}` expansion, pydantic strict models (typos fail start-up), stricter checks in production (secret length, secure cookie, no SQLite, no API docs). `SOLAVIS_CONFIG_DIR` overrides file by file. Seed "packages": demo and production.

## Background jobs
Quiet-camera check (missed check-ins), retention purge (events, snapshots), session cleanup.

## Known limits (state honestly)
No migrations tool yet; PostgreSQL/MySQL compile-verified, not run on real servers; login lockout in memory (single server); billing manual; no email/push; direct presigned upload not done.
