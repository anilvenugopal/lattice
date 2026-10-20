# 0010. Theming and overrides: the host owns the brand, apps style only their own pages

Status: Accepted (20 October 2026), as built below; rail groups and app keyboard shortcuts
are deferred until an app needs them.

## Context

A host runs several apps in one shell, for example strategiq, taskline and
incidents. Each party wants to change how things look:
- a host wants its own logo, name and colours;
- an app wants its own icon, perhaps an accent, and some styles of its own.

If any app could restyle the shell, one screen could show several colour
schemes. Lattice exists to prevent that inconsistency.

## Decision

### Precedence

Every lookup goes **host, then app, then core**. Each level may override only
what it owns:

| Level | May change | May not change |
|---|---|---|
| Core | Every default | — |
| Host | Brand: name, logos, favicon, the allowed brand tokens, fonts, the icon set, whole core pages (sign-in, error, home) | Component or layout CSS; another app's pages |
| App | Its own pages, templates, icons, accent and component tokens, inside its namespace | Core tokens at `:root`, core templates, the shell, other apps |

No level edits or copies core files. Changes go through tokens, slots,
registries, or a template override at a defined place.

### Logos and favicon

- **The host** sets these in settings: `LATTICE_BRAND_LOGO_LIGHT`,
  `LATTICE_BRAND_LOGO_DARK`, `LATTICE_BRAND_SHOW_NAME`.
- **An app** declares an **app icon** in its manifest: a name in the icon
  registry, from the icons the app adds (`icon="demo:app"`). Icons draw with
  `currentColor`, so one icon serves light and dark. It is shown in the Help menu
  next to the app's help link. An app never replaces the shell logo.

### Colour scheme

- **Host theme file.** The host may add `static/theme.css` in its host folder
  (`create_app(host_dir=…)`), served at `/static/host/theme.css`, that redefines semantic
  tokens inside `@layer settings`, once in `:root` and once in
  `[data-mode="dark"]`. It loads after the core tokens, so it wins. Components
  are unchanged because they read only tokens.
- **The allowed host tokens** are the brand set: `--brand`, `--brand-hover`,
  `--brand-alt`, `--accent`, `--text-on-accent`, `--link`, the `--surface-*`
  tokens, the `--text*` tokens, `--font-ui` and `--font-mono`. The list lives in one place in core
  (`lattice/kernel/css_rules.py`) and is shown in the developer help, Running ›
  Branding a host, and in Reference › Design tokens.
- **An app accent, scoped to its pages.** The shell marks each app's pages with
  `data-app="{key}"` on `<main>`. An app may define `--app-accent` and its own
  component tokens under `[data-app="{key}"]`, in `@layer components`. Core
  components that show an app's identity (its rail entry, page header accent)
  read `--app-accent`, falling back to `--brand`.
- **Status tones and chart series colours** come from an app's Column and Chart
  specs, and those name semantic tones (`success`, `warning`…). They never name
  colours directly.

### Icons

- **One registry** with namespaces. `icon("search")` looks in the host's icon set
  first, then core. `icon("taskline:dag")` looks in that app's icons.
- **A host can replace the whole core icon set** by supplying the same names.
- **An app can add icons** in its own namespace only.

### Templates

- **Search order:** the host's `templates/` folder, then the app's own folder
  (`{key}/…`), then core.
- **A host may override whole core pages:** sign-in, error pages and home.
- **An app renders its pages with core macros,** and cannot override core
  templates.
- **Named slots for small additions.** Core templates expose these, and hosts and
  apps register content for them:
  - `topbar.end`, `statusbar.start`, `statusbar.end`;
  - `signin.footer`;
  - `home.sections`;
  - `help.menu`.

### Other injected items

| Item | Owner | Mechanism |
|---|---|---|
| Rail order and grouping | Host | Order of the app list in `create_app`, plus optional groups |
| Home tiles and widgets | Apps contribute, host orders | Registry (tiles exist) |
| Ctrl+J sources and commands | Apps | Registry (exists) |
| Keyboard shortcuts | Apps | Registry; a clashing key fails at startup |
| Help and documentation links | App | `help_url` in the manifest, listed in the help menu |
| Email and notification layout | Host overrides the core layout; app owns content | Template search order |
| Wording, date and number formats | Core, with user preferences | Preferences today; translations only when needed |

### Checks

`tests/test_css_architecture.py` is extended to check stylesheets by owner:

- **A host `theme.css`** sets only allowed tokens, in both light and dark,
  inside `@layer settings`, and contains no other rules.
- **An app stylesheet** declares `@layer components` and sets no core token at
  `:root` or `[data-mode]`. Its token definitions sit under its
  `[data-app="{key}"]` selector.
- **The existing rules apply to app CSS too:** no colour literals outside
  settings, and no `--p-*` tokens.

The app loader rejects:
- a template override from an app outside its own namespace;
- an icon an app registers outside its namespace;
- a slot name that does not exist.

## Consequences

- One host looks like one product, whatever apps it runs. An app is recognisable
  by its icon and accent, not by a different theme.
- A rebrand is one theme file and two logo files.
- An app that needs a visual the components cannot express adds a component token
  in its own scope, or asks for a change in core. It cannot patch the shell.
- The kernel restructure builds the template search order, the icon registry,
  the slots and the `data-app` marking as part of the app loader.

## Rejected

- **Apps override core templates and CSS freely.** Inconsistent screens, and
  every core upgrade could break an app.
- **Each app ships its own complete theme.** Several colour schemes in one host.
- **Branding as code changes in core.** Every host would carry a fork of Lattice.

## As built (20 October 2026)

Built and enforced at startup (`create_app` refuses a violation):

- **Host theme** (`static/theme.css`): only the allowed brand tokens, in `:root` and
  `[data-mode="dark"]` alike, inside `@layer settings`; and `@font-face` for font files
  from the host folder only, with font descriptors and nothing else.
- **App stylesheets**: `@layer components`, every selector under `[data-app="{key}"]`, no
  colour literals, `--p-*` tokens or `!important`.
- **Logos, name and favicon**: `LATTICE_BRAND_LOGO_LIGHT`, `_DARK`, `_SHOW_NAME`, and
  `LATTICE_BRAND_FAVICON` (empty: the logos).
- **An app's accent** is a tone named in its manifest (`accent="warning"`), not a colour:
  the shell marks the app's rail entry and its page titles, and `--app-accent` is set on
  its pages. A token in the app's stylesheet could not reach the rail, which is outside
  the app's pages, so the manifest names it.
- **Icons**: one registry, app icons namespaced, a host may replace the core set.
- **Templates**: a host may override the sign-in, error and home pages and the three
  notification email templates (`email/notification.txt`, `digest.txt`, `test.txt`, ADR
  0016); apps cannot override core templates. Named slots, with unknown names refused.
- **Colours by meaning**: columns and charts name tones (ADR 0015 adds colour modes that
  follow `--brand`).

Deferred until an app needs them: **rail groups** chosen by the host, and **keyboard
shortcuts registered by apps** with clash checks.
