"""Named slots in the core templates (ADR 0010).

Hosts and apps add small pieces (a help link, an environment banner, a legal
notice) without overriding a core template. A core template renders a slot with
`{{ slot("topbar.end") }}`; each registered template is rendered there in order,
with the page's context.
"""

from __future__ import annotations

from jinja2 import pass_context
from markupsafe import Markup

SLOT_NAMES = ("topbar.end", "statusbar.start", "statusbar.end", "signin.footer",
              "home.sections", "help.menu")

_SLOTS: dict[str, list[str]] = {}


def reset() -> None:
    _SLOTS.clear()


def add(name: str, template: str) -> None:
    if name not in SLOT_NAMES:
        raise ValueError(f"Unknown slot {name!r}; slots are {', '.join(SLOT_NAMES)}")
    _SLOTS.setdefault(name, []).append(template)


@pass_context
def render_slot(context, name: str) -> Markup:
    env = context.environment
    return Markup("".join(env.get_template(t).render(context.get_all())
                          for t in _SLOTS.get(name, [])))
