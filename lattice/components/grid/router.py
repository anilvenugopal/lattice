"""Generic grid endpoints, shared by every registered GridSpec.

  GET  /_grid/{key}/rows            table body for the current state (HTMX partial)
  GET  /_grid/{key}/panel/{id}      side panel / reading pane for one row
  POST /_grid/{key}/action/{action} run an action on the selection (JSON)
  POST /_grid/{key}/columns         save the user's hidden columns
  GET  /_grid/{key}/export.csv      current filtered rows as CSV
"""

from __future__ import annotations

import csv
import io
from contextlib import contextmanager
from datetime import date, datetime
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.datastructures import QueryParams

from lattice.components.grid import engine
from lattice.components.grid.render import build_grid, render_panel, resolve_options
from lattice.components.grid.spec import ActionContext, ActionResult, GridSpec
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user
from lattice.kernel.database import Db, get_db
from lattice.kernel.services import audit, preferences
from lattice.kernel.web import render

REGISTRY: dict[str, GridSpec] = {}

router = APIRouter(prefix="/_grid", dependencies=[Depends(csrf_protect)])


def register(spec: GridSpec) -> GridSpec:
    if spec.key in REGISTRY and REGISTRY[spec.key] is not spec:
        raise ValueError(f"Grid key {spec.key!r} is already registered")
    REGISTRY[spec.key] = spec
    return spec


def _spec(key: str, user) -> GridSpec:
    spec = REGISTRY.get(key)
    if spec is None:
        raise HTTPException(404)
    if not user.has_any(spec.roles):
        raise HTTPException(403)
    return spec


@contextmanager
def _bad_state():
    """A request naming a fixed column the grid does not have is a 400, not a server error."""
    try:
        yield
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from None


@router.get("/{key}/rows")
def rows(key: str, request: Request, db: Db = Depends(get_db),
         user=Depends(current_user)):
    spec = _spec(key, user)
    with _bad_state():
        grid = build_grid(request, db, spec,
                          views_in_nav=request.query_params.get("_nav") == "1")
    return render(request, "components/grid_body.html", grid=grid)


@router.get("/{key}/panel/{row_id}")
def panel(key: str, row_id: str, request: Request, db: Db = Depends(get_db),
          user=Depends(current_user)):
    return render_panel(request, db, _spec(key, user), row_id)


def _validated_values(action, raw: dict, db: Db, user) -> dict[str, str]:
    """Values for the action's declared fields, checked against each field's kind and options.

    Raises 400 on a missing required value or a value the field does not allow.
    """
    values = {}
    for fld in action.fields:
        value = str(raw.get(fld.name) or "").strip()
        if not value:
            if fld.required:
                raise HTTPException(400, detail=f"Required: {fld.label}")
            values[fld.name] = ""
            continue
        try:
            if fld.kind == "select":
                if value not in {str(v) for v, _ in resolve_options(fld.options, db, user)}:
                    raise ValueError
            elif fld.kind == "number":
                float(value)
            elif fld.kind == "date":
                date.fromisoformat(value)
        except ValueError:
            raise HTTPException(400, detail=f"Invalid value for {fld.label}.") from None
        values[fld.name] = value
    return values


@router.post("/{key}/action/{action_key}")
async def run_action(key: str, action_key: str, request: Request,
                     db: Db = Depends(get_db), user=Depends(current_user)):
    spec = _spec(key, user)
    action = spec.action(action_key)
    if action is None or action.handler is None:
        raise HTTPException(404)
    if action not in spec.actions_for(user):
        raise HTTPException(403, detail="You do not have permission for this action.")
    body = await request.json()

    if body.get("all"):
        params = QueryParams(parse_qsl(body.get("params", "")))
        gq = engine.GridQuery.from_params(params, spec)
        with _bad_state():
            selected = engine.fetch_all(spec, db, user, gq, engine.MAX_BULK)
    else:
        selected = engine.fetch_by_ids(spec, db, user, list(body.get("ids", []))[:engine.MAX_BULK])

    if action.scope == "single" and len(selected) != 1:
        raise HTTPException(400, detail="Select exactly one row.")
    if action.scope == "multi" and not selected:
        raise HTTPException(400, detail="Select at least one row.")

    eligible = [r for r in selected if action.applies(r)]
    skipped = len(selected) - len(eligible)
    if not eligible and action.scope != "none":
        return JSONResponse({"message": f"{action.label}: none of the selected rows qualify.",
                             "tone": "warning", "refresh": False, "clear": False})

    values = _validated_values(action, body.get("values") or {}, db, user)

    ctx = ActionContext(db=db, user=user, ids=[r["id"] for r in eligible], rows=eligible,
                        values=values)
    result = action.handler(ctx)
    if not isinstance(result, ActionResult):
        result = ActionResult(message=result or f"{action.label}: {ctx.count} updated.")
    if skipped:
        result.message += f" {skipped} skipped (not eligible)."
        result.tone = "warning" if result.tone == "success" else result.tone

    # One audit event per row, so each row's history shows bulk actions too.
    bulk = f" (bulk of {ctx.count})" if ctx.count > 1 else ""
    audit.record_many(db, user.id, f"{spec.key}.{action.key}", f"{action.label}{bulk}",
                      spec.key, ctx.ids or [""], {"values": values} if values else None)
    return JSONResponse({"message": result.message, "tone": result.tone,
                         "refresh": result.refresh, "clear": result.clear_selection,
                         "redirect": result.redirect})


@router.post("/{key}/columns")
async def save_columns(key: str, request: Request, db: Db = Depends(get_db),
                       user=Depends(current_user)):
    spec = _spec(key, user)
    hidden = (await request.json()).get("hidden", [])
    valid = [k for k in hidden if spec.column(k) and not spec.column(k).required]
    preferences.set_pref(db, user.id, f"grid.{spec.key}.hidden", valid)
    return JSONResponse({"hidden": valid})


@router.get("/{key}/export.csv")
def export_csv(key: str, request: Request, db: Db = Depends(get_db),
               user=Depends(current_user)):
    spec = _spec(key, user)
    if not spec.export:
        raise HTTPException(404)
    gq = engine.GridQuery.from_params(request.query_params, spec)
    with _bad_state():
        rows = engine.fetch_all(spec, db, user, gq, engine.MAX_EXPORT)
    columns = [c for c in spec.columns if c.kind != "template"]

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([c.label or c.key for c in columns])
        for row in rows:
            writer.writerow([
                c.labels.get(str(row.get(c.key)), row.get(c.key)) if c.labels else row.get(c.key)
                for c in columns])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return StreamingResponse(generate(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="{spec.key}-{stamp}.csv"'})
