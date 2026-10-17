---
name: add-grid-page
description: Add a new list screen (records, queue, jobs, messages) to this Lattice app using the standard GridSpec, with nav entry, actions, migration and tests.
---

# Add a grid page

Read `docs/GRID.md` first. Copy the closest example:
`app/features/work_items.py` (table + detail page), `jobs.py` (polling, row-state
actions), `inbox.py` (split reader, per-user rows).

1. **Model.** Add the table to `app/models.py`. Run
   `make revision m="add <table>"`, review the file in `alembic/versions/`, then `make migrate`.
2. **Feature module** `app/features/<area>.py`:
   - `query(db, user)` returning a `select` with labeled columns including `id`.
     Filter rows the user may not see here.
   - Status/priority option lists and a `*_TONES` map, declared once.
   - Action handlers taking `ActionContext`; no commit.
   - `GRID = register(GridSpec(...))`.
   - `router = APIRouter(dependencies=[Depends(csrf_protect)])` and the page route
     returning `render_grid_page(request, db, GRID, "<nav key>", subtitle=...)`.
3. **Navigation.** Add `NavNode`s in `app/nav/manifest.py` (rail icon from `app/icons.py`).
   Detail pages: `hidden=True`, parent = list node.
4. **Wire.** Import the module in `app/main.py` and add it to `FEATURES`.
   Optional: `palette=Palette(...)` for Ctrl+J, `register_tile(HomeTile(...))` for the home page.
5. **Templates** (only if needed): panel body or detail page in `app/templates/features/`,
   built from `components/macros.html`.
6. **Tests** in `tests/test_<area>.py`: page renders for allowed roles, 403 for
   others, each action changes the rows it should and skips ineligible ones.
7. `make lint && make test`.

Do not write a custom table, pager, filter bar, selection script or list endpoint.
