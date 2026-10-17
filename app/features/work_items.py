"""Work Queue: cases that move through review (submissions, requests, tickets).

Shows the full pattern: a GridSpec with views, filters, bulk actions with input
fields, a side panel, a detail page, and create/edit forms.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, aliased

from app.auth.csrf import csrf_protect
from app.auth.deps import current_user, require_roles
from app.auth.roles import ADMINS, EDITORS
from app.db import get_db
from app.features.common import user_options
from app.grid import (
    Action,
    ActionContext,
    Column,
    Field,
    Filter,
    GridSpec,
    Palette,
    View,
    register,
    render_grid_page,
)
from app.models import User, WorkItem, utcnow
from app.services import audit
from app.services.home import HomeTile, register_tile
from app.web import render_page

STATUSES = [("new", "New"), ("in_review", "In review"), ("approved", "Approved"),
            ("declined", "Declined")]
STATUS_TONES = {"new": "info", "in_review": "warning", "approved": "success", "declined": "danger"}
PRIORITIES = [("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")]
PRIORITY_TONES = {"low": "neutral", "normal": "neutral", "high": "warning", "urgent": "danger"}
OPEN = ["new", "in_review"]


def query(db: Session, user):
    owner = aliased(User)
    return (
        select(WorkItem.id, WorkItem.ref, WorkItem.title, WorkItem.account, WorkItem.status,
               WorkItem.priority, WorkItem.owner_id, owner.display_name.label("owner"),
               WorkItem.amount, WorkItem.received_at, WorkItem.updated_at)
        .outerjoin(owner, owner.id == WorkItem.owner_id)
    )


def _update(ctx: ActionContext, **values) -> None:
    ctx.db.execute(update(WorkItem).where(WorkItem.id.in_(ctx.ids))
                   .values(**values, updated_at=utcnow()))


def assign(ctx: ActionContext) -> str:
    owner_id = int(ctx.values["owner_id"]) if ctx.values.get("owner_id") else None
    _update(ctx, owner_id=owner_id)
    return f"Assigned {ctx.count} item(s)."


def set_status(ctx: ActionContext) -> str:
    _update(ctx, status=ctx.values["status"])
    return f"Updated status on {ctx.count} item(s)."


def approve(ctx: ActionContext) -> str:
    _update(ctx, status="approved")
    return f"Approved {ctx.count} item(s)."


def remove(ctx: ActionContext) -> str:
    ctx.db.execute(delete(WorkItem).where(WorkItem.id.in_(ctx.ids)))
    return f"Deleted {ctx.count} item(s)."


def panel(db: Session, user, row: dict) -> dict:
    return {"template": "features/work_item_panel.html",
            "item": db.get(WorkItem, row["id"]),
            "events": audit.history(db, "work_items", row["id"], limit=5)}


GRID = register(GridSpec(
    key="work_items",
    title="Work items",
    path="/work",
    query=query,
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
        Filter("owner_id", "Owner", user_options),
    ],
    views=[
        View("open", "Open", where={"status": OPEN}),
        View("mine", "Assigned to me", where={"owner_id": "$me", "status": OPEN}),
        View("closed", "Closed", where={"status": ["approved", "declined"]}),
        View("all", "All"),
    ],
    actions=[
        Action("new", "New item", scope="none", href="/work/new", tone="primary", icon="plus",
               roles=EDITORS),
        Action("open", "Open", scope="single", href="/work/{id}", icon="external"),
        Action("assign", "Assign", handler=assign, icon="assign", roles=EDITORS,
               fields=[Field("owner_id", "Owner", kind="select",
                             options=lambda db, u: [("", "Unassigned"), *user_options(db)])]),
        Action("status", "Set status", handler=set_status, icon="flag", roles=EDITORS,
               fields=[Field("status", "Status", kind="select", options=STATUSES,
                             required=True)]),
        Action("approve", "Approve", handler=approve, icon="check", roles=EDITORS,
               when={"status": OPEN}, confirm="Approve {count} item(s)?"),
        Action("delete", "Delete", handler=remove, tone="danger", icon="trash",
               roles=ADMINS, confirm="Delete {count} item(s)? This cannot be undone."),
    ],
    default_sort="-received_at",
    row_href="/work/{id}",
    panel=panel,
    panel_title="{ref} · {title}",
    search_placeholder="Search ref, title, account, owner",
    empty_title="No work items match",
    empty_text="Change the view or clear filters to see more.",
    palette=Palette(title="{ref} · {title}", subtitle="{account}", href="/work/{id}",
                    icon="queue"),
))

register_tile(HomeTile("Open work items", GRID, view="open"))
register_tile(HomeTile("Assigned to me", GRID, view="mine", tone="accent"))


router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/work")
def work_list(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, GRID, "work.items",
                            subtitle="Cases waiting for review and decision.")


def _form_ctx(db: Session, item: WorkItem | None, errors: dict | None = None) -> dict:
    return {"item": item, "errors": errors or {}, "statuses": STATUSES,
            "priorities": PRIORITIES, "owners": user_options(db)}


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


@router.get("/work/new", dependencies=[Depends(require_roles(*EDITORS))])
def new_form(request: Request, db: Session = Depends(get_db)):
    return render_page(request, "features/work_item_form.html", "work.new", **_form_ctx(db, None))


@router.post("/work/new", dependencies=[Depends(require_roles(*EDITORS))])
async def create(request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    data, errors = _read_form(await request.form())
    if errors:
        return render_page(request, "features/work_item_form.html", "work.new",
                           status_code=400, **_form_ctx(db, None, errors), values=data)
    # The ref comes from the id, so it is set after the insert assigns one.
    item = WorkItem(ref=f"new-{uuid4().hex}", **data)
    db.add(item)
    db.flush()
    item.ref = f"WI-{item.id:05d}"
    audit.record(db, user.id, "work_items.create", "Created", "work_items", item.id)
    db.commit()
    return RedirectResponse(f"/work/{item.id}", status_code=303)


def _get(db: Session, item_id: int) -> WorkItem:
    item = db.get(WorkItem, item_id)
    if item is None:
        raise HTTPException(404)
    return item


@router.get("/work/{item_id}")
def detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = _get(db, item_id)
    owner = db.get(User, item.owner_id) if item.owner_id else None
    return render_page(request, "features/work_item_detail.html", "work.detail",
                       item=item, owner=owner, events=audit.history(db, "work_items", item.id),
                       spec=GRID, can_edit=request.state.user.has_any(EDITORS),
                       crumb=item.ref)


@router.get("/work/{item_id}/edit", dependencies=[Depends(require_roles(*EDITORS))])
def edit_form(item_id: int, request: Request, db: Session = Depends(get_db)):
    item = _get(db, item_id)
    return render_page(request, "features/work_item_form.html", "work.detail",
                       **_form_ctx(db, item), crumb=item.ref)


@router.post("/work/{item_id}/edit", dependencies=[Depends(require_roles(*EDITORS))])
async def save(item_id: int, request: Request, db: Session = Depends(get_db),
               user=Depends(current_user)):
    item = _get(db, item_id)
    data, errors = _read_form(await request.form())
    if errors:
        return render_page(request, "features/work_item_form.html", "work.detail",
                           status_code=400, **_form_ctx(db, item, errors), values=data,
                           crumb=item.ref)
    changed = {k: v for k, v in data.items() if getattr(item, k) != v}
    for key, value in changed.items():
        setattr(item, key, value)
    if changed:
        audit.record(db, user.id, "work_items.edit", "Edited " + ", ".join(sorted(changed)),
                     "work_items", item.id)
    db.commit()
    return RedirectResponse(f"/work/{item.id}", status_code=303)
