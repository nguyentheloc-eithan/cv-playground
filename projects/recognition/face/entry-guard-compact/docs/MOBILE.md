# Mobile app: architecture and backend readiness

> The full client plan (Windows desktop + Android first, then macOS + iOS) is `docs/CLIENTS.md`. The apps live in `clients/` (`clients/apps/mobile`). The `mobile/` folder in the layout below is now `clients/apps/mobile`.

Verdict: **the backend can support a mobile app now**, with the foundation added below. A few product features still need new endpoints (listed under "Still to build"). No folder restructuring of the backend is needed; add the app beside it.

## What was already mobile-friendly
JSON REST with OpenAPI; `Authorization: Bearer` tokens (login returns one); tenant isolation on every query; device API separate and versioned (`/device/v1`); alerts, events, people, devices, billing and tickets as plain endpoints; authenticated snapshot endpoint; audit log; start-up config validation; health and readiness probes.

## Added for mobile (tested, 164 tests pass)
| Need | What now exists |
|---|---|
| Stable contract for years of installed apps | `/api/v1/...` is an alias of `/api/...` (so a future `/api/v2` can differ). `python -m solavis.manage export-openapi` writes `docs/api/openapi.json` (80 paths) for client code generation |
| Force-update and maintenance | `GET /api/app-config?app_version=1.2.0&platform=ios` (public): `min_version`, `latest_version`, `update_required`, `maintenance`, `message`, store link, feature flags. Config: `server.yaml` `mobile:` |
| Stay signed in on a phone | `POST /api/auth/login {email, password, client:"mobile", device_name}` gives a **30-day sliding** session (`security.yaml` `session.mobile_days`); customers only, staff stay on the short web session. Sessions list and revoke already exist (`/api/auth/sessions`), so "sign out other devices" is free |
| Push notifications | Table `push_tokens`; `POST /api/push/register {token, platform, device_name}`, `POST /api/push/unregister`. Every alert is pushed to all tokens of that customer (critical = high priority, time-sensitive) through the Expo Push service. Config: `notifications.yaml` `push:` (off by default), env `SOLAVIS_EXPO_TOKEN` |
| Pictures in notifications and image views | `GET /api/snap-url/{name}` returns a signed link valid 15 min (`security.yaml` `snap_link_minutes`); `GET /s/<name>.<expiry>.<signature>` serves it without a login. Tamper-proof (HMAC), tested for forged, expired and cross-tenant use. Push payloads carry the link as `data.image` |
| Long lists | Cursor paging: `GET /api/events?limit=30&before=<smallest id you have>`, same for `/api/alerts` |

## Recommended folder layout (monorepo, add beside what exists)
```
entry-guard-compact/            (keep; rename the repo to "solavis" when convenient)
  solavis/                      backend + web (unchanged)
  docs/api/openapi.json         the contract (generated, commit it)
  docs/MOBILE.md                this file
  mobile/                       NEW: the app (Expo, React Native, TypeScript)
    app/                        screens (expo-router)
    src/api/                    typed client generated from docs/api/openapi.json (openapi-typescript)
    src/features/{devices,alerts,visitors,people,billing,support}/
    src/push/ src/auth/ src/theme/   (theme = Solavis tokens, gold accent)
  firmware/                     NEW later: ESP32-S3 C++ (uses /device/v1 only)
  hardware/                     enclosure, 3D model (exists)
  tests/                        backend tests; add contract tests that diff openapi.json
```
Why Expo: push (Expo Push is already wired), QR scanner for claim, Face ID/biometrics, deep links and OTA updates with one TypeScript codebase for iOS and Android. Flutter would also work: the backend contract is the same.

## App flows mapped to the API
- **Sign in:** login with `client:"mobile"`; store the token in Keychain/Keystore (expo-secure-store); unlock the app with Face ID locally (no backend change).
- **Home:** `/api/v1/overview`; poll on foreground, push for the rest.
- **Alerts:** push, then deep link to `/alerts/<id>`; picture via `data.image`; "Got it" = `POST /api/alerts/{id}/ack`.
- **Visitors:** `/api/events` (cursor), review = `POST /api/events/{id}/review`.
- **Camera control:** arm, unlock, service window, rename: existing endpoints.
- **People (consent), tickets, billing (read), team:** existing endpoints.
- **Admin on the road:** keep the ERP web-only (President face login needs the web flow); the app is for customers.

## Still to build (needed before store release)
1. **Add a camera from the phone.** Hardware spec says "claim from the app with the QR", but the customer API has no `POST /api/cameras/link {claim_code}` (today staff assign units to a customer). Needs: link an unclaimed unit to the caller's tenant, plan camera limit check, audit entry. Plus device onboarding on the firmware side (Wi-Fi setup by BLE or SoftAP).
2. **Account deletion** (`DELETE /api/me` or a request flow). App Store and Google Play require in-app deletion. Define what happens to the tenant when the owner deletes.
3. **Per-user notification preferences** (which alert levels, quiet hours) and cleanup of dead push tokens (Expo returns `DeviceNotRegistered`).
4. **Store payment policy.** Billing is manual today. Do not sell the subscription inside the app without checking Apple/Google rules (in-app purchase may be required for digital services). Safest first release: billing shown read-only with "manage on the web".
5. **Rate limits shared across servers** (login lockout is in memory) and refresh-token rotation if you want shorter-lived tokens than 30 days.
6. **Real-time view** (optional): push covers alerts. If you want a live status stream later, add Server-Sent Events on `/api/v1/stream`; the data model already supports it.
7. **Localisation** (EN/VI): error messages are English strings today; add error codes alongside messages so the app can translate.
8. **PostgreSQL run** and **Alembic migrations** before real users (already on the list in the main README).

## Contract rules for the API (so old apps keep working)
Never remove or rename a field in `/api/v1`; only add. Breaking change = new `/api/v2`. Keep `min_version` honest: raise it only when a server change would break older apps. Regenerate and commit `docs/api/openapi.json` with every API change; the app regenerates its client from it.
