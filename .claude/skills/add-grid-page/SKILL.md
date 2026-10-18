---
name: add-grid-page
description: Add a new list screen (records, queue, jobs, messages) to a Lattice app using the standard GridSpec, with nav entry, actions, migration and tests.
---

# Add a grid page

Read `lattice/help/developer/building-apps/grids.md` first. Copy the closest example in `apps/demo/lattice_demo/`:
`work_items.py` (table + detail page), `jobs.py` (polling, row-state actions),
`inbox.py` (split reader, per-user rows), each with its `sql/<area>.sql`. Import
only from `lattice.api`. Plain SQL, no ORM.

1. **Table.** `make migration schema=<app> m="add <table>"`, write the `CREATE TABLE`
   (in schema `<app>`, timestamps `DEFAULT lattice.utc_now()`), then `make migrate`.
2. **Queries** in `lattice_<app>/sql/<area>.sql`, each `-- name: x` plus a `--`
   comment line:
   - `grid`: a `SELECT` of the row columns including `id`. Filter rows the user may
     not see here, with `:user_id` if rows belong to people.
   - one query per action, e.g. `UPDATE … WHERE id = ANY(:ids)`.
3. **Module** in the app package, e.g. `lattice_<app>/<area>.py`:
   - `SQL = sql_queries(Path(__file__).parent / "sql").<area>`.
   - Status/priority option lists, declared once, used for the Column `labels` and `tones`.
   - Action handlers taking `ActionContext` and running `ctx.db.run(SQL.x, ids=ctx.ids)`;
     never commit (the request is one transaction).
   - `GRID = GridSpec(key="<app>.<area>", path="/<app>/<area>", query=SQL.grid, ...)`.
   - `router = APIRouter(dependencies=[Depends(csrf_protect)])` and the page route
     (`@router.get("/<area>")`, mounted under `/<app>`, `db: Db = Depends(get_db)`) returning
     `render_grid_page(request, db, GRID, "<nav key>", subtitle=...)`.
4. **Manifest.** In the app's `AppManifest`: the router in `routers=`, the grid in
   `grids=`, `NavNode`s in `nav=` (routes start with `/<app>`; detail pages
   `hidden=True`). Optional: `palette=Palette(...)` on the grid for Ctrl+J, and
   `HomeTile(...)` in `tiles=` for the home page.
5. **Templates and styles** (only if needed): in the app's `templates/<app>/`,
   built from `components/macros.html`; styles in the app's stylesheet, scoped to
   `[data-app="<app>"]`.
6. **Tests** in the app's `tests/`: page renders for allowed roles, 403 for
   others, each action changes the rows it should and skips ineligible ones. Set
   up and check rows with named queries in `tests/sql/checks.sql`.
7. `make lint && make test` (Postgres running). The SQL rules test fails on an
   unused or invalid named query, or SQL written in Python.

Do not write a custom table, pager, filter bar, selection script or list endpoint.
