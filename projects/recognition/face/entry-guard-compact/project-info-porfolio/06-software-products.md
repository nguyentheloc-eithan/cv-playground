# Software products

## Customer app (`/`)
Dashboard, Devices (claim, arm, unlock with service window, state, battery, signal), Alerts, Visitors (review: confirm/dismiss), People (consent), Reports (charts), Activity log, Support tickets, Billing (plan, invoices, how to pay), Team, Settings (Telegram chat id). Roles: owner (full), member (view).

## Solavis ERP (`/erp`, alias `/admin`)
| Module | What |
|---|---|
| Customers (CRM) | tenants, stages (trial, active, past due, suspended), notes, device list, remote revoke |
| Billing | plans, invoices, manual payment recording, bank QR option |
| Support | tickets with assignment restricted to people who can work tickets |
| Inventory | unit stock, claim codes, RMA |
| Tasks | scoped: President all, head their department, staff themselves |
| Organisation | 8 departments (Executive, Sales, Support, Finance, Operations, Engineering, Compliance, People), heads, roles, ceilings, people |
| Access review | who holds which rights, CSV |
| Security | integrity check of the log, face re-enrolment, sessions, frame viewer |
| Dashboard | permission-aware: each block appears only if the person holds the matching right; head sees a "My team" panel |

## Camera simulator
Separate app standing in for hardware: claim, heartbeat, visitor faces, tilt, turn 40° (triggers lock). Lets the whole cloud be demonstrated without a board.

## UI engineering
Own design system (tokens, light/dark, Inter self-hosted, Solavis Gold accent), collapsible icon-rail sidebar, own inline icon set (no downloads), focus-trapped modals, keyboard-operable, responsive down to 390 px, headless-Chrome checks for each role.

## Quality
157 automated tests (API, tenancy, tamper, subscription, delegation, face auth with real photos, security-log tamper detection, permission scoping). UI verified with headless Chrome driven over CDP, including a fake camera device for the face dialog.

## Demo story (60 seconds, good for video)
1. Simulator: claim camera. 2. Customer app: arm. 3. Click a face: visitor appears. 4. Turn 40°: camera locks, critical alert. 5. Unlock, re-arm. 6. ERP: suspend the customer; next visitor refused. 7. President face login and the security log.
