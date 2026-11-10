# Entry Guard Compact

Register faces, then check whether a face is authorized. Built to be read top to bottom in
about 20 minutes. No frameworks, no classes you must learn first.

## Run
```
pip install -r requirements.txt
python main.py --customer example create-user admin --role admin   # asks for a password
python main.py --customer example
```
Open http://127.0.0.1:8000 and log in.

| Where | What |
|---|---|
| `/tf-check` | **Security console.** Scans live with the laptop camera, shows a verdict per person, keeps a searchable scan log (filters, snapshots, review, CSV export) |
| `#register` | Guided registration: live quality hints, auto-capture, consent |
| `#people` | List, search, edit, disable, delete (erases photos and face data) |
| `#cameras` | Laptop camera (default) and IP cameras (RTSP): add, edit, **test connection** |
| `#audit` | Who did what and when |
Models are in `models/` (see `models/README.md`).

## How it works (read the files in this order)
```
browser ──► server.py ──► recognize.py ──► faces.py   (AI: find face, make vector)
 (page)     (HTTP)        register / check  db.py      (SQLite: people and vectors)
                              ▲
                          config.py  (settings from config/*.yaml)
```
| File | One job |
|---|---|
| `main.py` | Wire the 5 parts together and start |
| `app/config.py` | Load `default.yaml` + customer file |
| `app/faces.py` | Detect faces, turn a face into 128 numbers |
| `app/db.py` | Save and load people |
| `app/recognize.py` | The two features: `register` and `check` |
| `app/server.py` | Web server and the page |

**Register:** photo → one face → vector → save with the name.
**Check:** photo → vector → compare with every saved vector → highest score decides:
`>= accept_threshold` authorized, `< reject_threshold` unknown, between = uncertain.

## Per-customer settings
Each customer is one small file in `config/customers/`. It only lists what is different from
`config/default.yaml`. Examples: form fields (`person_fields`), thresholds (`policy`), model
files (`models`). Start with `--customer name` or `ENTRYGUARD_CUSTOMER=name`.

## Tests
`pytest` runs without models or a camera (a fake engine stands in for the AI).

## Not in this version (on purpose)
Live camera streams, tracking people across frames, liveness (photo-of-a-photo) detection,
login, door control. Add them one at a time after this works.

## Adding an IP camera (any brand)
**Cameras > Add IP camera.** The stream path is never fixed. Use whichever is easiest:
1. **Paste a full address** (`rtsp://user:password@192.168.1.10:554/stream1`): all fields are filled in.
2. **Pick a brand and stream** from the catalog (main / sub stream, channel number). The catalog lives in
   `config/camera_presets.yaml`; edit it to add brands, or define `camera_presets:` in a customer file to replace it.
3. **Type any custom path**; suggestions appear as you type.
4. **Find stream path automatically**: the server tries every known path on your camera and lists the ones that work.
5. **Save as template** to reuse your own path/port/transport for the next camera.

Then **Test connection**, and **Live view** shows the stream with face recognition.

## People, access rules and security
Registration collects the name, **phone**, person type, **{unit label}** (apartment, room, house...), an access period and
extra details (email, emergency contact, vehicle plate, ID number...), and generates an **ID** automatically.
After recognition the app decides **granted or denied** by type, status, dates and hours, and flags watch-list people.
Everything is configured per customer in `config/customers/<name>.yaml`: `site` (unit label, units, ID prefix),
`person_types`, `access` (days and hours), `person_fields`, `security` (lockout, password length).
See `docs/SECURITY.md` for the full list of protections and the known limits.

Create the first administrator: `python main.py --customer example create-user admin --role admin`
(more users can be added in the app under **Users**).

## Watch list and alerts
**People > Register** with person type *Criminal / wanted* (or *Banned*): enter the reason, source, optional case number,
instructions and review date, and **upload photo files**. A detection opens an alert that stays on every screen with a
siren until it is acknowledged; residents (role `resident`) see a short warning with the photo and no personal details.
Telegram / webhook notifications are optional. Read `docs/SECURITY.md` (watch list, false matches, legal notes) first.
