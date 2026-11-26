# prompt-task.md: orders for the AI agent

You are working in my **Next.js portfolio** workspace. This folder (`project-info-porfolio/`) is the source material for a new individual page about my self-employed project **Solavis**. The page must focus on **AI and hardware**.

## Global rules (apply to every task)
1. Read `README.md`, then `00-truth-ledger.md`. Claim only what the ledger allows. No invented numbers, customers, accuracy, awards, links. Label estimates "estimated" or "target".
2. Do not publish anything under "Private" in the ledger.
3. First read my portfolio code: router (app/ or pages/), components, styling system, content format, existing project pages, installed libraries. Follow its conventions. Smallest changes that fit. Do not redesign the site.
4. Ask me the questions in `questions-for-owner.md` that block you (role, dates, links, my other experience). Do not guess. If I have not answered, use clearly marked placeholders `[TODO: ...]` and list them at the end.
5. Add no new dependency unless a task says so or you justify it in one line and I approve. Prefer build-time rendering over client JS.
6. Never run git commit, push or stage. Leave changes in the working tree.
7. Accessibility AA, responsive to 390 px, reduced-motion respected, dark/light follows the site.
8. When done with each task: list files changed, claims you were unsure about, and what I must provide.

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

## Task 6: 3D enclosure viewer
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
