"""Items: the showcase's main sample records.

Shows a table grid with one column of every kind, filters, views, bulk actions with
input fields, `when` rules, a star toggle and a side panel; the record page built on
the same grid; and the plain form pattern for creating and editing.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from lattice.api import (
    Action,
    ActionContext,
    Column,
    Db,
    Field,
    Filter,
    GridSpec,
    HomeTile,
    Link,
    Palette,
    Panel,
    Permission,
    RecordPage,
    Step,
    TreeNode,
    View,
    audit,
    build_grid,
    csrf_protect,
    current_user,
    flash,
    get_db,
    render_grid_page,
    render_page,
    render_record_page,
    require,
    sql_queries,
    users,
)

SQL = sql_queries(Path(__file__).parent / "sql").items
EDIT, DELETE = "showcase.items.edit", "showcase.items.delete"
PERMISSIONS = [
    Permission(EDIT, "Edit items", "Create, edit, assign and change the status of items.",
               default_roles=("editor",)),
    Permission(DELETE, "Delete items", "Delete items for good."),
]

STATUSES = [("new", "New"), ("active", "Active"), ("blocked", "Blocked"), ("done", "Done"),
            ("archived", "Archived")]
STATUS_TONES = {"new": "info", "active": "warning", "blocked": "danger", "done": "success",
                "archived": "neutral"}
PRIORITIES = [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")]
PRIORITY_TONES = {"low": "neutral", "normal": "neutral", "high": "warning", "urgent": "danger"}
CATEGORIES = [("hardware", "Hardware"), ("software", "Software"), ("services", "Services"),
              ("research", "Research"), ("operations", "Operations"), ("design", "Design")]
OPEN = ["new", "active", "blocked"]


def assign(ctx: ActionContext) -> str:
    ctx.db.run(SQL.assign, ids=ctx.ids, owner_id=int(ctx.values["owner_id"] or 0) or None)
    return f"Assigned {ctx.count} item(s)."


def set_status(ctx: ActionContext) -> str:
    ctx.db.run(SQL.set_status, ids=ctx.ids, status=ctx.values["status"])
    return f"Updated status on {ctx.count} item(s)."


def complete(ctx: ActionContext) -> str:
    ctx.db.run(SQL.set_status, ids=ctx.ids, status="done")
    return f"Completed {ctx.count} item(s)."


def star(ctx: ActionContext) -> str:
    ctx.db.run(SQL.star, ids=ctx.ids)
    return f"Toggled the star on {ctx.count} item(s)."


def remove(ctx: ActionContext) -> str:
    ctx.db.run(SQL.delete, ids=ctx.ids)
    return f"Deleted {ctx.count} item(s)."


def panel(db: Db, user, row: dict) -> dict:
    return {"template": "showcase/item_panel.html",
            "item": db.one(SQL.by_id, id=row["id"]),
            "events": audit.history(db, "showcase.items", row["id"], limit=5)}


GRID = GridSpec(
    key="showcase.items",
    title="Items",
    path="/showcase/items",
    query=SQL.grid,
    columns=[
        Column("starred", "", kind="star", star_action="star", width="36px", sortable=False),
        Column("ref", "Ref", kind="mono", width="90px", required=True),
        Column("name", "Name", kind="strong", secondary="category", required=True),
        Column("category", "Category", labels=dict(CATEGORIES), hidden=True),
        Column("status", "Status", kind="badge", tones=STATUS_TONES, labels=dict(STATUSES),
               width="110px"),
        Column("priority", "Priority", kind="badge", tones=PRIORITY_TONES,
               labels=dict(PRIORITIES), width="100px"),
        Column("owner", "Owner", kind="user", width="160px"),
        Column("progress", "Progress", kind="progress", width="130px"),
        Column("amount", "Amount", kind="money", align="right", width="120px"),
        Column("score", "Score", kind="percent", align="right", width="80px", hidden=True),
        Column("tags", "Tags", kind="tags", hidden=True),
        Column("country", "Country", hidden=True),
        Column("parent_ref", "Parent", kind="mono", href="/showcase/items/{parent_id}",
               width="90px", hidden=True),
        Column("due_on", "Due", kind="date", width="110px"),
        Column("updated_at", "Updated", kind="ago", width="110px", hidden=True),
    ],
    search=["ref", "name", "owner", "tags", "country"],
    filters=[
        Filter("status", "Status", STATUSES),
        Filter("priority", "Priority", PRIORITIES),
        Filter("category", "Category", CATEGORIES),
        Filter("owner_id", "Owner", users.options),
    ],
    views=[
        View("open", "Open", where={"status": OPEN}),
        View("mine", "Mine", where={"owner_id": "$me", "status": OPEN}),
        View("starred", "Starred", where={"starred": True}),
        View("done", "Done", where={"status": ["done", "archived"]}, sort="-updated_at"),
        View("all", "All"),
    ],
    actions=[
        Action("new", "New item", scope="none", href="/showcase/items/new", tone="primary",
               icon="plus", permission=EDIT),
        Action("open", "Open", scope="single", href="/showcase/items/{id}", icon="external"),
        Action("assign", "Assign", handler=assign, icon="assign", permission=EDIT,
               fields=[Field("owner_id", "Owner", kind="select",
                             options=lambda db, u: [("", "Unassigned"), *users.options(db)])]),
        Action("status", "Set status", handler=set_status, icon="flag", permission=EDIT,
               fields=[Field("status", "Status", kind="select", options=STATUSES,
                             required=True)]),
        Action("complete", "Complete", handler=complete, icon="check", permission=EDIT,
               when={"status": ["active", "blocked"]}, confirm="Complete {count} item(s)?"),
        Action("star", "Star", handler=star, icon="star", in_row_menu=False),
        Action("delete", "Delete", handler=remove, tone="danger", icon="trash",
               permission=DELETE, confirm="Delete {count} item(s)? This cannot be undone."),
    ],
    default_sort="-updated_at",
    row_href="/showcase/items/{id}",
    panel=panel,
    panel_title="{ref} · {name}",
    search_placeholder="Search ref, name, owner, tags, country",
    empty_title="No items match",
    empty_text="Change the view or clear the filters to see more.",
    palette=Palette(title="{ref} · {name}", subtitle="{status}", href="/showcase/items/{id}",
                    icon="queue"),
)

TILES = [
    HomeTile("Open items", GRID, view="open"),
    HomeTile("My open items", GRID, view="mine", tone="accent"),
]

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/items")
def items_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "grids.items",
                            subtitle="Every column kind, filters, views, saved views, bulk "
                                     "actions, a side panel and CSV export.")


# ── The record page ─────────────────────────────────────────────────────────

def _notes(request: Request, db: Db, row: dict) -> dict:
    return {"notes": db.one(SQL.by_id, id=row["id"])["notes"]}


def _lifecycle(request: Request, db: Db, row: dict) -> dict:
    """The item's status as a stepper: created, active, done, archived."""
    status = row["status"]
    order = ["new", "active", "done", "archived"]
    reached = order.index(status) if status in order else 1
    steps = [Step("Created", "done", note=row["created_at"].strftime("%b %d, %Y"))]
    for i, (key, label) in enumerate([("active", "Active"), ("done", "Done"),
                                      ("archived", "Archived")], start=1):
        if status == "blocked" and key == "active":
            steps.append(Step(label, "failed", note="Blocked"))
        elif i < reached or (i == reached and key in ("done", "archived")):
            steps.append(Step(label, "done"))
        elif i == reached:
            steps.append(Step(label, "current"))
        else:
            steps.append(Step(label))
    return {"steps": steps}


