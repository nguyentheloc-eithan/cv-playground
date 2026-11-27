# Solavis portfolio pack, revision 2 (for my AI agent)

Self-employed project: **Solavis**, a solar-powered AI gate camera with a cloud subscription service.
Everything in this folder is source material. The agent writes the Next.js page from it.

## What is new in revision 2
- `assets/`: 58 real screenshots and renders (customer app, ERP, simulator, tests, 3D). Index and privacy notes: `assets/INDEX.md`.
- `3d-model/`: the presentation 3D model (`solavis-camera.glb`), its manifest and generator script.
- Truth ledger, hardware doc, page spec and checklist updated. Open questions now have defaults (no TODOs on the page).
- `prompt-task.md` starts with **Revision 2 tasks R1 to R6**; the revision 1 tasks remain below for verification.

## Read in this order
| # | File | Purpose |
|---|---|---|
| 0 | `00-truth-ledger.md` | **Read first.** What is built, tested, designed only, or not started. The page may claim only what is here. |
| 1 | `01-overview.md` | One-line pitch, problem, solution, product lines, role |
| 2 | `02-ai-computer-vision.md` | Face detection and recognition, thresholds, watch-list, face login, trade-offs |
| 3 | `03-hardware-embedded.md` | Parts, power budget, tamper sensors, enclosure, test plan |
| 4 | `04-architecture.md` | Device API, cloud, data model, multi-tenancy, subscription control |
| 5 | `05-security-and-trust.md` | Tamper state machine, device keys, hash-chained log, President face auth, delegated rights |
| 6 | `06-software-products.md` | Customer app, Solavis ERP, simulator, tests |
| 7 | `07-engineering-decisions.md` | Decisions and trade-offs (the "why") |
| 8 | `08-copy-deck.md` | Ready text: headline, pitch, card, CV paragraph, LinkedIn, bullets |
| 9 | `09-page-spec-nextjs.md` | Layout, sections, components, interactions for the individual page |
| 10 | `10-assets-checklist.md` | Screenshots and diagrams to capture or render |
| 10b | `11-clients-plan.md` | Desktop + mobile apps plan: Windows and Android first, then macOS and iOS; stack, folders, milestones, backend gaps, rules |
| 10c | `prompt-clients-plan.md` | **Prompt** to add that plan to the portfolio page |
| 11 | `questions-for-owner.md` | Gaps only I can fill (role, dates, links). Agent asks these before writing. |
| 12 | `prompt-task.md` | **The task prompts** for the complex work (page, diagrams, interactive demos) |
| - | `diagrams/*.mmd` | Mermaid sources (architecture, tamper states, power chain, auth flow) |
| - | `assets/` | Screenshots and renders, with `assets/INDEX.md` |
| - | `3d-model/` | `solavis-camera.glb`, manifest, generator, README |

## Rules for the agent
1. Read `00-truth-ledger.md` and obey it. No invented numbers, customers, accuracy, or sales.
2. Estimates are labelled "estimated" or "target". Measurements do not exist yet.
3. Keep private items out (see ledger, "Private").
4. Match my existing portfolio's style. Read its code first. Smallest changes that fit.
5. Where a fact is missing, ask. Do not guess.
