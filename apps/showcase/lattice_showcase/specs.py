"""Specs and free-form documents: forms from JSON Schema and the document store.

Specs are documents of a declared kind, with a Pydantic schema that uses nested objects,
arrays, an enum, a nullable date and a discriminated union. The free-form page edits one
document with no schema at all: its form is inferred from the document, and new fields can
be added.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from lattice.api import (
    Action,
    ActionContext,
    Column,
    Db,
    DocumentKind,
    FormSpec,
    GridSpec,
    Permission,
    build_form,
    csrf_protect,
    current_user,
    documents,
    flash,
    get_db,
    parse_form,
    render_grid_page,
    render_page,
    require,
)

EDIT = "showcase.specs.edit"
PERMISSIONS = [Permission(EDIT, "Edit specs", "Create, change and delete spec documents.",
                          default_roles=("editor",))]


class Dimension(BaseModel):
    name: str = Field(title="Measure")
    value: float = Field(ge=0)
    unit: Literal["mm", "cm", "m", "g", "kg"] = "mm"


class Supplier(BaseModel):
    """Made outside: who supplies it."""

    kind: Literal["supplier"] = "supplier"
    name: str = Field(title="Supplier")
    email: str | None = Field(None, json_schema_extra={"format": "email"})


class Internal(BaseModel):
    """Made inside: which team, and who pays."""

    kind: Literal["internal"] = "internal"
    team: str
    cost_centre: str = Field(pattern=r"^CC-\d{4}$", description="CC- and four digits")


class Spec(BaseModel):
    name: str = Field(min_length=3)
    summary: str = Field("", json_schema_extra={"x-widget": "textarea"})
    stage: Literal["draft", "review", "approved"] = "draft"
    version: int = Field(1, ge=1)
    released_on: date | None = None
    tags: list[str] = []
    dimensions: list[Dimension] = []
    source: Supplier | Internal = Field(discriminator="kind", title="Made by")


SPEC = DocumentKind(
    "showcase.spec", "Spec", schema=Spec, title="{name}", edit=EDIT,
    ui={"": {"sections": [("About", ["name", "stage", "version", "released_on", "summary"]),
                          ("Details", ["tags", "dimensions", "source"])]},
        "stage": {"labels": {"draft": "Draft", "review": "In review", "approved": "Approved"}},
        "tags": {"item_label": "Tag"},
        "dimensions": {"item_label": "Dimension"}})

NOTE = DocumentKind("showcase.note", "Free-form note", schema={"type": "object"},
                    title="{title}", edit=EDIT)
FREEFORM = FormSpec("showcase.freeform", permission=EDIT)     # no schema: inferred


def delete(ctx: ActionContext) -> str:
    documents.delete(ctx.db, ctx.user, SPEC, ctx.ids, record=False)
    return f"Deleted {ctx.count} spec(s)."


GRID = GridSpec(
    key="showcase.spec", title="Specs", path="/showcase/specs", query=documents.QUERY,
    params={"kind": SPEC.key},
    columns=[Column("id", "#", kind="mono", width="60px"),
             Column("title", "Name", kind="strong", required=True),
             Column("schema_version", "Schema", kind="number", width="80px", hidden=True),
             Column("updated_by", "Changed by", kind="user", width="170px"),
             Column("updated_at", "Changed", kind="ago", width="120px")],
    search=["title"],
    actions=[Action("new", "New spec", scope="none", href="/showcase/specs/new", tone="primary",
                    icon="plus", permission=EDIT),
             Action("open", "Open", scope="single", href="/showcase/specs/{id}", icon="edit"),
             Action("delete", "Delete", handler=delete, tone="danger", icon="trash",
                    permission=EDIT, confirm="Delete {count} spec(s)?")],
    default_sort="-updated_at", row_href="/showcase/specs/{id}",
    empty_title="No specs yet", empty_text="Choose New spec to write one.",
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/specs")
def specs_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "forms.specs",
                            subtitle="Documents in the document store, one kind, listed by a "
                                     "grid on documents.QUERY.")


def _page(request, form, *, doc=None, status_code=200):
    return render_page(request, "showcase/spec_form.html", "forms.spec" if doc else "forms.new",
                       form=form, doc=doc, status_code=status_code,
                       crumb=doc["title"] if doc else None)


@router.get("/specs/new", dependencies=[Depends(require(EDIT))])
def new_spec(request: Request):
    return _page(request, build_form(request, SPEC.form, {"source": {"kind": "internal"}}))


@router.post("/specs/new", dependencies=[Depends(require(EDIT))])
async def create_spec(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    result = parse_form(request, SPEC.form, await request.form())
    if not result.ok:
        return _page(request, result.form, status_code=400)
    doc_id = documents.create(db, user, SPEC, result.data)
    response = RedirectResponse(f"/showcase/specs/{doc_id}", status_code=303)
    flash(response, request, "Spec created.")
    return response


@router.get("/specs/{doc_id}")
def edit_spec(doc_id: int, request: Request, db: Db = Depends(get_db)):
    doc = documents.get(db, SPEC, doc_id)
    return _page(request, build_form(request, SPEC.form, doc["data"]), doc=doc)


@router.post("/specs/{doc_id}", dependencies=[Depends(require(EDIT))])
async def save_spec(doc_id: int, request: Request, db: Db = Depends(get_db),
                    user=Depends(current_user)):
    doc = documents.get(db, SPEC, doc_id)
    result = parse_form(request, SPEC.form, await request.form())
    if not result.ok:
        return _page(request, result.form, doc=doc, status_code=400)
    documents.update(db, user, SPEC, doc_id, result.data)
    response = RedirectResponse(f"/showcase/specs/{doc_id}", status_code=303)
    flash(response, request, "Spec saved.")
    return response


# ── Free-form: one document, no schema ──────────────────────────────────────

STARTER = {"title": "Release checklist", "owner": "Avery", "due": "2026-11-30",
           "approved": False, "budget": 12500,
           "steps": [{"name": "Freeze scope", "done": True}, {"name": "Sign off", "done": False}],
           "notes": "Anything goes here.\nThe form follows the document."}


def _note(db: Db) -> dict | None:
    found = documents.all_of(db, NOTE)
    return found[0] if found else None


@router.get("/freeform")
def freeform(request: Request, db: Db = Depends(get_db)):
    note = _note(db)
    return render_page(request, "showcase/freeform.html", "forms.freeform",
                       form=build_form(request, FREEFORM, note["data"] if note else STARTER))


@router.post("/freeform", dependencies=[Depends(require(EDIT))])
async def save_freeform(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    result = parse_form(request, FREEFORM, await request.form())
    if not result.ok or not isinstance(result.data, dict):
        return render_page(request, "showcase/freeform.html", "forms.freeform", form=result.form,
                           status_code=400)
    note = _note(db)
    if note:
        documents.update(db, user, NOTE, note["id"], result.data)
    else:
        documents.create(db, user, NOTE, result.data)
    response = RedirectResponse("/showcase/freeform", status_code=303)
    flash(response, request, "Saved.")
    return response
