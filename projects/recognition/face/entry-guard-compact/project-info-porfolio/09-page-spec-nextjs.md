# Individual project page spec (Next.js)

Route suggestion: `/projects/solavis` (match the portfolio's existing route pattern). Use the portfolio's own components, fonts and theme; do not import the Solavis app's design system. Optional: borrow the **Solavis Gold** accent (#D4A017) only for small highlights inside the page.

## Sections (in order)
1. **Hero:** title, status badge, pitch, 3 stats, hero visual (rendered enclosure or animated system diagram), links (repo `[LINK]`, demo video `[LINK]`).
2. **Problem and solution:** two columns, 4 problem bullets, 6 solution cards with icons.
3. **System diagram:** interactive architecture (camera, cloud, apps). Hover a node for 1-sentence detail. Source `diagrams/architecture.mmd`.
4. **AI and computer vision:** pipeline strip (capture, detect, embed, match, decide), decision table, threshold slider demo (see prompt-task Task 3), "what I would measure next".
5. **Hardware:** block diagram, parts table with "why", power-budget chart (stacked bars Wi-Fi vs 4G), 3D enclosure viewer (STL via react-three-fiber, or pre-rendered turntable images).
6. **Tamper protection:** state-machine diagram plus an interactive "try to tamper" simulator (Task 2): tilt, turn, open cover, cover lens, cut network; each lights up the layer that catches it, with its weakness.
7. **Cloud and subscription:** device API list, request flow for an event (402/423/429 outcomes), plan limits toggle demo.
8. **Security and trust:** President face-login flow diagram, ceilings and delegation visual (Task 4), hash-chain visual with a "tamper with a record" button that breaks the chain.
9. **Apps:** screenshots of customer app and ERP in a tabbed carousel (light and dark).
10. **Decisions and trade-offs:** filterable table from `07`.
11. **Status, honesty box:** built / designed / not done (from the ledger). Visible, not hidden.
12. **Roadmap:** bench test, firmware, 5 units, 5-user pilot, payments, custom PCB.
13. **My experience (Agent fills from owner's input):** related experience linking to other portfolio items.
14. **Footer CTA:** contact, next project.

## Behaviour and quality
- Server components by default; client components only for interactive demos; lazy-load heavy ones (3D viewer, charts) with skeletons.
- Accessible: keyboard-operable demos, text alternatives for diagrams, reduced-motion respected, contrast AA, visible focus.
- Responsive to 390 px; diagrams scroll or restack, not shrink illegibly.
- SEO: title, description, OpenGraph image (rendered card), JSON-LD `CreativeWork`.
- Dark/light follows the site.
- Performance: images via `next/image`, STL/3D optional and gated behind a button on mobile.
- Content in a typed data file (`content/solavis.ts` or MDX) so text edits need no component changes.
- No third-party trackers added; no new heavy dependencies without need (Mermaid rendering at build time or pre-rendered SVG preferred).
