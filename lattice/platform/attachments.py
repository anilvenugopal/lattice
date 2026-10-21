"""Attachments on any record (ADR 0017): the panel on every record page with a reference
kind, uploading, downloading and previewing, and Administration › Attachments.

The service is lattice/kernel/services/attachments.py; files are in the file store.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile

from lattice.components.grid import Action, ActionContext, Column, GridSpec, render_grid_page
from lattice.components.manifest import AppManifest
from lattice.components.record import RecordPanel
from lattice.components.references import Ref, parse, resolve
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user, require
from lattice.kernel.auth.permissions import Permission
from lattice.kernel.config import settings
from lattice.kernel.database import Db, get_db
from lattice.kernel.queries import SQL
from lattice.kernel.services import attachments, audit, files
from lattice.kernel.services.notifications import NotificationKind
from lattice.kernel.web import render, toast

ADD, MANAGE, BROWSE = "lattice.attachments.add", "lattice.attachments.manage", "lattice.folders.browse"
PERMISSIONS = [
    Permission(ADD, "Add attachments",
               "Attach files to records you can open, and delete the files you attached.",
               default_roles=("editor",)),
    Permission(MANAGE, "Manage attachments",
               "Delete anyone's attachments, and see every file in Administration › Attachments."),
    Permission(BROWSE, "Browse shared folders",
               "Browse the site's mounted shares with the folder picker, and create folders there.",
               default_roles=("editor",)),
]
CHUNK = 1024 * 1024


def _panel(request: Request, db: Db, subject: Ref) -> dict:
    user = request.state.user
    return {"files": attachments.on_subject(db, subject.urn), "can_add": user.can(ADD),
            "can_manage": user.can(MANAGE), "user_id": user.id, "inline": attachments.INLINE,
            "max_mb": settings.attachment_max_mb,
            "accept": ",".join(f".{t}" for t in sorted(attachments.allowed_types()))}


PANEL = RecordPanel("attachments.panel", "Attachments", "attachments/panel.html", kinds="*",
                    load=_panel)

router = APIRouter(dependencies=[Depends(csrf_protect)])


def _redraw(request: Request, db: Db, ref: Ref, message: str = "", tone: str = "success"):
    return render(request, "attachments/panel.html", subject=ref, values=_panel(request, db, ref),
                  headers=toast(message, tone) if message else None)


def _record(db: Db, user, subject: str) -> Ref:
    """The record, if this user may open it; else 404."""
    if resolve(db, user, subject) is None:
        raise HTTPException(404, detail="That record does not exist, or you cannot see it.")
    return parse(subject)


async def _chunks(upload: UploadFile):
    out = []
    while chunk := await upload.read(CHUNK):
        out.append(chunk)
    return out


@router.post("/add", dependencies=[Depends(require(ADD))])
async def add(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    limit = settings.attachment_max_mb * 1024 * 1024
    if int(request.headers.get("content-length") or 0) > 10 * limit:
        raise HTTPException(413, detail=f"Attach at most {settings.attachment_max_mb} MB a file.")
    form = await request.form()
    ref = _record(db, user, str(form.get("subject", "")))
    added, refused = [], []
    for upload in form.getlist("files"):
        if not isinstance(upload, UploadFile) or not upload.filename:
            continue
        try:
            row = attachments.add(db, user.id, ref.urn, upload.filename, await _chunks(upload))
        except attachments.Refused as exc:
            refused.append(str(exc))
            continue
        added.append(row["name"])
        audit.record(db, user.id, "attachments.added", f"Attached {row['name']}", ref.kind, ref.id)
        db.publish("attachments.added", subject=ref.urn,
                   data={"attachment_id": row["id"], "name": row["name"], "size": row["size"],
                         "author": user.display_name, "author_id": user.id})
    if refused:
        return _redraw(request, db, ref, "; ".join(refused), "danger")
    return _redraw(request, db, ref, f"Attached {', '.join(added)}." if added else "")


# ── The folder picker: browsing mounted shares (ADR 0017) ───────────────────

def _store(key: str) -> files.FileStore:
    store = files.FOLDER_STORES.get(key)
    if store is None:
        raise HTTPException(404, detail="No such folder store.")
    return store


@router.get("/folders", dependencies=[Depends(require(BROWSE))])
def folder_stores():
    return {"stores": [{"key": key, "label": s.label} for key, s in files.FOLDER_STORES.items()]}


@router.get("/folders/{store_key}", dependencies=[Depends(require(BROWSE))])
def folders(store_key: str, path: str = ""):
    """One folder of a share: where it is, and the folders inside it."""
    store = _store(store_key)
    try:
        inside = store.list(path)
    except ValueError as exc:                # a bad path: the store's own error
        raise HTTPException(400, detail=str(exc)) from None
    except Exception as exc:                 # the store did not answer (SharePoint, a share)
        raise HTTPException(502, detail=f"{store.label} did not answer: {exc}") from None
    parts = [p for p in path.strip("/").split("/") if p]
    crumbs = [{"name": store.label, "path": ""}] + [
        {"name": part, "path": "/".join(parts[:i + 1])} for i, part in enumerate(parts)]
    return {"store": store_key, "label": store.label, "path": "/".join(parts), "crumbs": crumbs,
            "folders": [{"name": f.name, "path": f.path} for f in inside]}


@router.post("/folders/{store_key}/new", dependencies=[Depends(require(BROWSE))])
async def new_folder(store_key: str, request: Request, user=Depends(current_user)):
    body = await request.json()
    store = _store(store_key)
    try:
        made = store.make_folder(str(body.get("path", "")), str(body.get("name", "")))
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(502, detail=f"{store.label} did not answer: {exc}") from None
    return {"name": made.name, "path": made.path}


@router.get("/{attachment_id}")
def download(attachment_id: int, inline: bool = False, db: Db = Depends(get_db),
             user=Depends(current_user)):
    """The file, as a download; images and PDFs may be shown in the browser (?inline=1)."""
    row = attachments.get(db, attachment_id)
    if row is None:
        raise HTTPException(404)
    _record(db, user, row["subject"])
    shown = inline and row["content_type"] in attachments.INLINE
    try:
        handle = files.attachments_store().open(row["store_key"])
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, detail="The file is missing from the store.") from None

    def stream():
        with handle:
            while chunk := handle.read(CHUNK):
                yield chunk
    name = quote(row["name"])
    return StreamingResponse(stream(), media_type=row["content_type"] if shown else "application/octet-stream",
                             headers={"Content-Disposition": f"{'inline' if shown else 'attachment'}; "
                                                            f"filename*=UTF-8''{name}",
                                      "Content-Length": str(row["size"]),
                                      "X-Content-Type-Options": "nosniff",
                                      "Content-Security-Policy": "sandbox",
                                      "Cache-Control": "private, max-age=300"})


@router.post("/{attachment_id}/delete")
def delete(attachment_id: int, request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    row = attachments.get(db, attachment_id)
    if row is None:
        raise HTTPException(404)
    ref = _record(db, user, row["subject"])
    if not (user.can(MANAGE) or (user.can(ADD) and row["added_by"] == user.id)):
        raise HTTPException(403, detail="You may delete only the files you attached.")
    attachments.remove(db, attachment_id)
    audit.record(db, user.id, "attachments.removed", f"Removed {row['name']}", ref.kind, ref.id)
    db.publish("attachments.removed", subject=ref.urn,
               data={"attachment_id": attachment_id, "name": row["name"], "author_id": user.id})
    return _redraw(request, db, ref, f"Removed {row['name']}.")


# ── Administration › Attachments ─────────────────────────────────────────────

def remove_selected(ctx: ActionContext) -> str:
    for attachment_id in ctx.ids:
        attachments.remove(ctx.db, attachment_id)
    return f"Removed {ctx.count} file(s)."


GRID = GridSpec(
    key="attachments", title="Attachments", path="/admin/attachments", query=SQL.attachments.grid,
    permission=MANAGE,
    columns=[Column("name", "File", kind="strong", secondary="content_type", required=True,
                    href="/attachments/{id}"),
             Column("subject", "On", kind="template", template="attachments/subject_cell.html",
                    sortable=False, width="240px"),
             Column("size", "Size", kind="number", align="right", width="110px"),
             Column("added_by_name", "Added by", kind="user", width="160px"),
             Column("created_at", "Added", kind="ago", width="110px")],
    search=["name", "subject", "added_by_name"],
    actions=[Action("remove", "Remove", handler=remove_selected, icon="trash", tone="danger",
                    confirm="Remove {count} file(s) for good?")],
    default_sort="-created_at", export=False,
    empty_title="No attachments yet", empty_text="Files attached to records appear here.",
)
admin_router = APIRouter(dependencies=[Depends(csrf_protect)])


@admin_router.get("/attachments", dependencies=[Depends(require(MANAGE))])
def attachments_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, GRID, "admin.attachments",
                            subtitle=f"Every file attached to a record. Kept in {settings.files_dir}.")


APP = AppManifest(
    key="attachments", label="Attachments", routers=[router], panels=[PANEL],
    permissions=PERMISSIONS, publishes=["attachments.added", "attachments.removed"],
    notifications=[NotificationKind(
        "attachments.on_followed", "New file on a record you follow",
        "Someone attached a file to a record you follow.",
        event="attachments.added", title="{author} attached {name}")],
)
