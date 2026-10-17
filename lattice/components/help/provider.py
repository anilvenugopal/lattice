"""The "Help" source in Ctrl+J: help topics matching the query, previewed in the palette."""

from __future__ import annotations

from fastapi import HTTPException, Request

from lattice.components.help import search as help_search
from lattice.components.help.content import HELP
from lattice.components.search.providers import SearchProvider, SearchResult
from lattice.kernel.web import render


def _search(db, user, q: str, limit: int) -> list[SearchResult]:
    if not q:
        return []
    return [SearchResult(id=f"{h.topic.app}/{h.topic.slug}".rstrip("/"), title=h.topic.title,
                         subtitle=" · ".join(filter(None, [HELP[h.topic.app].label, h.topic.summary])),
                         href=h.topic.url)
            for h in help_search.search(q, user, limit)]


def _preview(request: Request, db, item_id: str):
    app_key, _, slug = item_id.partition("/")
    app = HELP.get(app_key)
    topic = app.topics.get(slug) if app else None
    if topic is None or not topic.visible_to(request.state.user):
        raise HTTPException(404)
    return render(request, "help/preview.html", topic=topic, app_help=app)


PROVIDER = SearchProvider(
    key="help", label="Help", icon="info", search=_search,
    count=lambda db, user, q: len(help_search.search(q, user, limit=1000)) if q else 0,
    preview=_preview,
)
