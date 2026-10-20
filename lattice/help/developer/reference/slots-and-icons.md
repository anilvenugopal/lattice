---
title: Slots and icons
summary: The named slots in the core templates and the core icon set.
order: 80
keywords: slot icon svg topbar statusbar
---

> [!NOTE]
> Generated from `lattice/kernel/slots.py` and `lattice/kernel/icons.py` by `lattice docs build`. Change the code, not this page.

## Slots

Named slots in the core templates (ADR 0010).

A host adds a template to a slot with `create_app(slot_templates={name: [template]})`; an app with `AppManifest(slots={name: "{key}/template.html"})`.

| Slot | Rendered in |
|---|---|
| `topbar.end` | `base/shell.html` |
| `statusbar.start` | `base/shell.html` |
| `statusbar.end` | `base/shell.html` |
| `signin.footer` | `auth/login.html` |
| `home.sections` | `pages/home.html` |
| `help.menu` | `base/shell.html` |

## Icons

Inline SVG icons (Lucide-style strokes, 24px grid). Use `{{ icon("name") }}` in templates.

The core set:

`activity`, `alert`, `archive`, `arrow-down`, `arrow-up`, `assign`, `bookmark`, `check`, `chevron-down`, `chevron-left`, `chevron-right`, `clock`, `columns`, `download`, `edit`, `external`, `flag`, `home`, `inbox`, `info`, `key`, `keyboard`, `layout`, `link`, `lock`, `logout`, `mail`, `mail-open`, `monitor`, `moon`, `more`, `panel-right`, `paperclip`, `pin`, `play`, `plus`, `queue`, `refresh`, `retry`, `search`, `settings`, `shield`, `star`, `stop`, `sun`, `trash`, `user`, `users`, `x`.
