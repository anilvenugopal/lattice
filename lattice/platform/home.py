"""Home page and the health check."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from lattice.components import tiles as home_tiles
from lattice.components.manifest import AppManifest
from lattice.kernel.auth.deps import current_user
from lattice.kernel.db import get_db
from lattice.kernel.nav import NavNode
from lattice.kernel.services import audit
from lattice.kernel.web import render_page

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    recent = audit.history(db, limit=8) if user.is_admin else []
    return render_page(request, "pages/home.html", "home", tiles=home_tiles.tiles_for(db, user),
                       recent=recent)


APP = AppManifest(
    key="home", label="Home", routers=[router],
    nav=[NavNode("home", "Home", "/", icon="home", description="Overview and recent activity")],
)
