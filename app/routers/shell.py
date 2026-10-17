"""Home page, Ctrl+J search (providers in app/search.py), and the health check."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import search as search_providers
from app.auth.deps import current_user
from app.db import get_db
from app.services import audit
from app.services import home as home_tiles
from app.web import render, render_page

router = APIRouter()

RESULTS_PER_PROVIDER = 5
RESULTS_ONE_PROVIDER = 30


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    recent = audit.history(db, limit=8) if user.is_admin else []
    return render_page(request, "pages/home.html", "home", tiles=home_tiles.tiles_for(db, user),
                       recent=recent)


@router.get("/_search")
def search(request: Request, q: str = "", provider: str = "", db: Session = Depends(get_db),
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


@router.get("/_search/preview/{provider}/{item_id}")
def search_preview(provider: str, item_id: str, request: Request, db: Session = Depends(get_db),
                   user=Depends(current_user)):
    return search_providers.provider_for(user, provider).preview(request, db, item_id)
