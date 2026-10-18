---
title: Styling
summary: The five CSS layers, design tokens, light and dark themes, and how an app adds styles of its own.
order: 50
keywords: css itcss layers tokens theme dark light density stylesheet data-app scoped colour utilities
---

Most apps need no CSS: the macros, page classes and grid cover the common
pages. When an app does need styles, they go in its own stylesheet, follow
the rules below, and are checked when the host starts.

## The five layers

Lattice's CSS is split into five ITCSS layers. `lattice/static/css/app.css`
declares their order:

```css
@layer settings, base, layout, components, utilities;
```

A rule in a later layer always beats a rule in an earlier one, whatever its
specificity. Specificity battles and `!important` are not needed.

| Layer | Files | Contains | Must not contain |
|---|---|---|---|
| 1 settings | `1-settings/tokens.css` | Custom properties only, in three tiers (below) | Selectors other than `:root` and the theme hooks |
| 2 base | `2-base/base.css` | The reset and bare elements (`body`, `a`, `kbd`, `svg`) | Class selectors |
| 3 layout | `3-layout/shell.css`, `page.css` | Shell regions, page containers, layout objects (`.stack`, `.cluster`, `.grid-2`) | Component visuals |
| 4 components | `4-components/*.css`, one file per family | Named pieces: `.btn`, `.card`, `.dg` (the grid), `.palette`, `.help`. App stylesheets join this layer | Colour literals, primitive tokens, `!important` |
| 5 utilities | `5-utilities/utilities.css` | Single-purpose `.u-*` helpers: `u-muted`, `u-mono`, `u-text-right` | Anything else |

`tests/test_css_architecture.py` enforces, for Lattice's own CSS:

- colour literals and `--p-*` tokens appear only in settings;
- base has no class selectors;
- utilities hold only `.u-*` classes, and are the only place `!important` is allowed;
- every file is imported once, into the layer that matches its folder.

## Tokens

Components never use colour values. They use tokens: `var(--text-2)`,
`var(--surface-panel)`, `var(--sp-3)`. Tokens come in three tiers:

| Tier | Example | Who uses it |
|---|---|---|
| **Primitives** `--p-*` | `--p-navy-600: #234484` | Only `tokens.css`. Private |
| **Semantic** | `--surface-page`, `--text-2`, `--border`, `--brand`, `--sp-3`, `--fs-sm`, `--r-md` | Every component and app stylesheet |
| **Component** | `--rail-w`, `--row-pad-y`, `--toast-bg` | The component family that owns it; always defined from semantic tokens |

Every token and its light and dark value is listed in
[Reference › Design tokens](../reference/tokens.md).

**Adding a colour to Lattice:**

1. Add a primitive, if the colour is new.
2. Give it a semantic token in **both** theme blocks of `tokens.css`, light and dark.
3. Use the semantic token in components.

## Light, dark and density

- **Theme.** `[data-mode="dark"]` on `<html>` switches to the dark theme. It
  remaps the semantic tier and nothing else, so anything built from semantic
  tokens works in both themes without change.
- **Density.** `[data-density="compact"]` remaps the component tokens
  `--row-pad-y` and `--control-h`.

The user chooses both in Account › Preferences.

## Tones

`.tone-neutral`, `.tone-info`, `.tone-success`, `.tone-warning`,
`.tone-danger` and `.tone-accent` each set three tokens:

- `--tone-bg`: the background;
- `--tone-fg`: the text;
- `--tone-bd`: the border.

`badge`, `tag`, `alert` and `code-block` read them. A new component that
needs tones reads the same three tokens.

## An app's own stylesheet

Declare the folder and the file in the manifest:

```python
APP = AppManifest(
    key="helpdesk", …,
    static=HERE / "static",            # served at /static/helpdesk/
    stylesheets=["helpdesk.css"],      # loaded on every page
)
```

Write the stylesheet in the components layer, with every selector scoped to the
app:

```css
/* Helpdesk styles. Components layer, scoped to the helpdesk's pages. */
@layer components {

[data-app="helpdesk"] .sla { display: flex; align-items: center; gap: var(--sp-2); }
[data-app="helpdesk"] .sla__clock { color: var(--text-3); font-size: var(--fs-sm); }
[data-app="helpdesk"] .sla.is-breached .sla__clock { color: var(--danger); }

}
```

The shell puts `data-app="{key}"` on `<main>` and on side panels for the app's
pages, so these rules apply only there. `create_app` refuses to start if the
stylesheet breaks any of these rules:

- it must declare `@layer components`;
- every selector must start with `[data-app="{key}"]`;
- no colour literals (`#hex`, `rgb()`, `hsl()`, named colours);
- no `--p-*` primitive tokens;
- no `!important`.

An app cannot restyle the shell, another app or Lattice's components. If a
component needs to look different everywhere, change it in Lattice.

## Templates

Templates carry no inline colours or styles, except computed widths such as a
grid column's `width`. Use the layout helpers, the macros and, for small
adjustments, the `.u-*` utilities.

## Host themes

The brand colours and fonts belong to the host, not to apps. See
[Branding a host](../running/branding.md).
