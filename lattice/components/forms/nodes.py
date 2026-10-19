"""Turns a JSON Schema and a document into form fields, reads a form post back into JSON, and
validates it.

Every field's form name is its path in the document, as a JSON Pointer under `data`:
`data/address/city`, `data/items/0/name`. Array items are numbered as the form shows them;
a reordered or removed item is renumbered on the next render.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError, best_match

from lattice.components.forms.schema import kind_of, resolve, split_null

ROOT = "data"
MISSING = object()          # a field left empty: the property is left out of the document

_FORMAT_WIDGETS = {"date": "date", "date-time": "datetime-local", "time": "time", "email": "email",
                   "uri": "url", "url": "url"}


def child_name(parent: str, key: str | int) -> str:
    return f"{parent}/{str(key).replace('~', '~0').replace('/', '~1')}"


def humanize(key: str) -> str:
    text = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", str(key)).replace("_", " ").strip()
    return text[:1].upper() + text[1:]


@dataclass
class Node:
    """One field, fieldset or list of the form, as components/json_form.html draws it."""

    kind: str                       # object | array | string | number | integer | boolean | enum
                                    # | const | variant | json
    name: str                       # form name: data/address/city
    label: str
    help: str = ""
    required: bool = False
    nullable: bool = False
    value: Any = None               # scalars: the value as the input shows it
    widget: str = ""                # string: text, textarea, date, datetime-local, email, url, time
    placeholder: str = ""
    error: str = ""
    attrs: dict = field(default_factory=dict)       # HTML hints: min, max, step, maxlength…
    children: list[Node] = field(default_factory=list)  # object: properties; array: items
    sections: list[tuple[str, list[Node]]] = field(default_factory=list)  # object, from ui hints
    other: dict = field(default_factory=dict)       # object: keys the schema does not describe
    extensible: bool = False        # object: offer "Add field"
    options: list[tuple[str, str]] = field(default_factory=list)  # enum: (JSON value, label)
    variants: list[str] = field(default_factory=list)  # variant: option labels
    variant: int = 0                # variant: the chosen option
    can_add: bool = True            # array: below maxItems
    can_remove: bool = True         # array: above minItems
    readonly: bool = False


@dataclass
class Context:
    root: dict                      # the whole schema, for $ref
    ui: dict                        # hints by path ("" for the document, "address/city")
    errors: dict                    # form name -> message
    extensible: bool = False        # the schema was inferred: objects take new fields
    chosen: dict = field(default_factory=dict)   # form name -> variant index from the post


# ── Building the fields ─────────────────────────────────────────────────────

def build(schema: Any, value: Any, ctx: Context, name: str = ROOT, key: str = "",
          ui_path: str = "", required: bool = False, label: str = "") -> Node:
    s, nullable = split_null(resolve(schema, ctx.root), ctx.root)
    kind = kind_of(s)
    if value is None and "default" in s and kind not in ("object", "array"):
        value = s["default"]                         # a field the document lacks
    hints = ctx.ui.get(ui_path, {})
    node = Node(kind=kind, name=name, required=required, nullable=nullable,
                label=hints.get("label") or s.get("title") or label or humanize(key),
                help=hints.get("help") or s.get("description", ""),
                placeholder=hints.get("placeholder", ""), error=ctx.errors.get(name, ""),
                readonly=bool(hints.get("readonly") or s.get("readOnly")))

    if kind == "object":
        props = s.get("properties", {})
        data = value if isinstance(value, dict) else {}
        order = hints.get("order") or list(props)
        keys = [k for k in order if k in props] + [k for k in props if k not in order]
        by_key = {}
        for k in keys:
            by_key[k] = build(props[k], data.get(k), ctx, child_name(name, k), k,
                              f"{ui_path}/{k}".lstrip("/"), k in s.get("required", []))
        node.children = list(by_key.values())
        node.other = {k: v for k, v in data.items() if k not in props}
        node.extensible = ctx.extensible and s.get("additionalProperties", True) is not False
        node.value = isinstance(value, dict)          # an optional object the document has
        placed: set = set()
        for title, fields in hints.get("sections", []):
            members = [by_key[k] for k in fields if k in by_key and k not in placed]
            placed |= {n for n in fields}
            node.sections.append((title, members))
        if node.sections and len(placed) < len(keys):
            node.sections.append(("", [by_key[k] for k in keys if k not in placed]))
    elif kind == "array":
        items = s.get("items", {})
        values = value if isinstance(value, list) else []
        item_label = hints.get("item_label") or resolve(items, ctx.root).get("title") or "Item"
        node.children = [build(items, v, ctx, child_name(name, i), str(i), ui_path, True)
                         for i, v in enumerate(values)]
        for i, child in enumerate(node.children):
            child.label = f"{item_label} {i + 1}"
        node.can_add = len(values) < s.get("maxItems", 10_000)
        node.can_remove = len(values) > s.get("minItems", 0)
        node.attrs = {"item_label": item_label}
    elif kind == "variant":
        branches = [resolve(b, ctx.root) for b in s.get("oneOf") or s.get("anyOf")]
        node.variants = [_branch_label(b, s, i) for i, b in enumerate(branches)]
        node.variant = ctx.chosen.get(name, _pick(branches, s, value, ctx.root))
        node.variant = min(node.variant, len(branches) - 1)
        node.children = [build(branches[node.variant], value, ctx, name, key, ui_path, required,
                               node.label)]
    elif kind in ("enum", "const"):
        choices = s["enum"] if kind == "enum" else [s["const"]]
        labels = hints.get("labels", {})
        node.options = [(json.dumps(v), labels.get(str(v), str(v))) for v in choices]
        node.value = json.dumps(value if kind == "enum" else s["const"]) if (
            value is not None or kind == "const") else ""
        node.readonly = node.readonly or kind == "const"
    elif kind == "boolean":
        node.value = bool(value)
    elif kind in ("number", "integer"):
        node.value = "" if value is None else value
        node.attrs = {k: s[src] for k, src in (("min", "minimum"), ("max", "maximum"))
                      if src in s}
        node.attrs["step"] = 1 if kind == "integer" else s.get("multipleOf", "any")
    elif kind == "string":
        node.widget = (hints.get("widget") or s.get("x-widget")
                       or _FORMAT_WIDGETS.get(s.get("format", ""), "text"))
        node.value = "" if value is None else str(value)
        if node.widget == "datetime-local" and node.value:
            node.value = node.value.replace(" ", "T")[:16]
        node.attrs = {k: s[src] for k, src in (("minlength", "minLength"),
                      ("maxlength", "maxLength"), ("pattern", "pattern")) if src in s}
    else:
        node.value = "" if value is None else json.dumps(value, indent=2)
    return node


def _discriminator(schema: dict) -> str:
    d = schema.get("discriminator")
    return d.get("propertyName", "") if isinstance(d, dict) else ""


def _branch_label(branch: dict, schema: dict, i: int) -> str:
    prop = _discriminator(schema)
    const = branch.get("properties", {}).get(prop, {}).get("const") if prop else None
    return branch.get("title") or (str(const) if const is not None else f"Option {i + 1}")


def _pick(branches: list[dict], schema: dict, value: Any, root: dict) -> int:
    """The branch the value belongs to: by its discriminator, else the first it validates against."""
    prop = _discriminator(schema)
    if prop and isinstance(value, dict) and prop in value:
        for i, b in enumerate(branches):
            if b.get("properties", {}).get(prop, {}).get("const") == value[prop]:
                return i
    if value is not None:
        defs = {k: root[k] for k in ("$defs", "definitions") if k in root}
        for i, b in enumerate(branches):
            if Draft202012Validator({**b, **defs}).is_valid(value):
                return i
    return 0


# ── Reading a post ──────────────────────────────────────────────────────────

def parse(schema: Any, form, ctx: Context, name: str = ROOT, required: bool = False) -> Any:
    """The document the form describes, or MISSING for an empty optional field.

    Values that don't convert (a word in a number field, malformed JSON) are recorded in
    ctx.errors and left out.
    """
    s, nullable = split_null(resolve(schema, ctx.root), ctx.root)
    kind = kind_of(s)
    raw = _last(form, name)

    if kind == "object":
        out = {}
        for k, sub in s.get("properties", {}).items():
            v = parse(sub, form, ctx, child_name(name, k), k in s.get("required", []))
            if v is not MISSING:
                out[k] = v
        other = _last(form, f"{name}/__other")
        if other:
            out = {**json.loads(other), **out}
        for new_key, new_value in _added(form, name, ctx):
            out.setdefault(new_key, new_value)
        if not out and not required and _last(form, f"{name}/__present") is None:
            return None if nullable else MISSING
        return out
    if kind == "array":
        indexes = _indexes(form, name)
        items = [parse(s.get("items", {}), form, ctx, child_name(name, i), True) for i in indexes]
        return [v for v in items if v is not MISSING]
    if kind == "variant":
        branches = s.get("oneOf") or s.get("anyOf")
        chosen = _int(_last(form, f"{name}/__variant"), 0)
        ctx.chosen[name] = min(chosen, len(branches) - 1)
        return parse(branches[ctx.chosen[name]], form, ctx, name, required)
    if kind == "const":
        return s["const"]
    if kind == "boolean":
        values = form.getlist(name)
        return MISSING if not values else values[-1] == "true"
    if raw is None or raw == "":
        return None if nullable and raw == "" else MISSING
    try:
        if kind == "enum":
            return json.loads(raw)
        if kind == "integer":
            return int(raw)
        if kind == "number":
            number = float(raw)
            return int(number) if number.is_integer() and "." not in raw else number
        if kind == "string":
            if s.get("format") == "date-time" and re.fullmatch(r".{16}", raw):
                return raw + ":00Z"
            return raw
        return json.loads(raw)
    except ValueError:
        ctx.errors[name] = {"integer": "Enter a whole number.", "number": "Enter a number."}.get(
            kind, "Not valid JSON." if kind == "json" else "Choose one of the options.")
        return MISSING


def _last(form, name: str):
    values = form.getlist(name)
    return values[-1] if values else None


def _int(raw, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _indexes(form, name: str) -> list[int]:
    """Item numbers under an array's name, in the order the form posted them."""
    prefix = name + "/"
    seen: dict[int, None] = {}
    for key in form:
        if key.startswith(prefix):
            head = key[len(prefix):].split("/", 1)[0]
            if head.isdigit():
                seen.setdefault(int(head), None)
    return list(seen)


