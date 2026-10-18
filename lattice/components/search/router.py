"""Ctrl+J endpoints. Providers are in providers.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from lattice.components.search import providers as search_providers
from lattice.kernel.auth.deps import current_user
from lattice.kernel.database import Db, get_db
from lattice.kernel.web import render

router = APIRouter()

RESULTS_PER_PROVIDER = 5
RESULTS_ONE_PROVIDER = 30


@router.get("/_search")
def search(request: Request, q: str = "", provider: str = "", db: Db = Depends(get_db),
           user=Depends(current_user)):
    """Ctrl+J body: provider filters with counts, and results (all providers, or one)."""
    q = q.strip()
    providers = search_providers.providers_for(user)
    if provider and provider not in {p.key for p in providers}:
        provider = ""
    shown = [p for p in providers if p.key == provider] if provider else providers
    limit = RESULTS_ONE_PROVIDER if provider else RESULTS_PER_PROVIDER
    counts = {p.key: p.count(db, user, q) for p in providers}
    groups = [(p, results, counts[p.key]) for p in shown
              if (results := p.search(db, user, q, limit))]
    return render(request, "components/palette_body.html", q=q, provider=provider,
                  filters=[(p, counts[p.key]) for p in providers], groups=groups)


@router.get("/_search/preview/{provider}/{item_id:path}")
def search_preview(provider: str, item_id: str, request: Request, db: Db = Depends(get_db),
                   user=Depends(current_user)):
    return search_providers.provider_for(user, provider).preview(request, db, item_id)