def _children(request: Request, db: Db, row: dict) -> dict:
    tones = STATUS_TONES
    labels = dict(STATUSES)
    kids = db.all(SQL.children, ids=[row["id"]])
    grandkids = db.all(SQL.children, ids=[k["id"] for k in kids]) if kids else []

    def node(r):
        return TreeNode(f"{r['ref']} · {r['name']}", href=f"/showcase/items/{r['id']}",
                        badge=labels[r["status"]], tone=tones[r["status"]],
                        children=[node(g) for g in grandkids if g["parent_id"] == r["id"]])
    return {"nodes": [node(k) for k in kids]}


def _related(request: Request, db: Db, row: dict) -> dict:
    # The same grid, embedded and fixed to this item's category.
    return {"grid": build_grid(request, db, GRID, sync_url=False,
                               fixed={"category": row["category"]})}


DETAIL = RecordPage(
    grid=GRID, nav_key="grids.item", title="{ref} · {name}", status="status", crumb="{ref}",
    reference_kind="showcase.item",       # other apps' panels for items appear here
    properties=["ref", "status", "priority", "owner", "category", "amount", "progress", "score",
                "tags", "country", "parent_ref", "due_on", "updated_at"],
    links=[Link("Edit", "/showcase/items/{id}/edit", icon="edit", tone="primary",
                permission=EDIT)],
    panels=[Panel("lifecycle", "Lifecycle", "showcase/item_lifecycle.html", load=_lifecycle),
            Panel("notes", "Notes", "showcase/item_notes.html", load=_notes),
            Panel("children", "Child items", "showcase/item_children.html", load=_children,
                  place="side"),
            Panel("related", "Other items in this category", "showcase/item_related.html",
                  load=_related, place="full", flush=True)],
)


