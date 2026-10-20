"""Notices: what a claim handler is told, such as a comment on a claim they handle.

Each user sees only their own notices: the grid's query filters on `:user_id`, so the
list, the home tile, export and Ctrl+J all stop at the same boundary.
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
    GridSpec,
    HomeTile,
    Palette,
    View,
    csrf_protect,
    current_user,
    get_db,
    render_grid_page,
    sql_queries,
)

SQL = sql_queries(Path(__file__).parent / "sql").notices


def mark_read(ctx: ActionContext) -> str:
    ctx.db.run(SQL.mark_read, ids=ctx.ids)
    return f"Marked {ctx.count} notice(s) read."


GRID = GridSpec(
    key="showcase.notices", title="Notices", path="/showcase/notices", query=SQL.grid,
    columns=[Column("subject", "Notice", kind="strong", secondary="body", required=True),
             Column("is_read", "Read", kind="bool", width="80px"),
             Column("created_at", "When", kind="ago", width="120px")],
    search=["subject", "body"],
    views=[View("unread", "Unread", where={"is_read": False}), View("all", "All")],
    actions=[Action("read", "Mark read", handler=mark_read, icon="check",
                    when={"is_read": [False]})],
    default_sort="-created_at", row_href="/showcase/notices/{id}",
    palette=Palette("{subject}", "/showcase/notices/{id}", icon="inbox"),
    empty_title="No notices", empty_text="Comments on claims you handle appear here.",
)
TILES = [HomeTile("Unread notices", GRID, view="unread", tone="info")]

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("/notices")
def notices_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "claims.notices",
                            subtitle="What you are told about the claims you handle.")


@router.get("/notices/{notice_id}")
def open_notice(notice_id: int, db: Db = Depends(get_db), user=Depends(current_user)):
    """Mark the notice read and go to what it is about."""
    notice = db.one(SQL.open, id=notice_id, user_id=user.id)
    return RedirectResponse(notice["href"] or "/showcase/notices", status_code=303)


def tell(db: Db, owner_id: int, subject: str, body: str, href: str) -> None:
    db.run(SQL.add, owner_id=owner_id, subject=subject, body=body, href=href)
