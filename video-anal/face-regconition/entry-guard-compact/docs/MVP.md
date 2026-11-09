# Entry Guard Compact: MVP status

## What it does
1. **Register a face:** in the browser, capture 1 to 10 photos from the camera, enter the person's
   details, save. Each photo must contain exactly one clear face.
2. **Check a face:** capture the live camera view (button, or automatically every second). Every
   face found is compared with all registered people and labelled:

| Result | Meaning | Rule (from config) |
|---|---|---|
| AUTHORIZED | Matches a registered person | score >= `accept_threshold` |
| UNCERTAIN | Close but not sure | between the two thresholds |
| UNKNOWN | Nobody registered looks like this | score < `reject_threshold` |
| NO FACE | No usable face in the picture | face smaller than `policy.min_face_px` |

The score is similarity from 0 to 1 (higher = more alike).
3. **Manage people:** list registered people, delete one (their face data is erased too).
4. **Per-customer settings:** one YAML file per customer, nothing hard-coded.

## Run
```
cd entry-guard-compact
../entry-guard/.venv/bin/python main.py --customer example   # or your own venv
```
Open http://127.0.0.1:8000, allow the camera. Options: `--host`, `--port`.
Camera access works only on `localhost` / `127.0.0.1` or HTTPS.

## Configuration
`config/default.yaml` applies to everyone; `config/customers/<name>.yaml` overrides only what
differs (deep merge; lists are replaced whole). `${NAME}` reads an environment variable.

| Section | What a customer can change |
|---|---|
| `customer.name` | Name shown in the page |
| `person_fields` | Fields of the register form (key, label, required). Example: apartment `unit_no`, or office `employee_id` |
| `models` | Model files and detector confidence |
| `registration` | Min/max photos, smallest accepted face |
| `policy` | `accept_threshold`, `reject_threshold`, `min_face_px` |
| `storage.database` | Path of the SQLite file |

Rule: `reject_threshold` must not exceed `accept_threshold` (checked at start-up).

## Code map
| File | Job |
|---|---|
| `main.py` | Start-up: config, models, database, recognizer, server |
| `app/config.py` | Load and merge config |
| `app/faces.py` | YuNet finds faces, SFace turns a face into a 128-number vector |
| `app/db.py` | SQLite: `person` and `vector` tables |
| `app/recognize.py` | `register()` and `check()`, the product logic |
| `app/server.py` | Standard-library web server and API |
| `app/static/index.html` | The single page UI |
| `tests/test_compact.py` | Tests with a fake AI engine (no camera or models needed) |

## HTTP API (used by the page)
| Method and path | Body | Returns |
|---|---|---|
| GET `/` | | the page |
| GET `/api/config` | | `{customer, fields}` |
| GET `/api/people` | | list of `{id, name, fields}` |
| POST `/api/register` | `{name, fields, images:[data-url]}` | 201 `{id, name}` |
| POST `/api/check` | `{image: data-url}` | list of `{decision, score, person, fields, bbox}` |
| POST `/api/delete` | `{id}` | `{ok:true}` |

Errors: `{"error": {"code": "...", "message": "..."}}` with status 400. Codes: `MISSING_FIELD`,
`UNKNOWN_FIELD`, `PHOTO_COUNT`, `FACE_COUNT`, `FACE_SMALL`, `BAD_IMAGE`, `BAD_REQUEST`.

## Data stored
`data/entryguard.db` (git-ignored): people (name, custom fields) and face vectors.
Photos are **not** kept, only the vectors. Deleting a person deletes their vectors.

## Known limits (by design for the MVP)
- **No anti-spoofing:** a printed photo or a phone screen can pass as a real face.
- **No login:** anyone who can open the page can register or delete people. Keep it on localhost.
- **No live camera loop:** checks use browser snapshots; IP/RTSP cameras are not connected yet.
- **No event history or alerts:** results are shown on screen only.
- **No tracking:** each snapshot is judged alone, one frame at a time.
- **Single request at a time:** fine for one user, not for many.
- **Thresholds are defaults** (SFace 0.363); tune them with your own camera and lighting.
- **Tests cover the logic only**, using a fake engine; real-model accuracy is not measured.

## Suggested next steps
1. Measure thresholds with real people (same person vs different people) and set them per customer.
2. Add a liveness check, then login with a PIN or password.
3. Connect the door IP camera (RTSP) with tracking and a decision per person, not per frame.
4. Save events with snapshots and send unknown-person alerts.
