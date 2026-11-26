# Run Solavis on your machine (copy and paste)

All commands run from the repository folder:

```bash
cd /Users/eithan/Documents/priv/cv-playground/projects/recognition/face/entry-guard-compact
```

## 1. One-time setup

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python -m solavis.manage check-config
```

## 2. Start the demo (use 2 terminals, both in the folder above)

Terminal 1, the cloud:
```bash
venv/bin/python -m solavis.manage seed --package demo
venv/bin/python -m solavis.manage run
```

Terminal 2, the virtual camera:
```bash
venv/bin/python -m solavis.sim --package demo
```

| What | Address |
|---|---|
| Customer app (devices and ticket support) | http://127.0.0.1:8100 |
| Solavis ERP (our company's console) | http://127.0.0.1:8100/erp  (also `/admin`) |
| Camera simulator | http://127.0.0.1:8101 |

**Customer app logins** (password `demo1234`): `owner@demo.vn` (full control), `family@demo.vn` (view only), `other@demo.vn` (second customer, overdue invoice), `pho@demo.vn` (trial, no device yet).

**ERP logins** (password `demo1234`). Each person sees and can do only what their department and role allow:

| Account | Who | Notes |
|---|---|---|
| `president@solavis.vn` | President (super admin) | Password **and live face check**. First sign-in: enrol your face with the code `DEMO-FACE-2026` (demo only). Needs a webcam. |
| `sales.head@` `support.head@` `finance.head@` `ops.head@` `eng.head@` `compliance.head@` `people.head@` `@solavis.vn` | Department heads | Hold their department's full ceiling; manage their own people's roles and rights |
| `sales@` `support@` `finance@` `tech@` `@solavis.vn` | Staff | Hold one role from their department |

Stop a server: press `Ctrl+C` in its terminal.

## 3. What to try

**Customer app** (`owner@demo.vn`): Dashboard, Devices, Alerts, Visitors (confirm/dismiss), People (add with consent), Reports (charts), Activity log, Support (open a ticket), Billing (plan, invoices, how to pay), Team, Settings.

**ERP** (start as `president@solavis.vn`):
1. Sign in with the password, then enrol your face (code `DEMO-FACE-2026`; turn your head when asked). Next time it is password + face. Every attempt, with the captured frame, is in Security.
2. Dashboard, Customers, Billing, Support, Inventory, Tasks as before. The President sees everything.
3. **Organization:** 8 departments, each with a head, roles and a **ceiling** (the most anyone there can hold). Open one: add people, create roles, edit a person's rights (role + extra rights - withheld rights). Only the President changes ceilings, appoints heads and moves people; these need a fresh face check (a camera dialog pops up).
4. Sign out and sign in as `sales.head@solavis.vn`: you can manage only the Sales team, and cannot grant anything outside Sales' ceiling. Then `sales@solavis.vn`: a plain member sees only what the role allows.
5. **Access review** (President, DPO): who holds what, with CSV export. **Security** (President, DPO): tamper-evident log with integrity check, sessions, face re-enrolment.

**Camera story** (simulator on 8101 + customer app):
1. Simulator: **Claim camera**. 2. Customer app, Devices: **Arm here**. 3. Simulator: click a face (visitor shows in the app).
4. Simulator: **Turn 40°**. The camera locks and a critical alert appears. 5. Devices: **Unlock…**, then **Arm now**.
6. ERP, Customers, Demo Home: set the stage to **Suspended**. The next visitor is refused.

## Look and feel

All screens follow the Solavis design system (`.claude/rules/solavis-ui-design.md`, copied from `docs/style-ui.md`). Tokens live in `solavis/web/assets/solavis-tokens.css`; components in `app.css`. Dark mode follows your OS, or use the sun/moon button in the top bar.

## 4. Reset to a clean demo

**After updating to the department/President model you must reset** (old staff accounts have no department): stop the servers, `rm -rf data/solavis`, then seed again.

Stop both servers first, then:
```bash
venv/bin/python -m solavis.manage reset --yes
venv/bin/python -m solavis.manage seed --package demo
```
(If reset fails after code updates, delete the data folder: `rm -rf data/solavis`, then seed.) New columns are added to an existing database automatically; this is only a stop-gap until real migrations.

## 5. Useful commands

```bash
venv/bin/python -m pytest tests/test_solavis.py -q                 # run the tests
venv/bin/python -m solavis.manage create-staff you@company.com --department executive --president   # a President (prints a face enrollment code)
venv/bin/python -m solavis.manage create-staff boss@company.com --department sales --head          # a department head
venv/bin/python -m solavis.manage init-db                          # create tables only, no demo data
venv/bin/python -m solavis.manage seed --package production        # first admin only (needs env, see below)
```

Production bootstrap (creates only the President, prints a one-time face-enrollment code) needs these set first:
```bash
export SOLAVIS_ADMIN_EMAIL=you@company.com
export SOLAVIS_ADMIN_PASSWORD='ChooseAStrong1Password'
```

## 6. Change settings

Edit the files in `solavis/config/` (server, database, storage, security, notifications, recognition, tamper, tenancy, plans), then restart the cloud.
Your own copy of the folder: `export SOLAVIS_CONFIG_DIR=/path/to/my-config` (missing files fall back to the defaults).

Switch database (edit `solavis/config/database.yaml`):
```yaml
driver: postgresql      # or mysql, or sqlite
```
then `venv/bin/pip install -r requirements-prod.txt` and set `DB_HOST DB_USER DB_PASSWORD DB_NAME`.

Turn on Telegram alerts:
```bash
export SOLAVIS_TG_TOKEN='<bot token>'
```
and set `telegram.enabled: true` in `solavis/config/notifications.yaml`. Each customer pastes their chat id in the app (Settings).

## 7. Docker (production style)

```bash
cp .env.example .env          # fill in the values
docker compose up -d
docker compose exec solavis python -m solavis.manage seed --package production
```

## 8. Problems

| Problem | Fix |
|---|---|
| `Address already in use` | `lsof -i :8100` then `kill <pid>` (or `:8101` for the simulator) |
| `no such column` after updating the code | stop servers, `rm -rf data/solavis`, seed again (no migrations yet) |
| Visitor face "not found" | use clear front-facing photos; change `simulator.visitors` in `solavis/config/packages/demo.yaml` |
| No "Stranger" in the simulator | put a photo in `solavis/demo_faces/stranger/` and reload |
| `Config error ...` at start | the message names the file and key; fix that YAML line |
| Locked out of login | 5 wrong passwords block for 5 minutes; restart the server to clear |
