# Solavis clients

One TypeScript workspace for every customer app. The backend contract is `../docs/api/openapi.json`; nothing here talks to the backend any other way.

| App | Tech | Order | Status |
|---|---|---|---|
| `apps/mobile` | Expo (React Native) | Android first, iOS later | planned, no code |
| `apps/desktop` | Tauri 2 (web UI + small Rust shell) | Windows first, macOS later | planned, no code |

Shared packages: `api-client` (generated), `core` (sign-in, stores, polling, formatting), `ui-tokens` (Solavis Gold, one source for CSS and React Native), `i18n` (EN and VI).

Plan, milestones and rules: `../docs/CLIENTS.md`. Staff and the President use the ERP on the web, never these apps.
