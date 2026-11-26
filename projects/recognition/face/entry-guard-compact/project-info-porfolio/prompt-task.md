# prompt-task.md: orders for the AI agent (REVISION 2)

You already built a first version of the Solavis page from revision 1 of this pack. **This is revision 2.** Re-read the whole folder, then do the work below. Do not redo what already works: audit it, then fix and extend.

## What changed in revision 2
1. `assets/` now holds real screenshots (customer app, ERP, simulator, tests) and 3D renders. See `assets/INDEX.md`.
2. `3d-model/` holds a presentation 3D model of the camera (`solavis-camera.glb`, 26 named parts) and its generator. A first interactive viewer already exists in the portfolio (`src/components/pages/solavis/demos/EnclosureViewer.tsx` and `ProductScene.tsx`, using `three`, `@react-three/fiber`, `@react-three/drei`, model at `public/models/solavis-camera.glb`, parts and exploded offsets in `src/content/solavis-camera.manifest.json`). Audit and polish it.
3. `questions-for-owner.md` now gives defaults for every open item. **No `[TODO]` text may remain on the page.**
4. The truth ledger has new entries (3D model, viewer, screenshots). Obey it.

## Rev 2 tasks (do these first, in order)

### R1. Audit the existing page
List what exists: components, demos, content file, routes, tests. Run lint, type-check, tests, build. Report failures and fix them. Check the page against `00-truth-ledger.md`: remove or soften any claim outside it.

### R2. Remove every TODO
Search the whole source for `[TODO`. Replace each with the default from `questions-for-owner.md` (role, dates, repo text, video poster, contact reuse, experience section built only from existing portfolio content). Keep placeholders only where the owner must decide (face-photo privacy), and show a neutral fallback instead of visible TODO text.

### R3. Wire the screenshots
Copy the chosen images from `assets/` into the portfolio under `public/images/solavis/` (keep names), optimise with the existing image pipeline (`next/image`, width/height set, `priority` only for the hero). Replace the screenshot placeholder component with a gallery: tabs "Customer app", "ERP", "Camera simulator"; light/dark pair switcher that follows the site theme by default; lightbox with keyboard support and captions from `assets/INDEX.md`; alt text describing the screen. Add the tests image in the proof area. **Privacy:** images show face crops from demo sample photos. Until the owner confirms consent, wrap the visitor/people/security images in a "Show demo faces" toggle that is off by default (CSS blur of the crops is not enough; show the dashboard/devices/organization/sales-head images by default and gate the others), and mention it in the report.

### R4. Make the hardware section impressive (the owner said the old one was not)
Order: (1) full-width 3D hero (interactive, lazy, with `assets/3d/3d-hero.png` as poster so there is no empty box), (2) one-line spec strip (125 × 90 × 79 mm design, 6 V 1.5 W panel, 18650 about 11 Wh, ESP32-S3 + LTE, estimated 0.5 to 0.8 Wh/day), (3) exploded x-ray with a "layers" stepper that explains each group in order: solar, shell, optics, sensors, electronics, power, back plate, (4) power-chain diagram and power explorer, (5) tamper simulator, (6) parts table. Keep the "Design render, not yet built" caption inside the 3D area.
Viewer polish checklist: poster image while loading; `prefers-reduced-motion` respected; works with touch (pinch/drag); no page-scroll hijack on wheel (require a click or two-finger gesture to zoom on mobile); keyboard-operable controls with visible focus; pause rendering when off-screen; dispose geometries on unmount; fallback to `3d-exploded.png` if WebGL is missing; dark and light theme backgrounds; no console errors (React 19 dev-mode warning about "unmount a root" from the 3D canvas should be investigated and removed if it is ours).
Optional upgrades if time allows: camera "fly-to" when a hotspot opens; part labels with leader lines in exploded mode; a "tour" button that steps through the views; subtle idle motion only when not reduced-motion; compress the GLB with `gltf-transform` meshopt (ask before adding a dev dependency); a second material variant.

### R5. Use the new copy
Update the page text from `08-copy-deck.md` and the updated `03-hardware-embedded.md` (new "3D product model" paragraph). Hero image: `assets/3d/3d-hero.png`. OpenGraph image: generated from `3d-exploded.png` or `3d-hero.png`.

### R6. Final report
Files changed, defaults applied, claims you softened, privacy decisions made, anything still blocked (only face-photo consent), how to run, test, build.

## Global rules (apply to every task)
1. Read `README.md`, then `00-truth-ledger.md`. Claim only what the ledger allows. No invented numbers, customers, accuracy, awards, links. Label estimates "estimated" or "target". The 3D model is a "design render", never a prototype or photo.
2. Do not publish anything under "Private" in the ledger.
3. Follow the portfolio's conventions. Smallest changes that fit. Do not redesign the site.
4. Ask only about item 11 in `questions-for-owner.md`; use defaults for the rest.
5. Dependencies already added for 3D: `three`, `@react-three/fiber`, `@react-three/drei`, `@types/three`. Add nothing else without asking.
6. Never run git commit, push or stage. Leave changes in the working tree.
7. Accessibility AA, responsive to 390 px, reduced-motion respected, dark/light follows the site.

---

# Original task list (revision 1): verify, do not redo

