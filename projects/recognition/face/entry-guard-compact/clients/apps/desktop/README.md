# apps/desktop
Tauri 2 + the same TypeScript UI stack. Windows first (MSIX/NSIS installer, signed), macOS later (notarised DMG).
- `src/` web UI (reuses `packages/core`, `ui-tokens`, `i18n`)
- `src/tray/` tray icon, unread count, quick arm/disarm
- `src/platform/` Windows vs macOS differences (notifications, autostart, updater)
- `src-tauri/` Rust shell: tray, native notifications, autostart, updater, single-instance, token in OS credential store
Not created yet: run `pnpm create tauri-app` here when milestone D1 starts.
