# Prompt: add the Solavis desktop and mobile apps plan to my portfolio

Copy everything below into the AI agent that works in my Next.js portfolio.

---

## Context
You already built the individual Solavis page from the pack `project-info-porfolio/`. Re-read the pack first: `README.md`, `00-truth-ledger.md` (updated), `04-architecture.md`, `05-security-and-trust.md` and the new `11-clients-plan.md`. I am planning **customer apps**: a **desktop app** and a **mobile app**, released **Windows + Android first, then macOS + iOS**. The backend foundation is built and tested. The apps are **not started**; only the folder structure `clients/` exists, with README placeholders and no app code.

## Task
Update the existing Solavis page and content so it presents the **client apps plan** convincingly and honestly. Do not redesign the site. Smallest changes that fit my components, styling, i18n (EN and VI) and content file.

## Rules
1. Obey the truth ledger. Say **"planned"** for every app. No app screenshots, store badges, download links, release dates, user numbers or "available on". Mockups only if labelled "concept".
2. State as **built** only: `/api/v1` alias, public app-config force-update gate (now also per platform: windows, macos, android, ios), 30-day sliding phone sessions, push token endpoints with Expo delivery (off by default, not tested against Expo itself), signed picture links, cursor paging, OpenAPI export (80 paths), 165 passing tests, and the scaffolded `clients/` workspace (folders and READMEs only). Everything else is **planned**.
3. No invented dates, costs, versions or store-policy claims. Where store rules matter (in-app purchase, signing, notarisation), say "to be checked", as in the plan.
4. The stack in the plan (Expo for mobile, Tauri 2 for desktop, shared TypeScript packages) is a **recommendation**; write it as "chosen direction", with Flutter and Electron named as fallbacks.
5. Add no new dependency unless I approve. Reuse existing 3D, diagram and table components.

## Deliverables
1. **A "Desktop and mobile apps (planned)" section** after "Cloud and subscription" and before "Security":
   - One-paragraph intent: owners watch gates from a Windows PC tray and an Android phone, get tamper and visitor alerts, review visitors, control cameras and open tickets; the ERP stays web-only.
   - **Release order strip**: Wave 1 Windows + Android, Wave 2 macOS + iOS, each chip "planned", with a one-line reason per wave (from the plan).
   - **Readiness strip**: "Backend foundation built" (rule 2 list) versus "Apps planned".
   - **Architecture diagram** (SVG in the site theme, with title and description): Windows/macOS desktop (Tauri) and Android/iOS mobile (Expo) → shared packages (`api-client` generated from OpenAPI, `core`, `ui-tokens`, `i18n`) → `/api/v1` → Solavis cloud → alerts → Expo push to phones and a live stream or polling to the desktop tray.
   - **Monorepo file tree** from the plan (`solavis/`, `clients/apps/{mobile,desktop}`, `clients/packages/*`, `docs/api/openapi.json`, `firmware/`, `hardware/`) and one sentence on why `clients/` is a separate JavaScript workspace from the Python backend.
   - **Feature matrix** mobile vs desktop (the table in the plan), each cell "planned".
   - **Milestones** C0, M1, D1, M2, D2, M3/D3, W2 as status chips without dates (C0 partly done: contract export and folder scaffold).
   - **Risks and backend gaps** list A to G from the plan (link camera by claim code, account deletion, notification preferences, desktop live stream, error codes, store payment policy, shared rate limit), plus the release and trust work (Windows signing, Play data-safety, notarisation, Apple review).
   - **Contract rules** (4 bullets).
2. **Update existing sections** that mention apps or "web app" (hero pitch, architecture diagram: add desktop and phone clients, honesty box: "Desktop and mobile apps: planned" under not done and "Client-ready backend" under built, roadmap).
3. **Content and i18n:** put all new text in the typed content file(s), EN with VI mirrored. Update the card and CV summary with one sentence: "Windows and Android apps (then macOS and iOS) planned on a versioned, mobile-ready API."
4. **Optional small interactive piece:** "Sessions" explainer: web vs phone login and session length (8 hours vs 30 days sliding), staff always on the short web session. Pure TypeScript logic with a unit test, labelled "documented behaviour".
5. **Quality:** AA accessible, responsive to 390 px, reduced motion respected, dark and light, no console errors. Run lint, type-check, tests and build; fix what you break.

## Ask me only if blocked
Whether I want Flutter instead of Expo and Tauri (default: Expo + Tauri) and whether to show concept mockups (default: no).

## Final report
Files changed, claims you softened, anything unclear, how to run and test. Never run git commit, push or stage.
