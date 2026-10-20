---
title: Macros
summary: The template macros in components/macros.html and their arguments.
order: 60
keywords: jinja template macro page_header card badge field
---

> [!NOTE]
> Generated from `lattice/templates/components/macros.html` by `lattice docs build`. Change the code, not this page.

Shared Jinja macros for app templates. Import the ones a template uses:

```jinja
{% from "components/macros.html" import page_header, card, badge_for %}
```

Macros that call `csrf_field()` (`signout_button`, `session_table`) are imported `with context`.

## page_header

```jinja
page_header(title, subtitle="", badge_text="", badge_tone="neutral")
```

Page title row. Put buttons in a call block, e.g. {% call page_header("Users", "Accounts and roles") %}<a class="btn">…</a>{% endcall %}

## badge

```jinja
badge(text, tone="neutral")
```

tone: neutral | info | success | warning | danger | accent

## brand

```jinja
brand(class="")
```

The application logo (light and dark variants from settings) and, optionally, its name. CSS (4-components/brand.css) shows the variant that matches the current theme.

## alert

```jinja
alert(tone, text="")
```

Inline message. tone: info | success | warning | danger. Text, or a call block for richer content.

## signout_button

```jinja
signout_button(label="Sign out", class="btn btn--link")
```

The sign-out form. One POST route (/auth/logout) for every sign-out control.

## progress

```jinja
progress(value)
```

## badge_for

```jinja
badge_for(col, value)
```

Badge for a grid Column value: label and tone come from the Column definition.

## empty_state

```jinja
empty_state(title, text="", icon_name="layout")
```

## prop_list

```jinja
prop_list(items, columns=1)
```

items: list of (label, value) pairs. Values may be Markup.

## card

```jinja
card(title="", subtitle="", flush=False)
```

## stat

```jinja
stat(label, value, href="", tone="")
```

## field

```jinja
field(name, label, value="", type="text", error="", hint="", required=False, placeholder="", attrs="")
```

Form fields. `error` shows under the input and marks it invalid.

## select_field

```jinja
select_field(name, label, options, value="", error="", hint="", required=False, blank="")
```

## pref_row

```jinja
pref_row(label, hint="")
```

A settings row: label and hint on the left, the control (call block) on the right.

## segmented

```jinja
segmented(name, options, value, onchange="")
```

2–4 mutually exclusive options as a segmented control. onchange: optional inline JS.

## select_input

```jinja
select_input(name, options, value)
```

A bare select (no label wrapper), for pref_row and toolbars.

## session_table

```jinja
session_table(sessions, current_id=None, revoke=False)
```

Active sessions. current_id marks "This device"; revoke=True adds per-row sign-out buttons.

## checkbox

```jinja
checkbox(name, label, checked=False, value="on", hint="", disabled=False)
```

## timeline

```jinja
timeline(events)
```

Audit timeline. events: rows from audit.history().

## user_chip

```jinja
user_chip(name, sub="")
```

## folder_picker

```jinja
folder_picker(name, value="", text="", required=False)
```

A folder on a mounted share (ADR 0017): the value is "{store}:{path}", chosen with Browse… in a dialog that lists one folder at a time (static/js/folders.js). `text` is how the value reads (folder_label(value)).
