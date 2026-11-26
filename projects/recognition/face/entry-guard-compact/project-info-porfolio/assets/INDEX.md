# Captured assets (ready to use)

All images are real captures from the running Solavis demo (local, seeded demo data) or renders of the real 3D model. PNG, 1440 × 900 unless noted. Light and dark pairs share a number.

## 3d/ (renders of `3d-model/solavis-camera.glb`, 1948 × 1088)
| File | Shows | Use for |
|---|---|---|
| `3d-hero.png` | Assembled camera, 3/4 view, clean | Hero image, OpenGraph card, project card |
| `3d-hero-annotated.png` | Same with the "+" hotspots (camera, PIR, light, solar) | How-it-works section |
| `3d-front.png` / `3d-top.png` / `3d-back.png` | Orthogonal-style views | Gallery |
| `3d-exploded.png` | X-ray exploded view: solar panel, cover (translucent), board, battery, optics, back plate | Hardware section (best single image) |
| `3d-exploded-optics.png` | Only optics highlighted | Lens, glass, hood detail |
| `3d-exploded-electronics.png` | Only electronics highlighted | Board, ESP32, LTE, antenna |
| `3d-graphite.png` | Graphite finish | Colour option |
| `3d-on-gate-post.png` | Mounted on a gate post | Context / "where it lives" |
Note: the renders carry a small caption "Design render, not yet built". Keep it.

## customer-app/ (owner@demo.vn, camera locked after a tamper test, 7 visitor events)
`01-dashboard`, `02-devices` (state locked, reason turned), `03-alerts`, `04-visitors`, `05-people`, `06-reports`, `07-activity`, `08-support`, `09-billing`, `10-team`, `11-settings`, each `-light` and `-dark`.
Best for the page: `01-dashboard-*`, `02-devices-light`, `03-alerts-*`, `04-visitors-*`.

## erp/ (President session with live face verification on; demo data)
`01-dashboard`, `02-customers`, `03-billing`, `04-support`, `05-inventory`, `06-tasks`, `07-organization` (8 departments), `08-access` (access review), `09-security` (hash-chained log with face-check frames, "Face requirement On"), `10-audit`, `11-system`, each `-light` and `-dark`.
Also `12-sales-head-dashboard-light` and `13-sales-head-organization-light`: a Head of Sales sees only the business their department allows.
Best for the page: `09-security-light` (the security story), `07-organization-light`, `12-sales-head-dashboard-light` (scoped rights).

## simulator/
`01-camera-simulator-dark.png`: the virtual camera (claim, physical-world buttons, visitor faces, camera log).

## evidence/
`tests-157-passed.png`: pytest run, 157 passed in 26.85 s across 4 test files (rendered from the real output).

## Privacy: read before publishing
- The visitor, People and Security screenshots show **face crops from the sample photos in `data/photos/` (two real people)**. They are the demo's test faces. Publish only if both people consented. Otherwise replace those sample photos with stock or synthetic faces and re-capture, or blur the crops in the page.
- Emails shown are demo accounts (`@demo.vn`, `@solavis.vn`). No real customer data. Demo password is not visible in any image.
- Figures such as "298.000 ₫" MRR are seeded sample data, not revenue. Do not present them as real. Plan prices in the YAML are samples (kept private per the ledger): crop or avoid `09-billing-*` and `02-customers-*` if you do not want sample prices public.
