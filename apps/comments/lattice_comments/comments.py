"""Comments on any record of any app, by reference (ADR 0011).

The Comments panel appears on every record page that names its reference kind. Comments
store the record's URN, draw it with `ref()`, and announce `comments.added` so the app that
owns the record can react. This app never imports another.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request

from lattice.api import (
    Action,
    ActionContext,
    Column,
    Db,
    GridSpec,
    Permission,
    RecordPanel,
    Ref,
    audit,
    csrf_protect,
    current_user,
    get_db,
    parse,
    render,
    render_grid_page,
    require,
    resolve_ref,
    sql_queries,
)

SQL = sql_queries(Path(__file__).parent / "sql").comments
READ, WRITE, MODERATE = "comments.read", "comments.write", "comments.moderate"
PERMISSIONS = [
    Permission(READ, "Read comments", "See the Comments panel on records, and the Comments list.",
               default_roles=("viewer", "editor")),
    Permission(WRITE, "Write comments", "Comment on records, and delete your own comments.",
               default_roles=("editor",)),
    Permission(MODERATE, "Moderate comments", "Delete anyone's comments."),
]
MAX_BODY = 4000


def _panel(request: Request, db: Db, subject: Ref) -> dict:
    user = request.state.user
    return {"comments": db.all(SQL.on_subject, subject=subject.urn), "can_write": user.can(WRITE),
            "can_moderate": user.can(MODERATE), "user_id": user.id}


PANEL = RecordPanel("comments.panel", "Comments", "comments/panel.html", kinds="*",
                    load=_panel, permission=READ)


def delete(ctx: ActionContext) -> str:
    ctx.db.run(SQL.delete, ids=ctx.ids)
    return f"Deleted {ctx.count} comment(s)."


GRID = GridSpec(
    key="comments.all", title="Comments", path="/comments", query=SQL.grid, permission=READ,
    columns=[Column("subject", "On", kind="template", template="comments/subject_cell.html",
                    sortable=False),
             Column("body", "Comment"),
             Column("author", "By", kind="user", width="170px"),
             Column("created_at", "When", kind="ago", width="120px")],
    search=["body", "author", "subject"],
    actions=[Action("delete", "Delete", handler=delete, tone="danger", icon="trash",
                    permission=MODERATE, confirm="Delete {count} comment(s)?")],
    default_sort="-created_at", empty_title="No comments yet",
    empty_text="Comment on a record from the Comments panel on its page.",
)

router = APIRouter(dependencies=[Depends(csrf_protect)])


@router.get("", dependencies=[Depends(require(READ))])
def comments_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "comments",
                            subtitle="Every comment, on records from every app.")


def _redraw(request: Request, db: Db, subject: Ref):
    return render(request, "comments/panel.html", subject=subject,
                  values=_panel(request, db, subject))


@router.post("/add", dependencies=[Depends(require(WRITE))])
def add(request: Request, subject: str = Form(), body: str = Form(""),
        db: Db = Depends(get_db), user=Depends(current_user)):
    ref = parse(subject)
    if resolve_ref(db, user, subject) is None:
        raise HTTPException(404, detail="That record does not exist, or you cannot see it.")
    body = body.strip()[:MAX_BODY]
    if body:
        comment_id = db.value(SQL.add, subject=ref.urn, author_id=user.id, body=body)
        audit.record(db, user.id, "comments.added", "Commented", ref.kind, ref.id)
        db.publish("comments.added", subject=ref.urn,
                   data={"comment_id": comment_id, "author_id": user.id,
                         "author": user.display_name, "excerpt": body[:140]})
    return _redraw(request, db, ref)


@router.post("/{comment_id}/delete", dependencies=[Depends(require(WRITE))])
def remove(comment_id: int, request: Request, db: Db = Depends(get_db),
           user=Depends(current_user)):
    comment = db.one(SQL.by_id, id=comment_id)
    if comment["author_id"] != user.id and not user.can(MODERATE):
        raise HTTPException(403, detail="You can delete only your own comments.")
    db.run(SQL.delete, ids=[comment_id])
    ref = parse(comment["subject"])
    audit.record(db, user.id, "comments.deleted", "Deleted a comment", ref.kind, ref.id)
    return _redraw(request, db, ref)
