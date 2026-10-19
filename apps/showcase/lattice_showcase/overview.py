"""The showcase's start page: what each page shows and what it is built with."""

from __future__ import annotations

from fastapi import APIRouter, Request

from lattice.api import render_page

PAGES = [
    ("Items", "/showcase/items",
     "Every column kind, filters, views, saved views, bulk actions with input, a side panel, "
     "CSV export and Ctrl+J.", "GridSpec"),
    ("Item record page", "/showcase/items/1",
     "Header actions from the grid, properties, a lifecycle stepper, child items, an embedded "
     "grid and history.", "RecordPage"),
    ("New item", "/showcase/items/new",
     "The plain form pattern: server-side validation, then a redirect and a toast.",
     "Forms and feedback"),
    ("Live updates", "/showcase/jobs",
     "A grid that refreshes itself, with actions that depend on each row's state.",
     "GridSpec(poll_seconds=…)"),
    ("Reading pane", "/showcase/inbox",
     "A split list and reading pane, rows only you can see, unread styling, views in the "
     "sidebar.", "GridSpec(layout=\"split\")"),
    ("Charts", "/showcase/charts",
     "Ten chart kinds on the Items grid, following its filters.", "ChartSpec"),
    ("Specs", "/showcase/specs",
     "Documents in the document store, edited with a form drawn from a Pydantic model.",
     "FormSpec, DocumentKind"),
    ("Free-form", "/showcase/freeform",
     "A document with no schema: the form is inferred, and fields can be added.",
     "FormSpec(schema=None)"),
    ("Flows", "/showcase/flows",
     "A stepper, a tree, and a dependency graph with node actions.",
     "Step, TreeNode, Graph"),
]

router = APIRouter()


@router.get("")
def overview(request: Request):
    return render_page(request, "showcase/overview.html", "overview", pages=PAGES)
