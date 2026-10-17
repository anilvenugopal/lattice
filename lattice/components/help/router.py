"""Help pages: the help center, each app's help home and topics, and contextual help."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from lattice.components.help import search as help_search
from lattice.components.help.content import HELP, AppHelp, Topic, target_for
from lattice.kernel.auth.deps import current_user
from lattice.kernel.nav import BY_KEY
from lattice.kernel.web import render_page

router = APIRouter(prefix="/help")


@router.get("")
def center(request: Request, user=Depends(current_user)):
    apps = [a for a in HELP.values() if a.home.visible_to(user)]
    return render_page(request, "help/center.html", "help", apps=apps)


@router.get("/search")
def search(request: Request, q: str = "", user=Depends(current_user)):
    hits = help_search.search(q.strip(), user, limit=50) if q.strip() else []
    return render_page(request, "help/search.html", "help", q=q.strip(), hits=hits,
                       labels={k: a.label for k, a in HELP.items()}, title="Search help")


@router.get("/for/{nav_key}")
def for_page(nav_key: str, user=Depends(current_user)):
    """Help for the page the user is on (F1, Help menu): its mapped topic or its app's home."""
    node = BY_KEY.get(nav_key)
    return RedirectResponse(target_for(nav_key, node.app or "lattice") if node else "/help",
                            status_code=303)


def _app(key: str) -> AppHelp:
    app = HELP.get(key)
    if app is None:
        raise HTTPException(404)
    return app


@router.get("/{app_key}/_assets/{path:path}")
def asset(app_key: str, path: str, user=Depends(current_user)):
    root = _app(app_key).root.resolve()
    file = (root / path).resolve()
    if not file.is_relative_to(root) or not file.is_file() or file.suffix == ".md":
        raise HTTPException(404)
    return FileResponse(file)


@router.get("/{app_key}")
@router.get("/{app_key}/{slug:path}")
def topic(app_key: str, request: Request, slug: str = "", user=Depends(current_user)):
    app = _app(app_key)
    page: Topic | None = app.topics.get(slug.strip("/"))
    if page is None or not page.visible_to(user):
        raise HTTPException(404, detail="There is no help topic at this address.")
    previous, following = app.neighbours(page, user)
    return render_page(request, "help/topic.html", "help", crumb=f"{app.label} help", app_help=app,
                       topic=page, previous=previous, following=following,
                       title=page.title, user=user)
