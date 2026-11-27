# apps/mobile
Expo + TypeScript, expo-router. Android first (Play internal testing), iOS after the Android release is stable.
- `app/` screens (file-based routes)
- `src/features/*` one folder per product area
- `src/push/` Expo push registration, deep links from `data.alert_id`
- `src/auth/` login with `client:"mobile"`, token in SecureStore, local biometric unlock
- `src/platform/` anything that differs between Android and iOS (keep iOS differences here so the Android release is not blocked)
Not created yet: run `pnpm create expo-app` in this folder when milestone M1 starts.
