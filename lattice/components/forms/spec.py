"""Form and schema declarations (ADR 0007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaDef:
    """A named JSON Schema that forms can apply, e.g. a document kind's schema.

    `schema` is a JSON Schema dict or a Pydantic model class (its model_json_schema()).
    """

    id: str                         # "{app}.name"; documents record it
    title: str
    schema: Any
    ui: dict = field(default_factory=dict)
    version: int = 1                # bump when the schema changes shape

    def json_schema(self) -> dict:
        return as_json_schema(self.schema)


@dataclass
class FormSpec:
    """A form drawn from a JSON Schema. JSON in, JSON out; the app loads and saves.

    schema: a JSON Schema dict, a Pydantic model class, the id of a registered SchemaDef, or
    None to infer one from the document (every key present becomes a field; new fields can be
    added). `switchable` lets the user apply another registered schema.
    """

    key: str                        # "{app}.name"; the shared endpoint is /_form/{key}/render
    schema: Any = None
    ui: dict = field(default_factory=dict)   # hints by path: label, help, widget, order…
    permission: str = ""            # who may use the form's endpoint
    json_tab: bool = True           # offer the raw JSON tab
    switchable: bool = False        # offer the registered schemas to apply instead

    @property
    def app_key(self) -> str:
        return self.key.partition(".")[0] if "." in self.key else ""


def as_json_schema(schema: Any) -> dict:
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    raise TypeError(f"Not a JSON Schema or Pydantic model: {schema!r}")
