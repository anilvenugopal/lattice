"""The document store: JSON documents of declared kinds, validated, audited and listed by kind."""

import pytest
from pydantic import BaseModel, Field

from lattice.api import AppManifest, Column, DocumentKind, GridSpec, InvalidDocument, documents
from lattice.components.grid import engine
from lattice.host import AppError, create_app
from lattice.kernel.services import audit
from lattice.testing import current


class Template(BaseModel):
    name: str = Field(min_length=2)
    clauses: list[str] = []


TEMPLATE = DocumentKind("files.template", "Policy template", schema=Template)
NOTE = DocumentKind("files.note", "Note", schema={"type": "object", "properties": {
    "name": {"type": "string"}}}, edit="files.notes.edit")
GRID = GridSpec(key="files.template", title="Templates", path="/files", query=documents.QUERY,
                params={"kind": TEMPLATE.key}, columns=[Column("title", "Title")])


@pytest.fixture
def host_apps():
    from lattice.api import Permission
    return [AppManifest(key="files", label="Files", documents=[TEMPLATE, NOTE], grids=[GRID],
                        permissions=[Permission("files.notes.edit", "Edit notes")])]


def test_create_get_update_and_history(db, users, client):
    user = current(users["editor"])
    doc_id = documents.create(db, user, TEMPLATE, {"name": "Marine", "clauses": ["a"]})
    doc = documents.get(db, TEMPLATE, doc_id)
    assert doc["title"] == "Marine" and doc["data"]["clauses"] == ["a"]
    documents.update(db, user, TEMPLATE, doc_id, {"name": "Marine cargo"})
    assert documents.get(db, TEMPLATE, doc_id)["title"] == "Marine cargo"
    actions = [e["action"] for e in audit.history(db, TEMPLATE.key, doc_id)]
    assert actions == ["files.template.updated", "files.template.created"]


def test_invalid_documents_are_refused(db, users, client):
    with pytest.raises(InvalidDocument) as exc:
        documents.create(db, current(users["editor"]), TEMPLATE, {"name": "M"})
    assert exc.value.errors == {"data/name": "At least 2 characters."}
    with pytest.raises(InvalidDocument):
        documents.create(db, current(users["editor"]), TEMPLATE, ["not", "an", "object"])


def test_a_grid_lists_one_kind_only(db, users, client):
    user = current(users["editor"])
    documents.create(db, user, TEMPLATE, {"name": "Marine"})
    documents.create(db, user, NOTE, {"name": "Not a template"})
    rows = engine.fetch_page(GRID, db, user, engine.GridQuery()).rows
    assert [r["title"] for r in rows] == ["Marine"]


def test_kinds_get_a_form_and_a_schema(client):
    from lattice.components import forms
    assert forms.FORMS["files.note"].permission == "files.notes.edit"
    assert forms.SCHEMAS["files.template"].title == "Policy template"


def test_delete_is_per_kind(db, users, client):
    user = current(users["editor"])
    doc_id = documents.create(db, user, TEMPLATE, {"name": "Marine"})
    documents.delete(db, user, NOTE, [doc_id])                  # wrong kind: untouched
    assert documents.all_of(db, TEMPLATE)
    documents.delete(db, user, TEMPLATE, [doc_id])
    assert documents.all_of(db, TEMPLATE) == []


def test_kind_keys_are_namespaced():
    with pytest.raises(AppError, match="document kind 'other.x' must start with 'files.'"):
        create_app(apps=[AppManifest(key="files", label="Files",
                                     documents=[DocumentKind("other.x", "X", schema={})])])
