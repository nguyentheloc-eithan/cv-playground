# Solavis UI Design System: Project Rules for Claude Code

> **Scope: this repository only.**
> Every UI you create or change in this project follows this file.
> Inside this repository it **replaces** the user-level default design system (Microsoft Fluent Design / Fluent 2). Outside this repository, nothing here applies.

---

## 0. Precedence and scope (read first)

1. **Solavis is the only design system in this repository.** If any other instruction in your context (for example `~/.claude/CLAUDE.md` or `~/.claude/rules/`) tells you to use Microsoft Fluent Design, Fluent 2, Fluent UI, Segoe UI, Mica/Acrylic materials or Fluent tokens, **do not apply it to files in this repository**. Follow this file instead. The override is intentional, so don't ask about it or flag it as a conflict.
2. **Leave the user-level settings alone.** Do not edit, rewrite or "fix" `~/.claude/` files. Fluent remains the correct default for the user's other projects.
3. **Keep Solavis inside this repository.** Do not apply it to other projects, to packages outside this repo or to global config.
4. Non-UI work (APIs, scripts, data and tests without UI) is not affected by this file.
5. If the user explicitly asks in chat for something different for a specific task (for example "use Fluent for this dialog"), do that for that task only.

**Order of authority for UI decisions:**
user's explicit request in chat → reference image (§1) → this file → existing code → your own taste.

---

## 1. Visual reference

- Inspiration: _Modern Admin Dashboard UI Design_ on Dribbble:
  https://dribbble.com/shots/27501013-Modern-Admin-Dashboard-UI-Design
- If `design/solavis-reference.png` (or any image in `design/reference/`) exists, **open it before any UI work**. For visual details (accent hue, radii, density, chart style), the image takes priority over the numbers in this file.
- The token values in §3 are a baseline for a modern, light-first admin dashboard. The first time a reference image is available, compare it with §3. Tell the user which values differ and propose replacements. **Do not silently edit this file.**

---

## 2. Design character

- Clean, airy, light-first SaaS admin: a cool grey canvas with white cards floating on soft shadows.
- Generous radii (10–20px), generous whitespace, few visible borders.
- **One accent color (indigo)**, used sparingly: primary actions, the active nav item, the main chart series.
- Data first: large, readable KPI numbers, quiet labels and calm charts.
- Status is shown with **soft tinted pills**, never saturated solid badges.
- **What it is not:** Fluent's small 4px corners, Segoe UI, acrylic/mica/blur materials, reveal-highlight effects, Fluent's brand blue `#0F6CBD`, dense ribbon-style command bars.

---

## 3. Design tokens

Implement the tokens **once** as CSS custom properties in the project's global stylesheet, then reference them everywhere.
**Never hard-code hex/rgba colors, radii or shadows in components. Use `var(--sv-*)` only.**