## Task 0: Recon (do first, no code)
Report: framework version, router type, styling (Tailwind/CSS modules), content system (MDX/TS data/CMS), existing project page structure, chart/3D/animation libs present, image handling, how diagrams are done. Propose the file plan for the Solavis page. Wait for my OK if the plan touches shared layout.

## Task 1: The individual page (core)
Build `/projects/solavis` (match my route pattern) following `09-page-spec-nextjs.md`, using text from `01` to `08` and `08-copy-deck.md`. Put content in a typed data file or MDX so copy edits need no component changes. Include the visible **honesty box** (built / designed / not done) from the ledger. Add the project card to my projects grid and a CV-ready summary block. Acceptance: builds, lints, type-checks; Lighthouse accessibility >= 95; no horizontal scroll at 390 px; no claim outside the ledger.

## Task 2: Interactive "Try to tamper" simulator (hardware showcase)
A client component. A small camera illustration at a gate. Buttons: Tilt, Turn, Open cover, Cover lens, Cut network, Wave hand (PIR), Normal visitor. State machine as in `diagrams/tamper-states.mmd` (unclaimed, mounting, armed, locked, service). Each action lights the sensor layer that catches it and shows: sensor, threshold (tilt > 8°, heading change > 15°, histogram correlation < 0.55, 3 missed check-ins, reed open), what it can miss, and the resulting alert. A sidebar shows a live event log. "Unlock (service window)" and "Re-arm". Pure TypeScript logic in a separate module with unit tests (thresholds from `03` and `05`). Keyboard operable; text alternative for the illustration; no heavy library (SVG + CSS).

## Task 3: Recognition threshold demo (AI showcase)
Client component: a synthetic score distribution (clearly labelled "illustrative, not measured data") for genuine vs impostor comparisons with a draggable accept and reject threshold (defaults 0.363 and 0.30). Show the three zones (known, uncertain, unknown), and how false-accept vs false-reject trade off. Add the pipeline strip (capture, YuNet detect, SFace 128-d embedding, cosine match, decision) and the watch-list rule ("possible" vs "likely", human review always). Label every number. Do not present any accuracy figure.

## Task 4: Security visuals
(a) President face-login flow animation from `diagrams/president-auth.mmd`. (b) Delegation visual: President sets department ceiling, head creates roles within it, staff gets role + extras - denials, intersect ceiling; interactive: toggle a right and watch it be blocked above the ceiling. (c) Hash-chain visual: 6 linked blocks, a "edit a record" button breaks every following block and shows "integrity check failed". Implement the hash with Web Crypto SHA-256 on the client; label it a demonstration.

## Task 5: Power budget explorer (hardware showcase)
Client component with inputs: check-ins per day, events per day, network mode (Wi-Fi / 4G), sleep current (mA), panel yield (good light / winter). Compute daily energy using the model in `03-hardware-embedded.md` (document formulas in code comments), show a stacked bar, panel yield line, and days of autonomy for an 11 Wh cell. Defaults reproduce about 0.5 Wh (Wi-Fi) and 0.8 Wh (4G). Banner: "Estimates from datasheet values. Not measured." Add unit tests for the calculation.

## Task 6: 3D enclosure viewer (DONE in rev 2: see R4)
Display the enclosure. Preferred: render the STL files (`hardware/enclosure/cover.stl`, `backplate.stl`, `lens_hood.stl`, copy into `public/` after I approve) with react-three-fiber (ask before adding the dependency), orbit controls, exploded-view toggle, lazy-loaded behind a "Load 3D view" button on mobile. Fallback if no 3D library: 6 pre-rendered images in a gallery. Caption: "Design, not yet printed." Also show the parameter block idea ("one number changes the whole box") with a small code excerpt.

## Task 7: Diagrams
Render the four Mermaid files in `diagrams/` to SVG at build time (or inline React SVG matching my site's theme). Dark/light aware, with `<title>` and `<desc>` text alternatives. Architecture diagram nodes get hover descriptions.

## Task 8: Screenshots and demo video slots
Create a gallery component with light/dark paired screenshots, lightbox, captions. Use placeholders until I supply files from `10-assets-checklist.md`. Add a video slot (poster + lazy iframe or `<video>`), no autoplay with sound.

## Task 9: "My experience" section (needs my input)
Ask me for my CV and related projects. Write a section linking Solavis skills (embedded power budgeting, computer vision, multi-tenant backend, security design, CAD scripting) to my real experience, and cross-link my other portfolio items. Never invent employers, dates or results. Output a draft and a list of questions.

## Task 10: SEO, metadata and polish
Title, description, OpenGraph image (generated from the hero), JSON-LD `CreativeWork`, sitemap entry, canonical URL, alt text, print-friendly summary. Performance budget: no layout shift, lazy-load heavy demos, LCP image prioritised.

## Task 11 (optional): Evidence panel
A "Proof" tab showing the repo structure tree, line counts (about 3,500 backend lines, 2,000 test lines, 157 tests passing), and short code excerpts (tamper evaluator, entitlement check, hash chain). Use excerpts I approve; no secrets.

## Final report format
1. Files changed/added. 2. Hard-coded values or claims you were unsure of. 3. Open questions. 4. Placeholders still to fill. 5. How to run, test and build.
