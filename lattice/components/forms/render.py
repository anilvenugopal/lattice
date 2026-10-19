"""Build a form for a document, read a post back, and the shared endpoint for edits that change
the form's shape (add or remove an array item, choose a variant, add a field, switch tabs,
apply another schema).

    form = build_form(request, SPEC, data)                  # GET: show it
    result = parse_form(request, SPEC, await request.form()) # POST: read and validate
    if result.errors: …re-render result.form with status 400…
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from lattice.components.forms import nodes
from lattice.components.forms.schema import default_for, infer, kind_of, resolve, split_null
from lattice.components.forms.spec import FormSpec, SchemaDef, as_json_schema
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user
from lattice.kernel.web import render

FORMS: dict[str, FormSpec] = {}
SCHEMAS: dict[str, SchemaDef] = {}

router = APIRouter(prefix="/_form", dependencies=[Depends(csrf_protect)])


def register_form(spec: FormSpec) -> None:
    if spec.key in FORMS and FORMS[spec.key] is not spec:
        raise ValueError(f"Form key {spec.key!r} is already registered")
    FORMS[spec.key] = spec


def register_schema(schema: SchemaDef) -> None:
    if schema.id in SCHEMAS and SCHEMAS[schema.id] is not schema:
        raise ValueError(f"Schema id {schema.id!r} is already registered")
    SCHEMAS[schema.id] = schema


@dataclass
class FormResult:
    data: Any                       # the document the form describes
    errors: dict                    # form name -> message; empty when valid
    general: list[str]              # errors that belong to no one field
    form: dict                      # context to re-render the form with these values and errors
    schema_id: str = ""             # the registered schema the user applied, if any

    @property
    def ok(self) -> bool:
        return not self.errors and not self.general


@dataclass
class _Resolved:
    schema: dict
    ui: dict
    schema_id: str
    inferred: bool = False
    hints: dict = field(default_factory=dict)


def _resolve(spec: FormSpec, data: Any, schema_id: str = "") -> _Resolved:
    """The schema in force: one the user applied, the spec's, the document's $schema, or inferred."""
    if schema_id and (spec.switchable or schema_id == spec.schema) and schema_id in SCHEMAS:
        found = SCHEMAS[schema_id]
        return _Resolved(found.json_schema(), {**found.ui, **spec.ui}, schema_id)
    if isinstance(spec.schema, str):
        found = SCHEMAS[spec.schema]
        return _Resolved(found.json_schema(), {**found.ui, **spec.ui}, spec.schema)
    if spec.schema is not None:
        return _Resolved(as_json_schema(spec.schema), spec.ui, "")
    named = data.get("$schema") if isinstance(data, dict) else None
    if named in SCHEMAS:
        found = SCHEMAS[named]
        return _Resolved(found.json_schema(), {**found.ui, **spec.ui}, named)
    return _Resolved(infer(data if data is not None else {}), spec.ui, "", inferred=True)


def build_form(request: Request, spec: FormSpec, data: Any, *, errors: dict | None = None,
               general: list[str] | None = None, schema_id: str = "", mode: str = "form",
               chosen: dict | None = None, json_text: str | None = None) -> dict:
    """Context for components/json_form.html: render it with `json_form(form, …)`."""
    if not request.state.user.can(spec.permission):
        raise HTTPException(403)
    r = _resolve(spec, data, schema_id)
    ctx = nodes.Context(root=r.schema, ui=r.ui, errors=errors or {}, extensible=r.inferred,
                        chosen=chosen or {})
    return {
        "spec": spec,
        "root": nodes.build(r.schema, data, ctx, label=r.schema.get("title", "")),
        "mode": mode if spec.json_tab else "form",
        "json": json_text if json_text is not None else json.dumps(data, indent=2, default=str),
        "schema_id": r.schema_id,
        "schemas": [(s.id, s.title) for s in SCHEMAS.values()] if spec.switchable else [],
        "general": general or [],
        "errors": errors or {},
    }


def _read(spec: FormSpec, form, schema_id: str, mode: str) -> tuple[Any, dict, dict, str | None]:
    """(data, errors, chosen variants, the JSON text when it doesn't parse) without validating."""
    if mode == "json":
        text = form.get("__json", "")
        try:
            return json.loads(text or "null"), {}, {}, None
        except ValueError as exc:
            return None, {"__json": f"Not valid JSON: {exc}"}, {}, text
    original = json.loads(form.get("__original") or "null")
    r = _resolve(spec, original, schema_id)
    ctx = nodes.Context(root=r.schema, ui=r.ui, errors={}, extensible=r.inferred)
    data = nodes.parse(r.schema, form, ctx, required=True)
    return (None if data is nodes.MISSING else data), ctx.errors, ctx.chosen, None


def parse_form(request: Request, spec: FormSpec, form) -> FormResult:
    """Read a posted form back into a document and validate it against the schema in force."""
    schema_id = form.get("__schema", "")
    mode = form.get("__mode", "form")
    data, errors, chosen, bad_json = _read(spec, form, schema_id, mode)
    general: list[str] = []
    if "__json" in errors:
        general.append(errors.pop("__json"))
    elif not errors:
        r = _resolve(spec, data, schema_id)
        if not r.inferred:
            errors, general = nodes.validate(r.schema, data)
    ctx = build_form(request, spec, data, errors=errors, general=general, schema_id=schema_id,
                     mode=mode, chosen=chosen, json_text=bad_json)
    return FormResult(data=data, errors=errors, general=general, form=ctx, schema_id=schema_id)


# ── Edits that change the form's shape ──────────────────────────────────────

def _at(data: Any, name: str) -> tuple[Any, Any]:
    """(container, key) of a form name inside data."""
    parts = [p.replace("~1", "/").replace("~0", "~") for p in name.split("/")[1:]]
    node = data
    for p in parts[:-1]:
        node = node[int(p)] if isinstance(node, list) else node.setdefault(p, {})
    last = parts[-1] if parts else None
    return node, (int(last) if isinstance(node, list) and last is not None else last)


def _get(data: Any, name: str) -> Any:
    if name == nodes.ROOT:
        return data
    container, key = _at(data, name)
    try:
        return container[key]
    except (KeyError, IndexError, TypeError):
        return None


def _set(data: Any, name: str, value: Any) -> Any:
    if name == nodes.ROOT:
        return value
    container, key = _at(data, name)
    container[key] = value
    return data


def _new_item(spec: FormSpec, data: Any, schema_id: str, name: str) -> Any:
    """A new item for the array at `name`: its items schema's default, or empty."""
    r = _resolve(spec, data, schema_id)
    s = r.schema
    for part in name.split("/")[1:]:
        s, _ = split_null(resolve(s, r.schema), r.schema)
        if kind_of(s) == "array":
            s = s.get("items", {})
        else:
            s = s.get("properties", {}).get(part.replace("~1", "/").replace("~0", "~"), {})
    s, _ = split_null(resolve(s, r.schema), r.schema)
    return default_for(s.get("items", {}), r.schema)


def apply(spec: FormSpec, form, op: str) -> tuple[Any, dict, str, str, dict, str | None]:
    """Read the form, apply one edit, and return what to render."""
    schema_id = form.get("__schema", "")
    mode = form.get("__mode", "form")
    data, errors, chosen, bad_json = _read(spec, form, schema_id, mode)
    verb, _, name = op.partition(":")
    if verb == "mode":
        if name == "form" and bad_json is not None:
            return data, {}, schema_id, "json", {}, bad_json   # stay: fix the JSON first
        return data, {} if name == "form" else errors, schema_id, name, chosen, None
    if verb == "schema":
        return data, {}, name if name in SCHEMAS else "", mode, {}, None
    if bad_json is not None:
        return data, errors, schema_id, mode, chosen, bad_json
    if data is None:
        data = {}
    if verb == "add":
        new = _new_item(spec, data, schema_id, name)
        items = _get(data, name) or []
        data = _set(data, name, [*items, new])
    elif verb in ("remove", "up", "down"):
        parent, _, index = name.rpartition("/")
        items = list(_get(data, parent) or [])
        i = int(index)
        if verb == "remove" and i < len(items):
            items.pop(i)
        elif verb == "up" and 0 < i < len(items):
            items[i - 1], items[i] = items[i], items[i - 1]
        elif verb == "down" and i < len(items) - 1:
            items[i + 1], items[i] = items[i], items[i + 1]
        data = _set(data, parent, items)
        chosen = {}
    return data, errors, schema_id, mode, chosen, None


@router.post("/{key}/render")
async def rerender(key: str, request: Request, user=Depends(current_user)):
    spec = FORMS.get(key)
    if spec is None:
        raise HTTPException(404)
    if not user.can(spec.permission):
        raise HTTPException(403)
    form = await request.form()
    op = form.get("__op") or form.get("__pick", "")
    data, errors, schema_id, mode, chosen, bad_json = apply(spec, form, op)
    ctx = build_form(request, spec, data, errors=errors, schema_id=schema_id, mode=mode,
                     chosen=chosen, json_text=bad_json)
    return render(request, "components/json_form_body.html", form=ctx)
