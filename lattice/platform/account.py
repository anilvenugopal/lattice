"""Account > Preferences, Profile, Security for the signed-in user."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user
from lattice.kernel.auth.sessions import active as active_sessions
from lattice.kernel.auth.sessions import revoke_session, revoke_user_sessions
from lattice.kernel.db import get_db
from lattice.kernel.models import User, UserSession
from lattice.kernel.nav import NODES
from lattice.kernel.services import audit, preferences
from lattice.kernel.web import render_page, toast

router = APIRouter(prefix="/account", dependencies=[Depends(csrf_protect)])


def _landing_choices(user) -> list[tuple[str, str]]:
    return [(n.route, n.label) for n in NODES
            if n.parent is None and not n.bottom and user.has_any(n.roles)]


@router.get("/preferences")
def preferences_page(request: Request, user=Depends(current_user)):
    return render_page(request, "account/preferences.html", "account.preferences",
                       values={k: preferences.get(user, k) for k in preferences.DEFAULTS},
                       choices={**preferences.CHOICES, "landing_page": _landing_choices(user)})


@router.post("/preferences")
async def save_preferences(request: Request, db: Session = Depends(get_db),
                           user=Depends(current_user)):
    """Saves the keys present in the form; the theme button posts only `theme`."""
    form = await request.form()
    allowed = {**preferences.CHOICES, "landing_page": _landing_choices(user)}
    for key, choices in allowed.items():
        if key in form and (value := preferences.choice(key, form[key], choices)) is not None:
            preferences.set_pref(db, user.id, key, value)
    db.commit()
    # Full reload so theme and density apply to the shell.
    return Response(headers={"HX-Refresh": "true"})


@router.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    return render_page(request, "account/profile.html", "account.profile",
                       profile=db.get(User, user.id))


@router.post("/profile")
def save_profile(request: Request, display_name: str = Form(...), db: Session = Depends(get_db),
                 user=Depends(current_user)):
    row = db.get(User, user.id)
    name = display_name.strip()
    if not name:
        return Response(status_code=400, headers=toast("Display name is required.", "danger"))
    row.display_name = name[:255]
    audit.record(db, user.id, "user.profile_updated", f"{row.email} updated their profile",
                 "users", user.id)
    db.commit()
    return Response(headers={"HX-Refresh": "true"})


@router.get("/security")
def security_page(request: Request, db: Session = Depends(get_db), user=Depends(current_user)):
    sessions = active_sessions(db, user.id)
    return render_page(request, "account/security.html", "account.security", sessions=sessions)


@router.post("/sessions/{session_id}/revoke")
def revoke_one(session_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    sess = db.get(UserSession, session_id)
    if sess and sess.user_id == user.id:
        revoke_session(db, session_id)
        audit.record(db, user.id, "user.session_revoked", "Signed out one of their sessions",
                     "users", user.id, {"auth_method": sess.auth_method})
        db.commit()
    if session_id == user.session_id:
        return Response(headers={"HX-Redirect": "/auth/login"})
    return Response(headers={"HX-Refresh": "true"})


@router.post("/sessions/revoke-others")
def revoke_others(db: Session = Depends(get_db), user=Depends(current_user)):
    count = revoke_user_sessions(db, user.id, keep=user.session_id)
    audit.record(db, user.id, "user.session_revoked", f"Signed out {count} other session(s)",
                 "users", user.id)
    db.commit()
    return Response(headers={**toast(f"Signed out {count} other session(s)."), "HX-Refresh": "true"})


@router.get("/")
def account_root():
    return RedirectResponse("/account/preferences")
