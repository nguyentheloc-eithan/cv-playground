# Decisions and trade-offs

| Decision | Why | Cost / risk accepted |
|---|---|---|
| Recognise in the cloud, detect on camera | chip too small for the model; stolen camera exposes nothing | needs connectivity; 4G data per event |
| Ready-made boards, no custom PCB | pilot in ~10 weeks | bigger, pricier unit; custom board later |
| Layered tamper detection | no single sensor is enough (tilt blind to turns; magnet defeatable) | more parts, more tuning, false-alarm risk |
| Server is the authority | modified firmware gains nothing; camera cannot unlock itself | camera depends on cloud for state |
| Warm-white LED, not infrared | IR hurts recognition | uses more power, visible light |
| Thresholds and tamper limits in YAML | tune per site without firmware | wrong values can weaken security, so strict validation |
| Deep sleep + wake sources | solar budget ~0.5 to 0.8 Wh/day | latency on first wake; needs measuring |
| Compass uses change-from-baseline | metal distorts absolute heading | cannot detect slow drift beyond limit |
| Plans and limits as data | change pricing without deploy | must enforce per request (done) |
| Sources with capabilities | same cloud can later serve third-party cameras | small abstraction cost now |
| Parametric enclosure in code | one parameter block; reviewable diff | needs real-part dimensions confirmed |
| Department ceilings + head delegation | scales admin without giving everyone everything | more concepts than flat roles |
| President face auth, fresh re-verify | highest-privilege account needs strong, recorded auth | webcam and secure origin needed; liveness only basic |
| Hash-chained security log | edits become detectable | single-writer assumption |
| Own design system, no UI kit | consistent, light, no dependency | more CSS to maintain |
| SQLite default, PostgreSQL by config | zero-setup demo, production path | production DBs unverified on real servers |
| YAML config validated at start-up | typos fail loudly | stricter first run |
| No ORM models, SQLAlchemy Core | explicit SQL, small | more manual code |

## What I would change with more time
Migrations (Alembic), real PostgreSQL run with row-level security, evaluation set for accuracy, stronger liveness, firmware with OTA, payment gateway and e-invoice, email/push, measured power data, printed and weather-tested enclosure.
