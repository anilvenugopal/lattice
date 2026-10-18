"""Work Queue: cases that move through review (submissions, requests, tickets).

Shows the full pattern: a GridSpec with views, filters, bulk actions with input
fields, a side panel, a detail page, and create/edit forms.
"""

from __future__ import annotations

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
    Palette,
    Permission,
    View,
    audit,
    build_grid,
    csrf_protect,
    current_user,
    get_db,
    render_grid_page,
    render_page,
    require,
    sql_queries,
    users,
)

SQL = sql_queries(Path(__file__).parent / "sql").work_items
EDIT, DELETE = "demo.work.edit", "demo.work.delete"
PERMISSIONS = [
    Permission(EDIT, "Edit work items",
               "Create, edit, assign, set the status of and approve work items.",
               default_roles=("editor",)),
    Permission(DELETE, "Delete work items", "Delete work items for good."),
]

STATUSES = [("new", "New"), ("in_review", "In review"), ("approved", "Approved"),
            ("declined", "Declined")]
STATUS_TONES = {"new": "info", "in_review": "warning", "approved": "success", "declined": "danger"}
PRIORITIES = [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")]
PRIORITY_TONES = {"low": "neutral", "normal": "neutral", "high": "warning", "urgent": "danger"}
OPEN = ["new", "in_review"]


def assign(ctx: ActionContext) -> str:
    owner_id = int(ctx.values["owner_id"]) if ctx.values.get("owner_id") else None
    ctx.db.run(SQL.assign, ids=ctx.ids, owner_id=owner_id)
    return f"Assigned {ctx.count} item(s)."


def set_status(ctx: ActionContext) -> str:
    ctx.db.run(SQL.set_status, ids=ctx.ids, status=ctx.values["status"])
    return f"Updated status on {ctx.count} item(s)."


def approve(ctx: ActionContext) -> str:
    ctx.db.run(SQL.set_status, ids=ctx.ids, status="approved")
    return f"Approved {ctx.count} item(s)."


def remove(ctx: ActionContext) -> str:
    ctx.db.run(SQL.delete, ids=ctx.ids)
    return f"Deleted {ctx.count} item(s)."


def panel(db: Db, user, row: dict) -> dict:
    return {"template": "demo/work_item_panel.html",
            "item": db.one(SQL.by_id, id=row["id"]),
            "events": audit.history(db, "demo.work_items", row["id"], limit=5)}


GRID = GridSpec(
    key="demo.work_items",
    title="Work items",
    path="/demo/work",
    query=SQL.grid,
    columns=[
        Column("ref", "Ref", kind="mono", width="110px", required=True),
        Column("title", "Title", kind="strong", secondary="account", required=True),
        Column("account", "Account", hidden=True),
        Column("status", "Status", kind="badge", tones=STATUS_TONES, labels=dict(STATUSES),
               width="120px"),
        Column("priority", "Priority", kind="badge", tones=PRIORITY_TONES,
               labels=dict(PRIORITIES), width="100px"),
        Column("owner", "Owner", kind="user", width="170px"),
        Column("amount", "Amount", kind="money", align="right", width="120px"),
        Column("received_at", "Received", kind="ago", width="130px"),
        Column("updated_at", "Updated", kind="ago", width="130px", hidden=True),
    ],
    search=["ref", "title", "account", "owner"],
    filters=[
        Filter("status", "Status", STATUSES),
        Filter("priority", "Priority", PRIORITIES),
        Filter("owner_id", "Owner", users.options),
    ],
    views=[
        View("open", "Open", where={"status": OPEN}),
        View("mine", "Assigned to me", where={"owner_id": "$me", "status": OPEN}),
        View("closed", "Closed", where={"status": ["approved", "declined"]}),
        View("all", "All"),
    ],
    actions=[
        Action("new", "New item", scope="none", href="/demo/work/new", tone="primary", icon="plus",
               permission=EDIT),
        Action("open", "Open", scope="single", href="/demo/work/{id}", icon="external"),
        Action("assign", "Assign", handler=assign, icon="assign", permission=EDIT,
               fields=[Field("owner_id", "Owner", kind="select",
                             options=lambda db, u: [("", "Unassigned"), *users.options(db)])]),
        Action("status", "Set status", handler=set_status, icon="flag", permission=EDIT,
               fields=[Field("status", "Status", kind="select", options=STATUSES,
                             required=True)]),
        Action("approve", "Approve", handler=approve, icon="check", permission=EDIT,
               when={"status": OPEN}, confirm="Approve {count} item(s)?"),
        Action("delete", "Delete", handler=remove, tone="danger", icon="trash",
               permission=DELETE, confirm="Delete {count} item(s)? This cannot be undone."),
    ],
    default_sort="-received_at",
    row_href="/demo/work/{id}",
    panel=panel,
    panel_title="{ref} · {title}",
    search_placeholder="Search ref, title, account, owner",
    empty_title="No work items match",
    empty_text="Change the view or clear filters to see more.",
    palette=Palette(title="{ref} · {title}", subtitle="{account}", href="/demo/work/{id}",
                    icon="queue"),
)


TILES = [
    HomeTile("Open work items", GRID, view="open"),
    HomeTile("Assigned to me", GRID, view="mine", tone="accent"),
]

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/work")
def work_list(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "work.items",
                            subtitle="Cases waiting for review and decision.")


def _form_ctx(db: Db, item: dict | None, errors: dict | None = None) -> dict:
    return {"item": item, "errors": errors or {}, "statuses": STATUSES,
            "priorities": PRIORITIES, "owners": users.options(db)}


def _read_form(form) -> tuple[dict, dict]:
    data = {k: (form.get(k) or "").strip() for k in
            ("title", "account", "status", "priority", "owner_id", "amount", "description")}
    errors = {}
    if not data["title"]:
        errors["title"] = "Title is required."
    try:
        data["amount"] = float(data["amount"] or 0)
    except ValueError:
        errors["amount"] = "Enter a number."
    if data["status"] not in dict(STATUSES):
        data["status"] = "new"
    if data["priority"] not in dict(PRIORITIES):
        data["priority"] = "normal"
    data["owner_id"] = int(data["owner_id"]) if data["owner_id"].isdigit() else None
    return data, errors


FIELDS = ("title", "account", "status", "priority", "owner_id", "amount", "description")


@router.get("/work/new", dependencies=[Depends(require(EDIT))])
def new_form(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "demo/work_item_form.html", "work.new", **_form_ctx(db, None))


@router.post("/work/new", dependencies=[Depends(require(EDIT))])
async def create(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    data, errors = _read_form(await request.form())
    if errors:
        return render_page(request, "demo/work_item_form.html", "work.new",
                           status_code=400, **_form_ctx(db, None, errors), values=data)
    item_id = db.value(SQL.create, **data)
    audit.record(db, user.id, "demo.work_items.create", "Created", "demo.work_items", item_id)
    return RedirectResponse(f"/demo/work/{item_id}", status_code=303)


@router.get("/work/{item_id}")
def detail(item_id: int, request: Request, db: Db = Depends(get_db)):
    item = db.one(SQL.by_id, id=item_id)
    # The same grid, embedded and fixed to this item's account.
    related = build_grid(request, db, GRID, sync_url=False, fixed={"account": item["account"]})
    return render_page(request, "demo/work_item_detail.html", "work.detail",
                       item=item, events=audit.history(db, "demo.work_items", item_id),
                       spec=GRID, can_edit=request.state.user.can(EDIT),
                       related=related, crumb=item["ref"])


@router.get("/work/{item_id}/edit", dependencies=[Depends(require(EDIT))])
def edit_form(item_id: int, request: Request, db: Db = Depends(get_db)):
    item = db.one(SQL.by_id, id=item_id)
    return render_page(request, "demo/work_item_form.html", "work.detail",
                       **_form_ctx(db, item), crumb=item["ref"])


@router.post("/work/{item_id}/edit", dependencies=[Depends(require(EDIT))])
async def save(item_id: int, request: Request, db: Db = Depends(get_db),
               user=Depends(current_user)):
    item = db.one(SQL.by_id, id=item_id)
    data, errors = _read_form(await request.form())
    if errors:
        return render_page(request, "demo/work_item_form.html", "work.detail",
                           status_code=400, **_form_ctx(db, item, errors), values=data,
                           crumb=item["ref"])
    changed = sorted(k for k in FIELDS if item[k] != data[k])
    if changed:
        db.run(SQL.update, id=item_id, **data)
        audit.record(db, user.id, "demo.work_items.edit", "Edited " + ", ".join(changed),
                     "demo.work_items", item_id)
    return RedirectResponse(f"/demo/work/{item_id}", status_code=303)
