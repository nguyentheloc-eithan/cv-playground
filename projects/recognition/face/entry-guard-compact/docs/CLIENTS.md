# Client apps plan: desktop and mobile

Status: **planned**. Only the backend foundation exists (see `MOBILE.md`). The folder structure is scaffolded in `clients/` with README placeholders and no app code.

## Release order
| Wave | Platform | App | Why this order |
|---|---|---|---|
| 1 | Windows | Desktop (Tauri 2) | Gate and shop owners watch the camera from a PC; no store review, installer can ship fast |
| 1 | Android | Mobile (Expo) | Biggest phone share in the target market; Play internal testing is quick; push works through Expo/FCM |
| 2 | macOS | Desktop (same code) | Needs notarisation and an Apple Developer account |
| 2 | iOS | Mobile (same code) | Needs Apple review, APNs key, in-app account deletion and a payment-policy decision |

Rule: nothing in wave 1 may use an API that exists only on Apple. Platform differences live in `src/platform/` so wave 2 is porting, not rewriting.

## Stack decision (recommendation)
- **Mobile: Expo (React Native) + TypeScript.** Push, QR scan, biometrics, deep links and OTA updates are ready; the same code builds iOS later.
- **Desktop: Tauri 2 + the same TypeScript UI.** About 10 MB installers, native tray, notifications, autostart and updater, and one codebase for Windows and macOS. Electron is the fallback if a Tauri plugin blocks a feature (heavier, about 100 MB).
- **Shared packages** (`clients/packages`): `api-client` (generated from OpenAPI), `core` (platform-free logic), `ui-tokens` (Solavis Gold), `i18n` (EN, VI). Roughly 60% of the logic is shared; screens are written per app.
- Flutter would cover all four platforms with one UI codebase and is the alternative if you prefer one UI toolkit over sharing TypeScript. The backend contract is identical either way.

## Folder structure (created)
```
clients/
  README.md  package.json  pnpm-workspace.yaml  .gitignore
  apps/
    mobile/                    Expo app (Android first, iOS later)
      app/                     screens, file-based routes
      src/features/{devices,alerts,visitors,people,billing,support}/
      src/{push,auth,platform}/
    desktop/                   Tauri 2 app (Windows first, macOS later)
      src/{features,tray,platform}/
      src-tauri/{src,icons}/   Rust shell
  packages/
    api-client/                generated from docs/api/openapi.json
    core/                      session, app-config gate, paging, view models (no UI imports)
    ui-tokens/                 tokens -> CSS + TS
    i18n/                      en.json, vi.json
  tools/                       release helpers
docs/api/openapi.json          the contract
docs/CLIENTS.md  docs/MOBILE.md
```

## What each app does
| Feature | Mobile | Desktop |
|---|---|---|
| Sign in (`client:"mobile"` 30-day session; desktop uses the same flag with `device_name`) | yes, token in SecureStore, Face ID / fingerprint unlock | yes, token in OS credential store (Windows Credential Manager / Keychain) |
| Alerts with picture and "Got it" | push, deep link to the alert | native toast while running, tray badge |
| Visitors, review, people (consent) | yes | yes, wider table layout |
| Arm, unlock, service window, rename | yes | yes, plus tray quick actions |
| Tickets, team, billing (read only) | yes | yes |
| Add camera by QR claim code | yes (needs new endpoint) | enter the code by hand |
| Keep running in background | OS push | tray + autostart; background connection (see gap D) |
| Update | store + `/api/app-config` force-update gate | Tauri updater (signed) + the same gate |

ERP, staff tools and President face login stay on the web.

## Milestones (no dates)
| ID | Milestone | Exit check |
|---|---|---|
| C0 | Workspace and contract: `clients/` set up, `api-client` generated, `core` with login and app-config gate, tokens generated, CI typecheck | `pnpm gen:api && pnpm typecheck` green, generated client matches the committed OpenAPI |
| M1 | Android alpha: sign in, home, alerts, push registration | Alert on a test device within 5 s of being raised |
| D1 | Windows alpha: sign in, home, alerts, tray, native notification | Works from an unsigned build on a clean Windows 11 VM |
| M2 | Android beta: visitors, people, camera control, tickets, add camera, account deletion | Play internal testing track |
| D2 | Windows beta: same feature set as M2, signed installer, auto-update | Update from n-1 to n works, SmartScreen shows the publisher |
| M3 / D3 | Wave 1 release | Play closed testing then production; Windows installer on the site |
| W2 | macOS build (notarised) and iOS build (TestFlight) | Same API contract tests pass; APNs push delivered |

## Backend work this plan needs
Done now: `/api/v1`, force-update gate, 30-day sessions, push tokens, signed picture links, cursor paging, OpenAPI export. Added today: `app-config` and push register accept `windows` and `macos`; `windows_url`, `macos_url` and per-app `min_version_by_platform` in `server.yaml`.

Still to build, in priority order:
1. **A. Link a camera by claim code** (`POST /api/cameras/link`): tenant, plan limit, audit.
2. **B. Account deletion** (`DELETE /api/me` or request flow): required by Google Play and the App Store.
3. **C. Notification preferences and dead-token cleanup.**
4. **D. Live stream for desktop** (Server-Sent Events on `/api/v1/stream`): desktop has no OS push, so while the app runs in the tray it needs a long-lived connection. Fallback: poll `/api/overview` every 10 s.
5. **E. Error codes** next to messages, so apps translate EN and VI.
6. **F. Store payment policy** (Apple and Google): ship billing read-only first.
7. **G. Shared login rate limit** (database or Redis) and PostgreSQL plus Alembic.

## Release and trust work (not code)
- Windows: code-signing certificate or Azure Trusted Signing (unsigned installers trigger SmartScreen warnings). Auto-update keys kept offline.
- Android: Play Console account, upload key kept off the repo, data-safety form (camera pictures and faces count as sensitive).
- macOS: Developer ID and notarisation. iOS: Apple Developer Program, APNs key, App Review notes for the account-deletion flow.
- Privacy policy and consent text for face data, shared with the web app.

## Rules
- API changes only add fields in `/api/v1`; breaking change means `/api/v2`. Regenerate and commit `docs/api/openapi.json` with every API change.
- `packages/core` and `api-client` contain no UI or platform imports; tokens are never typed by hand.
- Secrets (keystores, signing certs, Expo token) never enter the repo.
- Portfolio claims follow `project-info-porfolio/00-truth-ledger.md`: planned means planned.
