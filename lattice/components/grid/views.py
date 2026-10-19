"""Saved grid views: a user's named grid state, optionally shared with everyone.

A view holds the grid's URL state (built-in view tab, search, filters, sort and
page size) as a query string, so opening one is the same as following a link.
Columns stay a per-user preference. Sharing needs `lattice.views.share`.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

from fastapi import HTTPException

from lattice.components.grid import engine
from lattice.components.grid.spec import GridSpec
from lattice.kernel.database import Db
from lattice.kernel.queries import SQL

SHARE = "lattice.views.share"
MAX_NAME = 80


def clean_state(spec: GridSpec, state: str) -> str:
    """The parts of a grid query string a view may hold, in a stable order."""
    filters = {f"f_{f.key}" for f in spec.filters}
    sorts = {c.key for c in spec.columns} | {"id"}

    def allowed(k: str, v: str) -> bool:
        return ((k == "sort" and v.lstrip("-") in sorts)
                or (k == "size" and v.isdigit() and int(v) in engine.PAGE_SIZES)
                or (k == "view" and spec.view(v) is not None)
                or (k in filters and v != ""))

    keep = [("q", v.strip()) if k == "q" else (k, v)
            for k, v in parse_qsl(state.lstrip("?"))
            if (k == "q" and v.strip()) or allowed(k, v)]
    return urlencode(sorted(keep))


def visible(db: Db, spec: GridSpec, user) -> list[dict]:
    return db.all(SQL.grid_views.visible, grid_key=spec.key, user_id=user.id)


def _get(db: Db, spec: GridSpec, user, view_id: int) -> dict:
    view = db.first(SQL.grid_views.by_id, id=view_id, grid_key=spec.key, user_id=user.id)
    if view is None:
        raise HTTPException(404, detail="That view no longer exists.")
    return view


def _name(db: Db, spec: GridSpec, user, raw, view_id: int = 0) -> str:
    name = str(raw or "").strip()
    if not name:
        raise HTTPException(400, detail="Give the view a name.")
    if len(name) > MAX_NAME:
        raise HTTPException(400, detail=f"Keep the name under {MAX_NAME} characters.")
    if db.value(SQL.grid_views.name_taken, grid_key=spec.key, user_id=user.id, name=name,
                id=view_id):
        raise HTTPException(400, detail=f"You already have a view named {name!r}.")
    return name


def _shared(user, wanted) -> bool:
    if wanted and not user.can(SHARE):
        raise HTTPException(403, detail="You do not have permission to share views.")
    return bool(wanted)


def create(db: Db, spec: GridSpec, user, body: dict) -> int:
    return db.value(SQL.grid_views.create, grid_key=spec.key, user_id=user.id,
                    name=_name(db, spec, user, body.get("name")),
                    state=clean_state(spec, str(body.get("state") or "")),
                    shared=_shared(user, body.get("shared")))


def update(db: Db, spec: GridSpec, user, view_id: int, body: dict) -> None:
    """Rename, re-save or (un)share one of the user's own views."""
    view = _get(db, spec, user, view_id)
    if not view["mine"]:
        raise HTTPException(403, detail="Only the owner can change a view.")
    name = _name(db, spec, user, body["name"], view_id) if "name" in body else view["name"]
    state = clean_state(spec, str(body["state"])) if "state" in body else view["state"]
    shared = _shared(user, body["shared"]) if "shared" in body else view["shared"]
    db.run(SQL.grid_views.update, id=view_id, name=name, state=state, shared=shared)


def delete(db: Db, spec: GridSpec, user, view_id: int) -> None:
    """The owner deletes a view; holders of lattice.views.share also delete shared ones."""
    view = _get(db, spec, user, view_id)
    if not (view["mine"] or user.can(SHARE)):
        raise HTTPException(403, detail="Only the owner can delete this view.")
    db.run(SQL.grid_views.delete, id=view_id)
