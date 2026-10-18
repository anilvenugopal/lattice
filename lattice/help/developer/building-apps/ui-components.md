---
title: UI components
summary: The shared macros, buttons, tones and icons every page is built from, plus keyboard and accessibility rules.
order: 40
keywords: macros components buttons tones badge icon keyboard shortcuts accessibility aria ui kit
---

Pages are built from shared macros and classes, not from markup of their own.
**Administration › UI kit** in a running host shows every one of them, in both
themes. Every macro and its arguments are listed in
[Reference › Macros](../reference/macros.md).

## Macros

Import the macros a template uses:

```jinja
{% from "components/macros.html" import page_header, card, prop_list, badge_for %}
```

Import `signout_button` and `session_table` `with context`, because they call
`csrf_field()`.

| Macro | Use for |
|---|---|
| `page_header(title, subtitle, badge_text, badge_tone)` | Every page title. Put buttons in a `call` block |
| `card(title, subtitle, flush)` | Grouping content. `flush=True` for a table inside |
| `prop_list(items, columns)` | A record's read-only fields: a list of `(label, value)` pairs |
| `stat(label, value, href, tone)` | A count on a dashboard |
| `empty_state(title, text, icon_name)` | Nothing to show |
| `timeline(events)` | A record's audit history, from `audit.history(...)` |
| `badge(text, tone)` | A status or category |
| `badge_for(column, value)` | A grid column's value with its declared label and tone |
| `alert(tone, text)`, or `{% call alert(tone) %}` | A message inside a page |
| `progress(value)` | A 0–100 bar with its percentage |
| `user_chip(name, sub)` | A person, with initials |
| `field`, `select_field`, `checkbox` | Form inputs with a label, hint and error |
| `pref_row(label, hint)`, `segmented(name, options, value)`, `select_input(name, options, value)` | Rows on a settings page |
| `brand(class)` | The logo and app name |
| `signout_button(label, class)` | Every sign-out control |
| `session_table(sessions, current_id, revoke)` | A list of sign-in sessions |

If a page needs something these do not cover, add a macro to
`components/macros.html`, and to the UI kit page, so every app can use it.
Do not write the markup inline in an app.

## Buttons

| Class | Use |
|---|---|
| `.btn.btn--primary` | The main action of a region. One per region |
| `.btn` | Other actions |
| `.btn--ghost` | Low-emphasis actions, such as Cancel and Back |
| `.btn--danger`, `.btn--danger-ghost` | Destructive actions. Always ask for confirmation |
| `.btn--link` | An action that looks like a link |
| `.btn--sm`, `.btn--lg`, `.btn--block` | Size and width |
| `.icon-btn` | An icon-only button. It needs `aria-label` and a `data-tip="…"` tooltip |

Button labels are verbs: "Approve", "Run job", "Save changes".

## Tones

Every coloured status uses one of six tones:

| Tone | Means |
|---|---|
| `neutral` | The default; no particular state |
| `info` | In progress, or for information |
| `success` | Done, healthy |
| `warning` | Needs attention |
| `danger` | Failed, or destructive |
| `accent` | A highlight, such as ownership or a special category |

Tones are the classes `tone-neutral` … `tone-accent` on `badge`, `tag`,
`alert` and `code-block`. Map each status value to one tone, once, in the
grid column's `tones`.

## Icons

```jinja
{{ icon("check") }}            {# a core icon, 16px #}
{{ icon("chevron-left", 14) }}  {# another size #}
{{ icon("helpdesk:ticket") }}  {# the app's own icon #}
```

Icons are inline SVG strokes on a 24px grid. They draw with `currentColor`, so
they follow the text colour and the theme. The core set is listed in
[Reference › Slots and icons](../reference/slots-and-icons.md).

An app adds its own icons in its manifest. The value is the SVG markup inside
`<svg>`:

```python
icons={"ticket": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M9 6v12"/>'}
```

Use them as `icon("helpdesk:ticket")`, and as `icon="helpdesk:ticket"` on a
`NavNode` or the manifest.

## Times

Store timestamps as naive UTC. Render them with `time_tag(value)`:

- the browser shows the value in the user's time zone;
- it follows their preference: relative ("3h ago") or absolute.

`time_tag(value, "date")` and `time_tag(value, "datetime")` always show an
absolute date.

## Keyboard

| Keys | Do |
|---|---|
| Ctrl/⌘ J | Search and jump (Ctrl+J) |
| F1 | Help for this page |
| ? | List the shortcuts |
| / | Focus the grid's search |
| ↑ ↓ or J K | Move between grid rows; the panel follows |
| Space or X | Select the row |
| Shift + click | Select a range |
| Enter | Open the row |
| Ctrl/⌘ A | Select every row on the page |
| Esc | Close the panel, then clear the selection |

New global keys belong in `static/js/app.js`, grid keys in `static/js/grid.js`.
Add both to the shortcuts dialog in `base/shell.html`.

## Accessibility

- **Labels.** Icon-only controls carry an `aria-label`.
- **Focus.** It is always visible (`--focus-ring`). Never remove an outline
  without the token replacement.
- **Colour.** It is never the only signal: badges have text, and a disabled
  action has a title that says why.
- **Keyboard.** Every feature works from the keyboard alone.
