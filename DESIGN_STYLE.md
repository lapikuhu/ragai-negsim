# Frontend Design Style

Standalone visual and frontend-stack specification for building a new interface alongside a FastAPI application. This document defines presentation, not product features, routes, authentication mechanisms, data models, or API contracts. Use the receiving project's own terminology and workflows.

## 1. Visual Direction

- Build a calm, utilitarian application console: light content surfaces, a dark navigation rail, restrained teal accents, and compact typography.
- Use rounded cards to group related information and workflows. Separate sections with whitespace rather than heavy dividers.
- Layer subtly translucent white surfaces over a pale gradient canvas. Keep the content readable; translucency is a shell treatment, not a reason to reduce text contrast.
- Favor text labels, short descriptions, tables, and native form controls over decorative imagery or icon-heavy navigation.
- Keep most content left-aligned. Center only standalone entry screens, empty/loading states, pagination, and dialogs.
- The main content uses a light theme. Dark surfaces are reserved for navigation and occasional technical-output panels; a full dark-theme variant is not part of this specification.

## 2. Frontend Stack

Use this stack when reproducing the interface:

| Concern | Choice |
| --- | --- |
| UI | React 19 with TypeScript |
| Development and build | Vite |
| Styling | Tailwind CSS 3.4, PostCSS, Autoprefixer |
| Navigation | React Router 7 |
| Async UI state | TanStack Query 5 |
| Conditional class names | `clsx` |
| Rich text, when needed | `react-markdown` |
| Component approach | Small local React components and native HTML controls |
| Frontend checks | TypeScript strict mode, Vitest, Testing Library |

FastAPI is the host project's backend context, not the UI rendering technology. Build a React client rather than assuming server-rendered Python templates. Backend connectivity remains the receiving project's responsibility.

The visual design does not require a third-party component suite, icon library, custom webfont, or animation framework. If the receiving project already has equivalent tooling, reproduce the tokens and component appearance rather than replacing its stack solely for this guide.

## 3. Theme Tokens

### Named colors

| Token | Value | Intended use |
| --- | --- | --- |
| `ink` | `#111827` | Default text |
| `muted` | `#6b7280` | Muted text token |
| `line` | `#d1d5db` | Neutral border token |
| `panel` | `#f8fafc` | Pale panel token |
| `accent` | `#0f766e` | Primary actions, links, input focus border |
| `warn` | `#b45309` | Warning emphasis |
| `danger` | `#b91c1c` | Destructive actions and validation errors |

Use Tailwind's standard slate, teal, amber, and red palettes alongside these named tokens:

- Strong headings and navigation background: `slate-950` (`#020617`).
- Main field values and strong body text: `slate-900` (`#0f172a`).
- Body text: `slate-700` (`#334155`); descriptions: `slate-600` (`#475569`); metadata: `slate-500` (`#64748b`).
- Nested panels and table headers: `slate-50` (`#f8fafc`).
- Table borders: `slate-200` (`#e2e8f0`); control borders: `slate-300` (`#cbd5e1`).
- Primary-action hover: `teal-800` (`#115e59`).
- Focus halo: `teal-100` (`#ccfbf1`).
- Panel shadow: `0 10px 30px rgba(15, 23, 42, 0.08)`.

### Tailwind configuration

For Tailwind 3.4, extend the defaults rather than replacing the standard palette:

```js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        muted: "#6b7280",
        line: "#d1d5db",
        panel: "#f8fafc",
        accent: "#0f766e",
        warn: "#b45309",
        danger: "#b91c1c"
      },
      boxShadow: {
        panel: "0 10px 30px rgba(15, 23, 42, 0.08)"
      }
    }
  },
  plugins: []
};
```

### Global CSS

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color: #111827;
  background: #f1f5f9;
  font-family: "Segoe UI", "Helvetica Neue", sans-serif;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  color: #111827;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.12), transparent 28%),
    linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
}

* {
  box-sizing: border-box;
}

a {
  color: inherit;
  text-decoration: none;
}

