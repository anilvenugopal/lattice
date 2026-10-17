# UI standards

Open **Administration › UI kit** in the running app to see every component.

## Page anatomy

```
┌ rail ┬ topbar: logo · breadcrumb · Search (Ctrl J) · theme · shortcuts · avatar ┐
│ icon │ sidebar (only when the section has   │ main                           │
│ icon │ more than one visible child)         │  page_header(title, subtitle)  │
│  …   │                                      │  content                       │
│ user ├──────────────────────────────────────┴────────────────────────────────┤
└──────┴ status bar: environment · user · roles                                ┘
```

- **Rail**: top-level `NavNode`s (`parent=None`). Bottom group: `bottom=True`.
- **Sidebar**: children of the active section. A section with one or zero visible
  children renders without a sidebar (see Jobs).
- **Breadcrumb**: derived from the node chain; detail pages add `crumb=`.

## Page types

| Type | Template | Example |
|---|---|---|
| List | `components/grid_page.html` via `render_grid_page` | `/demo/work`, `/demo/jobs`, `/admin/users` |
| Split list + reader | same, with `layout="split"` | `/demo/inbox` |
| Record (detail) | `page_header` + `card`s with `prop_list` + `timeline` | `/demo/work/1`, `/admin/users/1` |
| Form | `page page--narrow`, `card` with `field`s, `form-actions` | `/demo/work/new` |
| Settings | `card` with `form-row`s | `/account/preferences` |
| Dashboard | `stats` + `grid-2` of cards | `/` |

Containers: `.page` (default), `.page--narrow` (forms, settings, 760px),
`.page--fill` (grid fills the viewport). Layout helpers: `.stack`, `.stack-lg`,
`.cluster`, `.grid-2`, `.grid-2--wide-left`.

## Components

| Macro / class | Use for |
|---|---|
| `brand(class)` | The logo and app name (top bar, sign-in pages). Variants from `LATTICE_BRAND_LOGO_LIGHT` / `LATTICE_BRAND_LOGO_DARK` |
| `page_header(title, subtitle, badge_text, badge_tone)` with a `call` block for buttons | Every page title |
| `card(title, subtitle, flush)` | Grouping content; `flush` for tables |
| `prop_list(items, columns)` | Read-only fields of a record |
| `badge(text, tone)` → `.badge.tone-*` | Status, categories |
| `badge_for(column, value)`, `label_for`, `tone_for` | A grid Column's value with its declared label and tone |
| `alert(tone, text)` or `{% call alert(tone) %}` | Inline message on a page |
| `progress(value)` | 0–100 bar with percentage |
| `pref_row(label, hint)` with a call block, `segmented(name, options, value)`, `select_input(name, options, value)` | Settings rows |
| `session_table(sessions, current_id, revoke)` | Active sessions |
| `signout_button(label, class)` (import `with context`) | Every sign-out control |
| `stat(label, value, href, tone)` | Dashboard counts |
| `field`, `select_field`, `checkbox` | Form inputs with label, hint, error |
| `empty_state(title, text, icon)` | Nothing to show |
| `timeline(events)` | Audit history of a record |
| `user_chip(name, sub)` | A person |
| `.btn` + `--primary`, `--ghost`, `--danger`, `--danger-ghost`, `--link`, `--sm`, `--lg`, `--block` | Buttons |
| `.icon-btn` + `data-tip="…"` | Icon-only buttons always have a tooltip and `aria-label` |
| `.segmented` | 2–4 mutually exclusive options |
| `app.toast(message, tone)` / `toast()` header | Transient feedback |

## Buttons

One primary button per region (the main action). Destructive actions use
`danger` tone and a confirmation. Labels are verbs: "Approve", "Run job",
"Save changes" — not "OK" or "Submit".

## Tones

`neutral` default · `info` in progress / informational · `success` done, healthy ·
`warning` needs attention · `danger` failed, destructive · `accent` highlight
(ownership, special category). Map each status to one tone in the feature module.

## CSS architecture

Five ITCSS layers. `lattice/static/css/app.css` declares their order with
`@layer settings, base, layout, components, utilities;`. A rule in a later layer
always beats an earlier one, whatever its specificity.

| Layer | Folder | Contains | Must not contain |
|---|---|---|---|
| 1 settings | `1-settings/tokens.css` | Custom properties only, in three tiers: primitives `--p-*` (raw palette) → semantic (`--surface-*`, `--text-*`, `--tone-*`, spacing, type) → component tokens (`--rail-w`, `--toast-bg`) | Selectors other than `:root` and theme hooks |
| 2 base | `2-base/base.css` | Reset and bare elements (`body`, `a`, `kbd`, `svg`) | Class selectors |
| 3 layout | `3-layout/shell.css`, `page.css` | Shell regions, page containers, layout objects (`.stack`, `.cluster`, `.grid-2`) | Component visuals |
| 4 components | `4-components/*.css`, one file per family | Named pieces: `.btn`, `.card`, `.dg`, `.palette`. Apps add their own stylesheet, scoped to `[data-app="{key}"]` | Colour literals, primitive tokens, `!important` |
| 5 utilities | `5-utilities/utilities.css` | `.u-*` single-purpose helpers (`u-muted`, `u-mono`, `u-text-right`) | Anything else |

`tests/test_css_architecture.py` enforces these rules:
- colour literals and `--p-*` primitives appear only in settings;
- base has no classes;
- utilities hold only `.u-*` classes, and are the only place `!important` is allowed;
- each file is imported once, into the layer matching its folder.

**Adding styles**
- A new component gets its own file in `4-components/` plus an import line in `app.css`.
- A colour is added as a primitive, then given a semantic token in both theme blocks.
- **Tones:** add `tone-<name>` to `.badge`, `.tag`, `.alert` or `.code-block`. Each tone class sets `--tone-bg`, `--tone-fg` and `--tone-bd`, which those components read.

## Theme and density

Light, dark and system themes come from the semantic tier. Dark mode is
`[data-mode="dark"]` and remaps the semantic tier only. Density (`compact`)
remaps the component tokens `--row-pad-y` and `--control-h`.

## Ctrl+J

Three columns:
- **Sources:** All, Pages, one per grid with `palette=`, then Commands, each with a match count.
- **Results:** five per source under All, up to 30 for one source.
- **Preview:** the highlighted result.

Keys:
- ↑/↓ moves the highlight, and the preview follows.
- Tab and Shift+Tab switch the source.
- Enter opens the result or runs the command.

Providers live in `lattice/components/search/providers.py`; an app adds one through its manifest `search=`.

## Keyboard

Ctrl/⌘+J palette · `?` shortcuts · in grids: `/` search, ↑↓ or J/K move,
Space/X select, Shift+click range, Enter open, Ctrl+A select page, Esc close
panel then clear selection. New keyboard behaviour belongs in `app.js` (global)
or `grid.js` (grid) and in the shortcuts dialog in `base/shell.html`.

## Accessibility

Icon-only controls carry `aria-label`. Focus is visible (`--focus-ring`). Do not
remove outlines without the token replacement. Colour is never the only signal:
badges have text, disabled actions have a `title` with the reason.