def _added(form, name: str, ctx: Context):
    """Properties added with "Add field": (key, value) pairs, typed as chosen."""
    keys = form.getlist(f"{name}/__new/key")
    kinds = form.getlist(f"{name}/__new/type")
    values = form.getlist(f"{name}/__new/value")
    for i, (k, t, v) in enumerate(zip(keys, kinds, values, strict=False)):
        k = k.strip()
        if not k:
            continue
        try:
            yield k, {"string": lambda x: x, "number": float, "integer": int,
                      "boolean": lambda x: x == "true", "object": lambda x: {},
                      "array": lambda x: []}[t](v)
        except (KeyError, ValueError):
            ctx.errors[f"{name}/__new/{i}"] = f"{k}: not a valid {t}."


# ── Validation ──────────────────────────────────────────────────────────────

def validate(schema: dict, data: Any) -> tuple[dict, list[str]]:
    """Errors by form name, and errors that belong to no field, from jsonschema (Draft 2020-12)."""
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    by_field: dict[str, str] = {}
    general: list[str] = []
    for error in validator.iter_errors(data):
        if error.validator in ("oneOf", "anyOf") and error.context:
            # A nullable field fails its null branch too; report the other branch's reason.
            real = [e for e in error.context
                    if not (e.validator == "type" and e.validator_value == "null")]
            error = best_match(real or error.context)
        name = ROOT
        for part in error.absolute_path:
            name = child_name(name, part)
        if error.validator == "required":
            for missing in error.validator_value:
                if isinstance(error.instance, dict) and missing not in error.instance:
                    by_field.setdefault(child_name(name, missing), "Required.")
            continue
        message = _message(error)
        if name == ROOT:
            general.append(message)
        else:
            by_field.setdefault(name, message)
    return by_field, general


def _message(error: ValidationError) -> str:
    v, n = error.validator, error.validator_value
    return {
        "type": lambda: f"Must be {'an' if str(n)[:1] in 'aeiou' else 'a'} {n}.",
        "minLength": lambda: f"At least {n} characters.",
        "maxLength": lambda: f"At most {n} characters.",
        "minimum": lambda: f"At least {n}.",
        "maximum": lambda: f"At most {n}.",
        "exclusiveMinimum": lambda: f"More than {n}.",
        "exclusiveMaximum": lambda: f"Less than {n}.",
        "pattern": lambda: "Doesn't match the expected format.",
        "format": lambda: f"Not a valid {n}.",
        "enum": lambda: "Choose one of the options.",
        "const": lambda: f"Must be {n}.",
        "minItems": lambda: f"Add at least {n}.",
        "maxItems": lambda: f"At most {n}.",
        "uniqueItems": lambda: "Items must all be different.",
        "additionalProperties": lambda: error.message,
    }.get(v, lambda: error.message)()
