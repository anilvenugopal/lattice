---
title: Branding a host
summary: Give a host its own name, logos, colours and fonts, replace the sign-in, error and home pages, and add to slots.
order: 30
keywords: brand branding logo theme colours colors fonts theme.css override sign-in page slots icons white label
---

The host owns the brand. Apps style only their own pages, so a host can run
apps from different teams and still look like one product.

| To change | Use |
|---|---|
| The name and logos | Settings |
| Colours and fonts | `static/theme.css` in the host folder |
| The sign-in, error or home page | A template override in the host folder |
| A small addition, such as a banner or link | A slot |
| Core icons | `icons_override` |

Everything except the settings lives in the host folder, passed as
`create_app(…, host_dir=Path(__file__).parent)`:

```text
helpdesk_host/
  main.py
  static/
    theme.css             brand tokens, light and dark
    logo-light.svg
    logo-dark.svg
  templates/
    auth/login.html       optional: replaces the sign-in page
    host/banner.html      templates for slots
```

## Name and logos

| Setting | Is |
|---|---|
| `LATTICE_APP_NAME` | The name in the top bar, page titles and the sign-in page |
| `LATTICE_BRAND_LOGO_LIGHT` | The logo for light mode; also the favicon, unless one is set |
| `LATTICE_BRAND_LOGO_DARK` | The logo for dark mode; also the favicon in dark mode |
| `LATTICE_BRAND_FAVICON` | The browser tab icon, when it should differ from the logos (`.ico`, `.svg` or `.png`) |
| `LATTICE_BRAND_SHOW_NAME` | `false` when the logo images already contain the name |

Files in the host's `static/` folder are served at `/static/host/`, so:

```bash
LATTICE_APP_NAME=Helpdesk
LATTICE_BRAND_LOGO_LIGHT=/static/host/logo-light.svg
LATTICE_BRAND_LOGO_DARK=/static/host/logo-dark.svg
```

## Colours and fonts

`static/theme.css` redefines brand tokens, for both themes:

```css
@layer settings {
  :root {
    --brand: #0B7A75;
    --brand-hover: #08605C;
    --link: #0B7A75;
    --font-ui: "Inter", system-ui, sans-serif;
  }
  [data-mode="dark"] {
    --brand: #3FB8B2;
    --brand-hover: #5FCBC6;
    --link: #3FB8B2;
    --font-ui: "Inter", system-ui, sans-serif;
  }
}
```

It loads after Lattice's CSS. `create_app` refuses to start unless:

- the file declares `@layer settings`;
- its only selectors are `:root` and `[data-mode="dark"]`;
- it sets only allowed tokens, and no other properties;
- light and dark set the same tokens;
- colours appear only as token values.

**Allowed tokens:**

- `--brand`, `--brand-hover`, `--brand-alt`;
- `--accent`, `--text-on-accent`, `--link`;
- `--font-ui`, `--font-mono`;
- any `--surface-*` or `--text-*` token.

[Reference › Design tokens](../reference/tokens.md) marks them all, with their
default values.

**Your own font files.** `theme.css` may load fonts with `@font-face`, from the
host folder only (a path relative to `theme.css`, or `/static/host/…`), with
font descriptors and nothing else:

```css
@font-face { font-family: "Brand Sans"; src: url("fonts/brand-sans.woff2") format("woff2");
             font-weight: 400 700; font-display: swap; }
@layer settings {
  :root { --font-ui: "Brand Sans", system-ui, sans-serif; }
  [data-mode="dark"] { --font-ui: "Brand Sans", system-ui, sans-serif; }
}
```

Fonts from other sites (a font CDN) are refused: the site keeps working with no
outside requests. Keep the system fonts as fallbacks.

## Replacing whole pages

A host may replace three core templates, by putting a file with the same path
in its `templates/` folder:

| Template | Is |
|---|---|
| `auth/login.html` | The sign-in page |
| `base/error.html` | The error page (403, 404, 500) |
| `pages/home.html` | The home page |
| `email/notification.txt` | The email for one notification ([Notifications](../building-apps/notifications.md)) |
| `email/digest.txt` | The daily summary email |
| `email/test.txt` | The test email from Administration › Email |

Start from Lattice's own template in `lattice/templates/` and keep its blocks
and variables. The email templates are plain text: they receive `base` (the
site's address), `app_name` and their own values (`title`, `notification_id`,
`kind_label`; `items` for the summary), and should keep to titles and links, never
record content. Any other template in the host folder must be under `host/`;
`create_app` refuses to start otherwise.

## Slots

A slot adds a small piece to a core page without replacing it:

```python
app = create_app(apps=[…], host_dir=HERE,
                 slot_templates={"statusbar.start": "host/banner.html",
                                 "help.menu": "host/help_links.html"})
```

```jinja
{# templates/host/banner.html #}
<span class="badge tone-warning">Training environment: data is reset nightly</span>
```

| Slot | Where |
|---|---|
| `topbar.end` | The right of the top bar |
| `statusbar.start`, `statusbar.end` | The status bar |
| `signin.footer` | Under the sign-in form |
| `home.sections` | The end of the home page |
| `help.menu` | The Help menu, after Lattice's items |

A slot template receives the page's context. Apps can fill slots too, with
`AppManifest(slots={…})` and templates in their own folder.

## Icons

`icons_override` replaces core icons by name, everywhere:

```python
create_app(apps=[…], icons_override={"search": '<circle cx="10" cy="10" r="6"/><path d="m20 20-5-5"/>'})
```

Values are SVG markup on a 24px grid, drawn with `currentColor`. Only existing
icon names can be replaced; the list is in
[Reference › Slots and icons](../reference/slots-and-icons.md).