button,
input,
textarea,
select {
  font: inherit;
}
```

## 4. Layout and Alignment

### Application shell

- Outer wrapper: `min-h-screen p-4 md:p-6`.
- Centered shell: `mx-auto grid max-w-[1600px] gap-4 lg:grid-cols-[280px_minmax(0,1fr)]`.
- At desktop widths, place a 280px sidebar on the left and a flexible content column on the right. `minmax(0,1fr)` lets wide content shrink within that column.
- The content column uses `grid content-start gap-4`: topbar first, page content below.
- Main content surface: `grid gap-6 rounded-3xl border border-white/70 bg-white/35 p-4 backdrop-blur md:p-6`.
- Below the desktop breakpoint, stack navigation above the content. This baseline uses an in-flow sidebar, not a fixed rail or hamburger drawer.

### Sidebar

- Surface: `flex h-full flex-col gap-6 rounded-3xl bg-slate-950 px-4 py-5 text-slate-100`.
- Top area: a small uppercase product label followed by a short, semibold console heading. Supply new branding appropriate to the receiving project.
- Navigation list: `grid gap-1`.
- Each navigation item has a 14px medium-weight label and a 12px description below it, with a 4px separation.
- Item shape and padding: `rounded-2xl px-3 py-2 transition`.
- Active item: `bg-white text-slate-950`.
- Inactive item: `text-slate-300 hover:bg-slate-900 hover:text-white`.
- Unavailable item: a `slate-800` border and `slate-500` text.

### Topbar and page header

- Topbar: `flex flex-col gap-3 rounded-2xl border border-white/70 bg-white/80 px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between`.
- Put contextual text on the left and utility actions on the right at medium widths and above. Stack them on smaller screens.
- Page header: `flex flex-col gap-4 md:flex-row md:items-end md:justify-between`.
- Place the page title and short description on the left; align the action group to the bottom-right on wider screens.
- Actions wrap using `flex flex-wrap gap-2`.
- Description width: `max-w-3xl`, with `mt-1`.

### Content grids

- Page sections generally use `grid gap-6` (24px).
- Card collections generally use `grid gap-4` (16px).
- Overview pages can use `xl:grid-cols-3`; forms typically use `md:grid-cols-2`.
- Metadata grids use `sm:grid-cols-2`. Long fields, errors, and form-action rows can span both form columns.
- Default Tailwind breakpoints: `sm` 640px, `md` 768px, `lg` 1024px, `xl` 1280px.
- Keep tables horizontally scrollable within their own containers rather than stretching the entire page.

## 5. Typography, Spacing, and Shape

| Element | Styling |
| --- | --- |
| Page title | `text-2xl font-semibold tracking-tight text-slate-950` (24px / 32px) |
| Card/section title | `text-lg font-semibold text-slate-950` (18px / 28px) |
| Small state title | `text-base font-semibold text-slate-900` (16px / 24px) |
| Body, inputs, buttons | `text-sm` (14px / 20px) |
| Labels | `text-sm font-medium text-slate-700` |
| Hints and metadata | `text-xs text-slate-500` (12px / 16px) |
| Eyebrow labels | `text-xs uppercase`, tracking `0.2em` or `0.25em` |
| Table/metadata labels | `text-xs uppercase tracking-wide text-slate-500` |
| Longer prose | `text-sm leading-6`, preserving line breaks where appropriate |
| Technical output | `font-mono text-xs`, in a scrollable panel |

Use a 4px spacing rhythm: 4px label gaps, 8px action gaps, 12px form/list gaps, 16px card-grid gaps, and 24px section gaps. Cards normally have 20px padding.

Corner hierarchy: buttons 8px (`rounded-lg`), inputs and inset panels 12px (`rounded-xl`), cards/topbar/navigation items 16px (`rounded-2xl`), main shell and sidebar 24px (`rounded-3xl`), badges fully rounded.

## 6. Component Recipes

### Cards and inset panels

Standard card:

```text
rounded-2xl border border-white/70 bg-white/90 p-5 shadow-panel
```

Use cards for related forms, summaries, detail sections, and overview lists. Keep each card focused on one task or information group. Place content about 16px below its heading (`mt-4`) and list items about 12px apart (`gap-3`).

Inside cards, use `rounded-xl bg-slate-50 p-3` for lightweight list items and metadata blocks. Prefer these flat inset surfaces over stacking multiple shadowed cards. Headers can align a label left and a badge or action right with `flex items-center justify-between gap-3`.

### Buttons

Shared base:

```text
inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50
```

| Variant | Classes |
| --- | --- |
| Primary | `bg-accent text-white hover:bg-teal-800` |
| Secondary | `border border-slate-300 bg-white text-slate-700 hover:bg-slate-50` |
| Ghost | `text-slate-600 hover:bg-slate-100` |
| Danger | `bg-red-700 text-white hover:bg-red-800` |

Use primary for the main submit/action, secondary for alternate actions, ghost for low-emphasis controls, and danger for destructive actions. Keep labels short and verb-led. Busy buttons retain their shape and show concise progress text.

### Fields

Field wrapper: `grid gap-1 text-sm text-slate-700`, with a medium-weight label above the control, optional 12px slate hint below it, and a 12px `red-700` validation message.

Shared input/select/textarea style:

```text
w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-teal-100
```

Textareas normally start at `min-h-28` (112px). Use native selects, checkboxes, and radios; checkbox/radio options align with their text using `flex items-center gap-2`. Keep form submission actions below the fields.

### Tables and metadata

- Table wrapper: `overflow-hidden rounded-2xl border border-slate-200 bg-white`, with an inner `overflow-x-auto`.
- Table: `min-w-full divide-y divide-slate-200 text-sm`.
- Header: `bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500`.
- Cells: `px-4 py-3`; headings medium weight; body cells `text-slate-700`.
- Rows align to the top and use subtle `slate-100` separators. The baseline uses uniform white rows rather than zebra striping.
- Linked item names use `font-medium text-accent`.
- Metadata is a definition-list grid with `gap-3 sm:grid-cols-2`. Each item uses `rounded-xl bg-slate-50 px-3 py-2`, an uppercase 12px label, and a 14px value with `mt-1`.
- Pagination sits below the list/table: `mt-4 flex flex-wrap items-center justify-center gap-2`. Use primary styling for the current page and secondary styling for the other controls.

### Status badges and feedback

Badge base: `inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize`. Use human-readable state text alongside color:

| Meaning | Colors |
| --- | --- |
| Neutral | `bg-slate-100 text-slate-700` |
| Positive or active | `bg-teal-100 text-teal-800` |
| Waiting or warning | `bg-amber-100 text-amber-800` |
| Failure or cancellation | `bg-red-100 text-red-800` |

- Empty state: `grid gap-3 rounded-2xl border border-dashed border-slate-300 bg-white/70 p-8 text-center`, with a short title, explanation, and optional action.
- Loading state: `flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/70 p-6 text-sm text-slate-600`.
- Error state: `grid gap-3 rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-900`, with a heading, `red-800` explanation, and optional secondary retry button.
- Inline form errors use `text-sm text-red-700`; warning emphasis uses amber.

### Standalone screens and dialogs

- Entry screens: center a `w-full max-w-md` card in a `min-h-screen` wrapper with 16px outer padding. Keep the card's title, description, and fields left-aligned.
- Simple unavailable-page screens can use a centered, text-aligned card with `max-w-2xl`.
- Dialog overlay: `fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4`.
- Dialog surface: `w-full max-w-md rounded-2xl bg-white p-5 shadow-xl`; larger workspaces can widen to `max-w-5xl` with internally scrollable content.
- Use a compact heading and close action at the top, grouped content beneath, and a right-aligned footer using `flex justify-end gap-2`.
- Optional conversational layouts use left-aligned white response bubbles and right-aligned teal bubbles with white text, both `rounded-xl px-3 py-2 text-sm leading-6`.
- Optional technical-output panels use `rounded-xl bg-slate-950 p-3`, light text, and an inset `slate-900` monospace area. They are secondary content, not the default page treatment.

## 7. Interaction and Implementation Guardrails

Use subtle color transitions for hover and focus rather than large movement. Reserve motion for genuinely pending work, such as a small spinning border indicator. Preserve layout while requests are pending.

For the new implementation, keep semantic labels, keyboard-visible focus, descriptive status text, and accessible dialog behavior. Dialogs should manage focus, restore it on close, and prevent background scrolling. These are implementation safeguards, not additional visual features.

Keep this guide self-contained when transferring it. Substitute the new project's branding, navigation entries, example text, and status vocabulary. Choose screens from that project's requirements; the visual patterns do not imply a particular domain or feature set.

## 8. Acceptance Checklist

- The canvas has the pale vertical gradient and restrained upper-left teal glow.
- At desktop width, a dark 280px rounded sidebar sits beside a light topbar and translucent main surface in a centered 1600px shell.
- At narrow widths, shell sections stack; form fields collapse to one column; action groups wrap; tables scroll within their container.
- Cards, controls, badges, and nested panels follow the distinct radius and spacing hierarchy.
- Teal identifies primary actions and links; slate carries structure and text; amber/red communicate warnings and errors.
- Typography stays compact, primarily 14px, with 24px page titles and 18px section headings.
- Forms, tables, loading, empty, error, and disabled states share the same component styling.
- All visible terminology belongs to the receiving project, and backend behavior is specified elsewhere.