If no tokens file exists yet, create `src/styles/solavis-tokens.css` (or put it in the project's existing global-styles location) and import it once in the app entry.

```css
/* ============ Solavis tokens: light (default) ============ */
:root {
  /* Surfaces */
  --sv-bg: #f4f6fb; /* app canvas behind cards */
  --sv-surface: #ffffff; /* cards, sidebar, menus, inputs */
  --sv-surface-muted: #f8f9fc; /* table header, segmented-control track */
  --sv-surface-hover: #f3f5fa; /* row/nav/menu hover */
  --sv-border: #e6e9f2; /* dividers, decorative card lines */
  --sv-border-input: #8a93a5; /* form-control outlines (3:1 on white) */

  /* Text (all pass WCAG AA 4.5:1 on --sv-surface and --sv-bg) */
  --sv-text: #111827;
  --sv-text-secondary: #525c6e;
  --sv-text-muted: #6b7385; /* lightest color allowed for readable text */
  --sv-text-on-primary: #ffffff;

  /* Brand */
  --sv-primary: #4f46e5;
  --sv-primary-hover: #4338ca;
  --sv-primary-text: #4f46e5; /* links / primary-colored text */
  --sv-primary-soft: #eef0ff; /* active nav bg, icon tiles, chips */
  --sv-focus-ring: rgba(79, 70, 229, 0.35);

  /* Status: text color / soft background */
  --sv-success: #15803d;
  --sv-success-soft: #e9f7ef;
  --sv-warning: #b45309;
  --sv-warning-soft: #fef4e4;
  --sv-danger: #b91c1c;
  --sv-danger-soft: #fdeded;
  --sv-danger-solid: #dc2626;
  --sv-info: #0369a1;
  --sv-info-soft: #e8f5fc;

  /* Charts (use in this order) */
  --sv-chart-1: #4f46e5; /* indigo */
  --sv-chart-2: #0ea5e9; /* sky */
  --sv-chart-3: #f59e0b; /* amber */
  --sv-chart-4: #10b981; /* emerald */
  --sv-chart-5: #f43f5e; /* rose */
  --sv-chart-6: #94a3b8; /* slate (other / previous period) */
  --sv-chart-grid: #e6e9f2;

  /* Typography */
  --sv-font:
    'Inter', ui-sans-serif, -apple-system, 'Helvetica Neue', Arial, sans-serif;

  /* Radius */
  --sv-radius-sm: 6px; /* checkbox, kbd hint, tooltip */
  --sv-radius-md: 10px; /* buttons, inputs, nav items, menu items */
  --sv-radius-lg: 12px; /* popovers, dropdowns, icon tiles, toasts */
  --sv-radius-xl: 16px; /* cards */
  --sv-radius-2xl: 20px; /* modals, promo panels */
  --sv-radius-pill: 999px; /* badges, avatars, switches */

  /* Elevation */
  --sv-shadow-card:
    0 1px 2px rgba(16, 24, 40, 0.04), 0 4px 16px rgba(16, 24, 40, 0.06);
  --sv-shadow-raised: 0 8px 24px rgba(16, 24, 40, 0.1);
  --sv-shadow-overlay: 0 16px 40px rgba(16, 24, 40, 0.16);
  --sv-overlay: rgba(17, 24, 39, 0.45);

  /* Spacing (4px base) */
  --sv-space-1: 4px;
  --sv-space-2: 8px;
  --sv-space-3: 12px;
  --sv-space-4: 16px;
  --sv-space-5: 20px;
  --sv-space-6: 24px;
  --sv-space-8: 32px;
  --sv-space-10: 40px;
  --sv-space-12: 48px;

  /* Layout */
  --sv-sidebar-w: 264px;
  --sv-sidebar-w-collapsed: 80px;
  --sv-topbar-h: 72px;
  --sv-content-max: 1440px;

  /* Motion */
  --sv-ease: cubic-bezier(0.2, 0, 0, 1);
  --sv-dur-fast: 120ms;
  --sv-dur: 200ms;
}

/* ============ Dark theme: only if the project enables dark mode ============ */
[data-theme='dark'] {
  --sv-bg: #0b0f19;
  --sv-surface: #121826;
  --sv-surface-muted: #182033;
  --sv-surface-hover: #1c2539;
  --sv-border: #232c40;
  --sv-border-input: #606a80;

  --sv-text: #e8ebf3;
  --sv-text-secondary: #a4acbd;
  --sv-text-muted: #8891a5;

  --sv-primary: #5b54f0;
  --sv-primary-hover: #4f46e5;
  --sv-primary-text: #8b90ff;
  --sv-primary-soft: rgba(91, 84, 240, 0.18);
  --sv-focus-ring: rgba(139, 144, 255, 0.45);

  --sv-success: #4ade80;
  --sv-success-soft: rgba(74, 222, 128, 0.14);
  --sv-warning: #fbbf24;
  --sv-warning-soft: rgba(251, 191, 36, 0.14);
  --sv-danger: #f87171;
  --sv-danger-soft: rgba(248, 113, 113, 0.14);
  --sv-info: #38bdf8;
  --sv-info-soft: rgba(56, 189, 248, 0.14);

  --sv-chart-grid: #232c40;

  /* In dark mode cards get a 1px --sv-border instead of a visible shadow */
  --sv-shadow-card: 0 1px 2px rgba(0, 0, 0, 0.4);
  --sv-shadow-raised: 0 8px 24px rgba(0, 0, 0, 0.45);
  --sv-shadow-overlay: 0 16px 40px rgba(0, 0, 0, 0.55);
  --sv-overlay: rgba(0, 0, 0, 0.6);
}
```

**Tailwind:** if the project uses Tailwind, map these variables in the theme (`tailwind.config.*` for v3, `@theme` in CSS for v4), for example `primary: 'var(--sv-primary)'` and `rounded-xl → var(--sv-radius-xl)`. Then use the theme classes rather than arbitrary values.

### 3.1 Typography

- Font: **Inter**. Load it explicitly (`@fontsource/inter`, `next/font`, or self-hosted woff2). Do not rely on `system-ui`, which renders as Segoe UI on Windows and drifts back toward Fluent.
- Every numeric value (KPIs, table numbers, chart ticks) uses `font-variant-numeric: tabular-nums`.
- Headings use `letter-spacing: -0.01em`. Use sentence case everywhere; never uppercase buttons.

| Role                     | Size / line-height | Weight                                   | Color                 |
| ------------------------ | ------------------ | ---------------------------------------- | --------------------- |
| Page title (H1, top bar) | 24 / 32            | 600                                      | `--sv-text`           |
| Modal title              | 18 / 28            | 600                                      | `--sv-text`           |
| Card / section title     | 16 / 24            | 600                                      | `--sv-text`           |
| KPI value                | 28 / 36            | 600                                      | `--sv-text`           |
| Body                     | 14 / 20            | 400                                      | `--sv-text`           |
| Label, table header      | 13 / 18            | 500                                      | `--sv-text-secondary` |
| Caption, meta, ticks     | 12 / 16            | 500                                      | `--sv-text-muted`     |
| Sidebar section label    | 11 / 16            | 600, UPPERCASE, `letter-spacing: 0.06em` | `--sv-text-muted`     |

---

## 4. Layout: the app shell

```
┌────────────┬──────────────────────────────────────────────────────┐
│  SIDEBAR   │  TOP BAR: title / subtitle  ·  search  ·  bell  ·  avatar │
│  264px     ├──────────────────────────────────────────────────────┤
│  logo      │  [ KPI ] [ KPI ] [ KPI ] [ KPI ]      4 × 3 cols       │
│  nav       │  [ Main chart card     8 cols ] [ Side card  4 cols ]  │
│  groups    │  [ Data table card                         12 cols ]   │
│  …         │                                                        │
│  promo     │                                                        │
│  profile   │                                                        │
└────────────┴──────────────────────────────────────────────────────┘
```

- The canvas is `--sv-bg`. Content padding is 32px on desktop, 24px on tablet and 16px on mobile. Content width is capped at `--sv-content-max`.
- 12-column grid with a **24px gap** between cards, both horizontally and vertically.
- Breakpoints:
  - ≥ 1280px: full sidebar.
  - 1024–1279px: sidebar collapses to an 80px icon rail with tooltips.
  - < 1024px: sidebar becomes an off-canvas drawer opened from a menu button in the top bar.
  - KPI grid: 4 → 2 (< 1280px) → 1 (< 640px). Chart row stacks below 1024px.

---

## 5. Components

### Sidebar

- Background `--sv-surface` with a 1px `--sv-border` on the right edge and no shadow. Padding 24px 16px.
- Top: a 32px logo mark (`--sv-primary` background, `--sv-radius-md`) plus the "Solavis" wordmark at 18/600.
- Nav item: 44px tall, `--sv-radius-md`, padding 0 12px, 12px gap, 20px icon, label 14/500 in `--sv-text-secondary`.
  - Hover: `--sv-surface-hover` background, `--sv-text` color.
  - **Active:** `--sv-primary-soft` background, `--sv-primary-text` for icon and label, weight 600.
  - Count badge: a right-aligned pill in `--sv-primary-soft` / `--sv-primary-text`, 12/500.
- Group labels (e.g. MAIN, MANAGEMENT, SYSTEM) use the sidebar-section-label style, with 24px above and 8px below.
- Bottom (optional): a help/upgrade card (`--sv-primary-soft`, `--sv-radius-2xl`, 16px padding), then the user row: 36px avatar, name 14/600, role 12 muted, chevron.

### Top bar

- 72px tall and sticky. Transparent over the canvas; once the page scrolls, it gets a solid `--sv-bg` background and a bottom `--sv-border`. No blur.
- Left: H1 page title, with an optional subtitle or breadcrumb (13–14, `--sv-text-secondary`).
- Right, 12px gap:
  - Search field: 320px wide, 40px tall, `--sv-surface`, `--sv-radius-md`, with a leading search icon and a trailing `⌘K` hint chip.
  - Icon buttons: 40×40, `--sv-surface`, `--sv-radius-md`. Notifications show an 8px `--sv-danger-solid` dot.
  - Avatar: 40px circle.

### Card (base container)

- `--sv-surface`, `--sv-radius-xl`, `--sv-shadow-card`. **No border in light mode**; 1px `--sv-border` in dark mode. Padding 24px (20px on mobile).
- Header: title 16/600 on the left. On the right go the actions: a segmented control (Weekly / Monthly / Yearly), a "View all" link in `--sv-primary-text`, or a 32px kebab icon button. Leave 20px below the header.

### KPI / stat card

- Top row: label 13/500 secondary on the left; on the right, a 40×40 icon tile (`--sv-radius-lg`, `--sv-primary-soft` background, 20px icon in `--sv-primary`). Tiles may use the status soft colors to tell KPIs apart.
- Value: 28/36, weight 600, tabular-nums, 12px below the top row.
- Bottom row: a delta pill (`--sv-success-soft` / `--sv-success` or `--sv-danger-soft` / `--sv-danger`, 12/600, with a 14px arrow-up-right / arrow-down-right icon), then "vs last month" in 12 muted.
- Optional sparkline: 32px tall, `--sv-chart-1`, 2px stroke, no axes.

### Data table (inside a card)

- Toolbar (24px padding): search (240px), Filter and Export as secondary buttons, a date-range picker, and the primary action on the right.
- Header row: `--sv-surface-muted`, 44px tall, 13/500 secondary, sentence case, 14px sort icons.
- Body rows: 60px tall, 14px text, 1px `--sv-border` divider between rows. Hover uses `--sv-surface-hover`; selected uses `--sv-primary-soft`.
- First column: checkbox (18px, `--sv-radius-sm`), 32px avatar, name 14/600 with a 12 muted subline.
- Numbers are right-aligned with tabular-nums. Status uses the status badge below. The last column is a kebab menu.
- Footer: "Showing 1–10 of 248" (13 muted) on the left. Pagination on the right uses 32×32 `--sv-radius-md` buttons; the active page is `--sv-primary` with white text.

### Status badge

- Pill, 24px tall, padding 0 10px, 12/600, soft background with matching text color and an optional 6px leading dot.
- Mapping:
  - **success:** Completed, Active, Paid, Delivered
  - **warning:** Pending, Processing, In review
  - **danger:** Cancelled, Failed, Overdue
  - **info:** New, Draft, Scheduled
  - **neutral:** `--sv-surface-muted` background with `--sv-text-secondary` text

### Buttons

- Sizes: **md** is 40px tall, padding 0 16px, 14/600. **sm** is 32px tall, padding 0 12px, 13/600. Both use `--sv-radius-md`, an 18px icon and an 8px gap.
- **Primary:** `--sv-primary` background with white text; hover `--sv-primary-hover`. **Only one primary button per region.**
- **Secondary:** `--sv-surface` background, 1px `--sv-border`, `--sv-text`; hover `--sv-surface-hover`.
- **Ghost:** transparent, `--sv-text-secondary`; hover `--sv-surface-hover`.
- **Destructive:** `--sv-danger-solid` background with white text.
- **Disabled:** 45% opacity, `cursor: not-allowed`, no hover change.
- Icon-only buttons are square at the same height and always have an `aria-label`.
- No gradients and no uppercase on buttons. Transitions use `--sv-dur-fast` and `--sv-ease`.

### Inputs, selects, search

- 40px tall, `--sv-radius-md`, `--sv-surface` background, 1px `--sv-border-input`, padding 0 12px, 14px text, placeholder in `--sv-text-muted`.
- Label above the field (13/500 `--sv-text`, 6px gap). Helper text 12 muted. On error: `--sv-danger-solid` border plus a 12px message in `--sv-danger` with an icon.
- Selects have a 16px chevron-down. Checkbox, radio and switch use `--sv-primary` when on. The switch is a 36×20 pill.
- **Focus (every interactive element, `:focus-visible`):** `--sv-primary` border plus `box-shadow: 0 0 0 3px var(--sv-focus-ring)`.

### Tabs and segmented control

- **Segmented control** (chart period switch): track in `--sv-surface-muted`, `--sv-radius-md`, 4px padding. Items are 32px tall with `--sv-radius-sm` and 13/500 secondary text. The active item gets `--sv-surface`, `--sv-shadow-card` and `--sv-text`.
- **Page tabs:** 14/500 secondary text with 24px gaps over a bottom `--sv-border`. The active tab has `--sv-text` and a 2px `--sv-primary` underline.

### Menus, popovers, tooltips

- Dropdown or popover: `--sv-surface`, `--sv-radius-lg`, `--sv-shadow-raised`, 6px padding. Items are 36px tall with `--sv-radius-md` and a hover of `--sv-surface-hover`. Destructive items use `--sv-danger` text.
- Tooltip: `--sv-text` background with white 12/500 text, `--sv-radius-sm`, padding 6px 10px.

### Modal

- `--sv-surface`, `--sv-radius-2xl`, `--sv-shadow-overlay`, 480px wide (640px for forms), 24px padding. Backdrop is `--sv-overlay` with **no blur**.
- Header: title 18/600 plus a close icon button. Footer actions are right-aligned: secondary, then primary.

### Toast

- Bottom-right, `--sv-surface`, `--sv-radius-lg`, `--sv-shadow-raised`. A status icon sits in a soft tile, followed by the message and an optional action. Auto-dismiss after 5s; errors stay until dismissed.

### Avatar

- Circle, 24, 32 or 40px. The fallback shows initials in `--sv-primary-text` on `--sv-primary-soft`, weight 600.

### Empty and loading states

- Empty: centered in the card. A 72px `--sv-surface-muted` circle holds a 32px icon, followed by a title (16/600), one line of 14px secondary text and a single primary button.
- Loading: skeleton blocks in `--sv-surface-muted`, shaped like the real content, with a subtle shimmer that is disabled under `prefers-reduced-motion`. No full-page spinners.

---

## 6. Charts

- Use the chart library the project already has (Recharts, Chart.js, ECharts, ApexCharts, …) and apply these styles through its options. **Ask before adding a new chart library.**
- If the library needs literal colors at runtime, read them from the tokens with `getComputedStyle(document.documentElement).getPropertyValue('--sv-chart-1')`.
- Use series colors `--sv-chart-1` … `--sv-chart-6` in order. A single-series chart uses `--sv-chart-1`, and the previous-period comparison uses `--sv-chart-6`.
- **Line / area:** 2.5px stroke and smooth (monotone) curves. Point markers appear only on hover: a 6px dot with white fill and a 2px series-color stroke. Area fill is a vertical gradient of the series color from 18% to 0% opacity.
- **Bar:** maximum width 32px, 6px radius on the top corners (for stacked bars, only the top segment), and roughly 40% gaps between categories.
- **Donut:** 16–20px ring with the total in the center (24/600) and a caption. The legend list sits beside it: dot, label, value.
- **Grid and axes:** horizontal 1px dashed `--sv-chart-grid` lines only. No vertical grid, axis lines or chart border. Tick labels are 12px `--sv-text-muted` with abbreviated values (12k, 1.2M).
- **Tooltip:** `--sv-text` background with white 12/500 text, `--sv-radius-md`, padding 8px 12px, `--sv-shadow-raised`. Show the series dot, label and value.
- **Legend:** an 8px dot plus 13px secondary text, in the card header or below the chart.
- Never rely on color alone: always pair it with a legend or direct labels, plus a tooltip on hover or focus.

---

## 7. Icons

- **Lucide** (`lucide-react` or the stack's equivalent), outline style, stroke width 1.75. Sizes: 20px for nav and the top bar, 18px in buttons, 16px inline.
- If the project already uses another outline icon set, keep using that set.
- **Do not use Fluent System Icons (`@fluentui/react-icons`) in this project.**

---

## 8. Accessibility (non-negotiable)

- All text tokens already meet WCAG AA (4.5:1). Don't introduce lighter text colors.
- Form-control outlines use `--sv-border-input`, which meets 3:1.
- Every interactive element has a visible `:focus-visible` style (§5 Inputs).
- The sidebar, menus, tabs, tables and modals are fully keyboard-operable. Modals trap focus and close on Esc.
- Icon-only buttons have an `aria-label`. Charts have a text alternative (title plus summary, or a data table).
- Hit targets are at least 32px (40px preferred).
- Respect `prefers-reduced-motion`: no shimmer, and transitions of 0–1ms.

---

## 9. Do not

- Import `@fluentui/*` packages, use `FluentProvider`, Fluent tokens (`tokens.colorBrand…`), Segoe UI as the primary font, Mica/Acrylic or backdrop blur, or reveal/hover-glow effects.
- Hard-code hex/rgba colors, radii or shadows in components.
- Add a new UI kit (MUI, Ant Design, Chakra, Fluent…) without asking. If the project already uses headless or utility tooling (Radix, shadcn/ui, Tailwind), style it with Solavis tokens.
- Use solid, saturated status badges, pure black `#000` text, or a border and a shadow on the same card.
- Use gradients anywhere except chart area fills and the optional sidebar promo card.
- Put more than one primary button in a region, use uppercase button labels, or center body text in tables.

---

## 10. How to work on UI in this repo (Claude Code workflow)

1. **Before any UI task:** apply this file, check for a reference image (§1) and locate the tokens file. If there isn't one, create it from §3 first, and wire up the Tailwind theme mapping if Tailwind is used.
2. **Build with tokens and existing components.** Reuse Solavis components already in the repo before creating new ones.
3. **Existing Fluent-styled code:** when a component you are editing still uses Fluent, convert _that component_ to Solavis as part of the task and mention it in your summary. Don't migrate untouched screens; ask before any repo-wide migration.
4. **Uncovered patterns:** derive them from the closest component here (same radii, spacing scale and color roles). List them in your summary so the user can add them to this file.
5. **This file is the user's.** Change its tokens or rules only when the user asks or approves a proposal.

### Done checklist (verify before reporting a UI task complete)

- [ ] Only `--sv-*` tokens are used; no stray hex values, px radii or shadows.
- [ ] No Fluent imports, components, fonts or icons.
- [ ] Inter is loaded and numbers use `tabular-nums`.
- [ ] Cards use `--sv-radius-xl`, `--sv-shadow-card` and 24px padding, with a 24px grid gap.
- [ ] Exactly one primary action per region.
- [ ] Statuses are soft pill badges, mapped as in §5.
- [ ] Focus is visible, icon buttons are labelled and text contrast is intact.
- [ ] Layout is checked at 1440, 1024, 768 and 390px widths.
- [ ] If dark mode is enabled, it uses the dark token set with nothing hard-coded.

---

## Setup notes (for the developer; Claude can skip this section)

- **Location:** save this file as `.claude/rules/solavis-ui-design.md` in the project. Rule files without `paths` frontmatter load automatically every session.
  Alternative: keep it at the project root and add the line `@solavis-ui-design.md` to the project's `CLAUDE.md`. Claude Code asks you to approve the import the first time.
- **Reference image:** save a screenshot of the Dribbble shot as `design/solavis-reference.png`.
- **Check it's loaded:** run `/memory` in Claude Code; the file should be listed.
- **Make the global rule yield (recommended):** in `~/.claude/CLAUDE.md`, word your Fluent rule as a default, for example:
  `Default UI design system: Microsoft Fluent 2 — unless the project's own CLAUDE.md or .claude/rules/ names a different design system; then use the project's.`
