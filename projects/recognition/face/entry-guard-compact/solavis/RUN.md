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
| Customer app | http://127.0.0.1:8100 |
| Admin console | http://127.0.0.1:8100/admin |
| Camera simulator | http://127.0.0.1:8101 |

Logins (password `demo1234` for all):

| Account | View | Use it for |
|---|---|---|
| `owner@demo.vn` | Customer app `/` | full control of the "Demo Home (Hanoi)" account |
| `family@demo.vn` | Customer app `/` | view only (cannot change cameras, people, billing) |
| `other@demo.vn` | Customer app `/` | second customer, overdue invoice (proves data stays separate) |
| `pho@demo.vn` | Customer app `/` | a trial customer with no device yet |
| `staff@solavis.vn` | Admin `/admin` | role **admin**: everything |
| `sales@solavis.vn` | Admin `/admin` | role **sales**: customers, notes, tasks; no billing changes |
| `support@solavis.vn` | Admin `/admin` | role **support**: tickets, inventory returns; cannot see invoices |
| `finance@solavis.vn` | Admin `/admin` | role **finance**: invoices and payments; cannot see tickets |

Stop a server: press `Ctrl+C` in its terminal.

## 3. What to try

**Customer app** (`owner@demo.vn`): Dashboard, Devices, Alerts, Visitors (confirm/dismiss), People (add with consent), Reports (charts), Activity log, Support (open a ticket), Billing (plan, invoices, how to pay), Team, Settings.

**Admin** (`staff@solavis.vn`):
1. Dashboard: MRR, pipeline, overdue invoices, trials ending, tasks, tickets.
2. Customers: filter by stage, open a customer (tabs: Overview, Billing, Support, Devices, Contacts & users, Notes & tasks, Activity).
3. Billing: create an invoice, "Mark paid" (an overdue or suspended customer becomes active).
4. Support: reply to the ticket; tick "Internal note" to see it stays hidden from the customer.
5. Inventory: assign a stock unit to a customer (creates a claim code), mark a unit returned/lost (needs a reason).
6. Staff: change a role; log in as `finance@` or `support@` to see the permission limits.

**Camera story** (simulator on 8101 + customer app):
1. Simulator: **Claim camera**. 2. Customer app, Devices: **Arm here**. 3. Simulator: click a face (visitor shows in the app).
4. Simulator: **Turn 40°**. The camera locks and a critical alert appears. 5. Devices: **Unlock…**, then **Arm now**.
6. Admin, Customers, Demo Home: set the stage to **Suspended**. The next visitor is refused.

## 4. Reset to a clean demo

Stop both servers first, then:
```bash
venv/bin/python -m solavis.manage reset --yes
venv/bin/python -m solavis.manage seed --package demo
```
(If reset fails after code updates, delete the data folder: `rm -rf data/solavis`, then seed.) New columns are added to an existing database automatically; this is only a stop-gap until real migrations.

## 5. Useful commands

```bash
venv/bin/python -m pytest tests/test_solavis.py -q                 # run the tests
venv/bin/python -m solavis.manage create-staff you@company.com     # add an admin
venv/bin/python -m solavis.manage init-db                          # create tables only, no demo data
venv/bin/python -m solavis.manage seed --package production        # first admin only (needs env, see below)
```

Production bootstrap needs these set first:
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
