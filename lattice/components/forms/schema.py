"""JSON Schema helpers for forms: resolve references, read the shapes forms support, infer a
schema from a document.

Forms support a subset of JSON Schema 2020-12 (ADR 0007): object, array, string (with
formats), number, integer, boolean, enum, const, $ref/$defs, nullable types (`["string",
"null"]` or `anyOf` with null, as Pydantic writes Optional fields) and oneOf/anyOf between
objects (a discriminator chooses the variant). Anything else is edited as raw JSON.
"""

from __future__ import annotations

import re
from typing import Any

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$")


def resolve(schema: Any, root: dict, seen: frozenset = frozenset()) -> dict:
    """The schema with `$ref` replaced by its target (sibling keywords win) and single-item
    `allOf` merged in. Recursive references stop at the second visit."""
    if not isinstance(schema, dict):
        return {} if schema is True else {"not": {}}
    out = dict(schema)
    while "$ref" in out:
        ref = out.pop("$ref")
        if ref in seen:
            return {"description": out.get("description", ""), "x-recursive": ref}
        seen = seen | {ref}
        out = {**_pointer(root, ref), **out}
    if len(out.get("allOf", [])) == 1:
        inner = resolve(out.pop("allOf")[0], root, seen)
        out = {**inner, **out}
    return out


def _pointer(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"Only local references are supported, not {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def split_null(schema: dict, root: dict) -> tuple[dict, bool]:
    """(schema without null, nullable) for ["x", "null"] types and anyOf/oneOf with a null branch."""
    t = schema.get("type")
    if isinstance(t, list) and "null" in t:
        rest = [x for x in t if x != "null"]
        return {**schema, "type": rest[0] if len(rest) == 1 else rest}, True
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if branches:
            resolved = [resolve(b, root) for b in branches]
            others = [b for b in resolved if b.get("type") != "null"]
            if len(others) < len(resolved):
                base = {k: v for k, v in schema.items() if k != key}
                if len(others) == 1:
                    return {**others[0], **base}, True
                return {**base, key: others}, True
    return schema, False


def kind_of(schema: dict) -> str:
    """object | array | string | number | integer | boolean | enum | const | variant | json"""
    if "const" in schema:
        return "const"
    if "enum" in schema:
        return "enum"
    if schema.get("oneOf") or schema.get("anyOf"):
        return "variant"
    t = schema.get("type")
    if t == "object" or (t is None and "properties" in schema):
        return "object"
    if t == "array" and "prefixItems" not in schema:
        return "array"
    if t in ("string", "number", "integer", "boolean"):
        return t
    return "json"


def infer(value: Any) -> dict:
    """A schema that describes `value` as it is: every key present, nothing required."""
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        if DATE.match(value):
            return {"type": "string", "format": "date"}
        if DATE_TIME.match(value):
            return {"type": "string", "format": "date-time"}
        return {"type": "string", "x-widget": "textarea"} if "\n" in value else {"type": "string"}
    if isinstance(value, dict):
        return {"type": "object", "properties": {k: infer(v) for k, v in value.items()}}
    if isinstance(value, list):
        items: dict = {}
        for item in value:
            if isinstance(item, dict) and items.get("type") == "object":
                for k, v in item.items():
                    items["properties"].setdefault(k, infer(v))
            elif not items:
                items = infer(item)
        return {"type": "array", "items": items or {"type": "string"}}
    return {}


def default_for(schema: dict, root: dict) -> Any:
    """A new value for an empty array item or a new property: the schema's default, or empty."""
    schema, _ = split_null(resolve(schema, root), root)
    if "default" in schema:
        return schema["default"]
    kind = kind_of(schema)
    if kind == "object":
        return {k: default_for(v, root) for k, v in schema.get("properties", {}).items()
                if k in schema.get("required", [])}
    if kind == "array":
        return []
    if kind == "const":
        return schema["const"]
    if kind == "variant":
        return default_for((schema.get("oneOf") or schema.get("anyOf"))[0], root)
    return None
