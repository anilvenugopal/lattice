"""The document store (ADR 0007): JSON documents of kinds that apps declare.

    SPEC = DocumentKind("showcase.spec", "Spec", schema=Spec,
                        title="{name}", edit="showcase.specs.edit")
    APP = AppManifest(…, documents=[SPEC])

    doc_id = documents.create(db, user, SPEC, data)     # validated against the schema
    data = documents.get(db, SPEC, doc_id)["data"]

Each kind's schema is registered as a SchemaDef (id = the kind's key) and its form as a
FormSpec with the same key, so `build_form(request, SPEC.form, data)` draws it. A grid
of one kind runs `QUERY` with `params={"kind": SPEC.key}`; give it the kind's key, so its
actions and the record page's history share the audit trail.

Guide: lattice/help/developer/building-apps/json-forms.md#the-document-store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lattice.components.forms import nodes
from lattice.components.forms.spec import FormSpec, SchemaDef, as_json_schema
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL
from lattice.kernel.services import audit
from lattice.kernel.web import fmt

QUERY = SQL.documents.grid


@dataclass
class DocumentKind:
    key: str                        # "{app}.{name}"
    label: str                      # "Policy template"
    schema: Any                     # JSON Schema dict or Pydantic model class
    ui: dict = field(default_factory=dict)   # form hints, as for FormSpec
    title: str = "{name}"           # the document's title, formatted with its data
    version: int = 1                # bump when the schema changes shape
    edit: str = ""                  # permission to create, change and delete; empty = anyone
    form: FormSpec = field(init=False)

    def __post_init__(self):
        self.form = FormSpec(self.key, schema=self.key, permission=self.edit)

    def schema_def(self) -> SchemaDef:
        return SchemaDef(self.key, self.label, self.schema, self.ui, self.version)


class InvalidDocument(ValueError):
    """The data does not satisfy the kind's schema."""

    def __init__(self, errors: dict, general: list[str]):
        super().__init__("; ".join([*general, *(f"{k}: {v}" for k, v in errors.items())]))
        self.errors, self.general = errors, general


def _checked(kind: DocumentKind, data: Any) -> dict:
    if not isinstance(data, dict):
        raise InvalidDocument({}, ["A document is a JSON object."])
    errors, general = nodes.validate(as_json_schema(kind.schema), data)
    if errors or general:
        raise InvalidDocument(errors, general)
    return data


def create(db: Db, user, kind: DocumentKind, data: dict) -> int:
    data = _checked(kind, data)
    title = fmt(kind.title, data)[:255]
    doc_id = db.value(SQL.documents.create, kind=kind.key, schema_version=kind.version,
                      title=title, data=data, user_id=user.id)
    audit.record(db, user.id, f"{kind.key}.created", f"Created {kind.label.lower()} {title}",
                 kind.key, doc_id)
    return doc_id


def update(db: Db, user, kind: DocumentKind, doc_id: int, data: dict) -> None:
    get(db, kind, doc_id)
    data = _checked(kind, data)
    title = fmt(kind.title, data)[:255]
    db.run(SQL.documents.update, id=doc_id, kind=kind.key, schema_version=kind.version,
           title=title, data=data, user_id=user.id)
    audit.record(db, user.id, f"{kind.key}.updated", f"Changed {kind.label.lower()} {title}",
                 kind.key, doc_id)


def get(db: Db, kind: DocumentKind, doc_id: int) -> dict:
    """The document (id, title, data, schema_version, timestamps); 404 when missing."""
    return db.one(SQL.documents.by_id, id=doc_id, kind=kind.key)


def all_of(db: Db, kind: DocumentKind) -> list[dict]:
    return db.all(SQL.documents.of_kind, kind=kind.key)


def delete(db: Db, user, kind: DocumentKind, ids: list[int], *, record: bool = True) -> None:
    """record=False from a grid action handler: the grid records its own audit event."""
    db.run(SQL.documents.delete, ids=list(ids), kind=kind.key)
    if record:
        audit.record_many(db, user.id, f"{kind.key}.deleted", f"Deleted {kind.label.lower()}",
                          kind.key, list(ids))