# ── The plain form pattern ──────────────────────────────────────────────────

FIELDS = ("name", "category", "status", "priority", "owner_id", "amount", "due_on", "notes")


def _form_ctx(db: Db, item: dict | None, errors: dict | None = None) -> dict:
    return {"item": item, "errors": errors or {}, "statuses": STATUSES, "priorities": PRIORITIES,
            "categories": CATEGORIES, "owners": users.options(db)}


def _read_form(form) -> tuple[dict, dict]:
    data = {k: (form.get(k) or "").strip() for k in FIELDS}
    errors = {}
    if not data["name"]:
        errors["name"] = "Name is required."
    try:
        data["amount"] = Decimal(data["amount"] or "0").quantize(Decimal("0.01"))
    except InvalidOperation:
        errors["amount"] = "Enter a number."
    try:
        data["due_on"] = date.fromisoformat(data["due_on"]) if data["due_on"] else None
    except ValueError:
        errors["due_on"] = "Enter a date."
    for key, options, default in (("status", STATUSES, "new"), ("priority", PRIORITIES, "normal"),
                                  ("category", CATEGORIES, "hardware")):
        if data[key] not in dict(options):
            data[key] = default
    data["owner_id"] = int(data["owner_id"]) if data["owner_id"].isdigit() else None
    return data, errors


@router.get("/items/new", dependencies=[Depends(require(EDIT))])
def new_form(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "showcase/item_form.html", "grids.new", **_form_ctx(db, None))


@router.post("/items/new", dependencies=[Depends(require(EDIT))])
async def create(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    data, errors = _read_form(await request.form())
    if errors:
        return render_page(request, "showcase/item_form.html", "grids.new", status_code=400,
                           **_form_ctx(db, None, errors), values=data)
    item_id = db.value(SQL.create, **data)
    audit.record(db, user.id, "showcase.items.create", "Created", "showcase.items", item_id)
    response = RedirectResponse(f"/showcase/items/{item_id}", status_code=303)
    flash(response, request, "Item created.")
    return response


@router.get("/items/{item_id}")
def detail(item_id: int, request: Request, db: Db = Depends(get_db)):
    return render_record_page(request, db, DETAIL, item_id)


@router.get("/items/{item_id}/edit", dependencies=[Depends(require(EDIT))])
def edit_form(item_id: int, request: Request, db: Db = Depends(get_db)):
    item = db.one(SQL.by_id, id=item_id)
    return render_page(request, "showcase/item_form.html", "grids.item",
                       **_form_ctx(db, item), crumb=item["ref"])


@router.post("/items/{item_id}/edit", dependencies=[Depends(require(EDIT))])
async def save(item_id: int, request: Request, db: Db = Depends(get_db),
               user=Depends(current_user)):
    item = db.one(SQL.by_id, id=item_id)
    data, errors = _read_form(await request.form())
    if errors:
        return render_page(request, "showcase/item_form.html", "grids.item", status_code=400,
                           **_form_ctx(db, item, errors), values=data, crumb=item["ref"])
    changed = sorted(k for k in FIELDS if item[k] != data[k])
    if changed:
        db.run(SQL.update, id=item_id, **data)
        audit.record(db, user.id, "showcase.items.edit", "Edited " + ", ".join(changed),
                     "showcase.items", item_id)
    response = RedirectResponse(f"/showcase/items/{item_id}", status_code=303)
    flash(response, request, "Saved." if changed else "Nothing changed.")
    return response
