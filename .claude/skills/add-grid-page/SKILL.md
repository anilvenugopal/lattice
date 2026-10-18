---
name: add-grid-page
description: Add a new list screen (records, queue, jobs, messages) to a Lattice app using the standard GridSpec, with nav entry, actions, migration and tests.
---

# Add a grid page

Read `lattice/help/developer/building-apps/grids.md` first. Copy the closest example in `apps/demo/lattice_demo/`:
`work_items.py` (table + detail page), `jobs.py` (polling, row-state actions),
`inbox.py` (split reader, per-user rows). Import only from `lattice.api`.

1. **Model.** Add the table to the app's `models.py` (`from lattice.api import Base`).
   Run `make revision m="add <table>"`, review the file in `alembic/versions/`, then
   `make migrate`.
2. **Module** in the app package, e.g. `lattice_<app>/<area>.py`:
   - `query(db, user)` returning a `select` with labeled columns including `id`.
     Filter rows the user may not see here.
   - Status/priority option lists, declared once, used for the Column `labels` and `tones`.
   - Action handlers taking `ActionContext`; no commit.
   - `GRID = GridSpec(key="<app>.<area>", path="/<app>/<area>", ...)`.
   - `router = APIRouter(dependencies=[Depends(csrf_protect)])` and the page route
     (`@router.get("/<area>")`, mounted under `/<app>`) returning
     `render_grid_page(request, db, GRID, "<nav key>", subtitle=...)`.
3. **Manifest.** In the app's `AppManifest`: the router in `routers=`, the grid in
   `grids=`, `NavNode`s in `nav=` (routes start with `/<app>`; detail pages
   `hidden=True`). Optional: `palette=Palette(...)` on the grid for Ctrl+J, and
   `HomeTile(...)` in `tiles=` for the home page.
4. **Templates and styles** (only if needed): in the app's `templates/<app>/`,
   built from `components/macros.html`; styles in the app's stylesheet, scoped to
   `[data-app="<app>"]`.
5. **Tests** in the app's `tests/`: page renders for allowed roles, 403 for
   others, each action changes the rows it should and skips ineligible ones.
6. `make lint && make test`.

Do not write a custom table, pager, filter bar, selection script or list endpoint.
