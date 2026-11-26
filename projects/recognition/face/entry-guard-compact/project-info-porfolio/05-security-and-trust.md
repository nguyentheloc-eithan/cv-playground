# Security and trust design

## Threat thinking (camera)
| Threat | Defence |
|---|---|
| Camera turned/moved/stolen | 5 sensing layers (hardware doc), auto lock, critical alert, photo |
| Cover opened | reed + magnet, immediate /tamper |
| Firmware modified to keep uploading | server checks subscription, state and limits per request |
| Stolen camera leaks data | camera holds no faces and no storage keys; device key stored hashed server-side and revocable |
| Replay / retry over 4G | idempotency key per event |
| Lens spray/cover | histogram correlation vs armed baseline |
| Power/network cut | missed check-in alert |
| False alarms | thresholds in config, service window (15 min) for owner maintenance, 2-week outdoor false-alarm test planned |

## Threat thinking (company back office)
- **President** signs in with password **and live face**; 60-minute sessions; sensitive actions need a face check newer than 10 minutes (HTTP 428 flow).
- **Tamper-evident log:** each `security_log` record hash covers the previous one; `verify_chain` detects edits, deletions, reordering; face frames stored with retention (90 d). Every mutating President request is logged by middleware.
- **Delegated rights (dynamic RBAC):** President sets a department **ceiling**; a head creates roles and grants within it; effective = (role ∪ extra − denied) ∩ ceiling; heads cannot grant outside the ceiling or to another head. 15 permissions across 8 modules.
- Sessions: hashed tokens, idle timeout for staff, optional IP allowlist, list and revoke.
- Login lockout (5 failures / 5 min customers; 3 / 15 min face).
- Customer-data separation tested; staff cannot act on other staff via customer-user endpoints.
- Access review page: who holds what, CSV export.

## Privacy by design
Consent record per registered person; watch-list needs human review and uses "possible match" wording; deletion erases data; retention windows; minimal storage (crop only); data export and delete for owners.

## Honest gaps
Printed-photo/replay attack only partly covered; log chain assumes one writer (guarded on PostgreSQL); no two-person approval workflow; face required only for the President.
