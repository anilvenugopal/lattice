"""Administration: users, roles, sessions, audit log, system info, UI kit.

Every route requires the admin role. The lists use the standard grid.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.csrf import csrf_protect
from app.auth.deps import current_user, require_roles
from app.auth.passwords import hash_password, policy_errors
from app.auth.roles import ADMIN, ADMINS
from app.auth.sessions import AUTH_METHOD_LABELS, is_active_clause, revoke_user_sessions
from app.auth.sessions import active as active_sessions
from app.db import get_db
from app.grid import (
    REGISTRY,
    Action,
    ActionContext,
    ActionResult,
    Column,
    Field,
    Filter,
    GridSpec,
    View,
    register,
    render_grid_page,
)
from app.models import AuditEvent, Role, User, UserRole, UserSession, utcnow
from app.nav import NODES
from app.services import audit, users
from app.web import flash, render_page

router = APIRouter(prefix="/admin",
                   dependencies=[Depends(csrf_protect), Depends(require_roles(*ADMINS))])


def role_options(db: Session, _user=None) -> list[tuple[str, str]]:
    return [(r.code, r.label) for r in db.scalars(select(Role).order_by(Role.sort_order))]


# ── Users ────────────────────────────────────────────────────────────────────

def users_query(db: Session, user):
    roles = (select(UserRole.user_id, func.group_concat(UserRole.role_code, ", ").label("roles"))
             .group_by(UserRole.user_id).subquery()
             if db.bind.dialect.name == "sqlite" else
             select(UserRole.user_id,
                    func.string_agg(UserRole.role_code, ", ").label("roles"))
             .group_by(UserRole.user_id).subquery())
    return (
        select(User.id, User.display_name, User.email, User.is_active, User.must_change_password,
               func.coalesce(roles.c.roles, "").label("roles"),
               (User.oidc_subject.isnot(None)).label("sso"),
               User.created_at, User.last_login_at)
        .outerjoin(roles, roles.c.user_id == User.id)
    )


def _not_self(ctx: ActionContext) -> list[int]:
    return [i for i in ctx.ids if i != ctx.user.id]


def activate(ctx):
    ctx.db.execute(update(User).where(User.id.in_(ctx.ids)).values(is_active=True))
    return f"Activated {ctx.count} user(s)."


def deactivate(ctx):
    ids = _not_self(ctx)
    ctx.db.execute(update(User).where(User.id.in_(ids)).values(is_active=False))
    for uid in ids:
        revoke_user_sessions(ctx.db, uid)
    skipped = " Your own account was skipped." if len(ids) < ctx.count else ""
    return f"Deactivated {len(ids)} user(s).{skipped}"


def grant_role(ctx):
    role = ctx.values["role"]
    have = set(ctx.db.scalars(select(UserRole.user_id).where(
        UserRole.role_code == role, UserRole.user_id.in_(ctx.ids))))
    for uid in ctx.ids:
        if uid not in have:
            ctx.db.add(UserRole(user_id=uid, role_code=role))
    return f"Granted {role} to {len(set(ctx.ids) - have)} user(s)."


def revoke_role(ctx):
    role = ctx.values["role"]
    ids = _not_self(ctx) if role == ADMIN else ctx.ids
    result = ctx.db.execute(UserRole.__table__.delete().where(
        UserRole.role_code == role, UserRole.user_id.in_(ids)))
    return f"Removed {role} from {result.rowcount} user(s)."


def reset_password(ctx):
    temp = secrets.token_urlsafe(9) + "A1"
    user = ctx.db.get(User, ctx.ids[0])
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    revoke_user_sessions(ctx.db, user.id)
    return ActionResult(f"Temporary password for {user.email}: {temp} (shown once; "
                        "they must change it at next sign-in).", tone="info")


def sign_out_users(ctx):
    n = sum(revoke_user_sessions(ctx.db, uid, keep=ctx.user.session_id) for uid in ctx.ids)
    return f"Revoked {n} session(s)."


USERS = register(GridSpec(
    key="users",
    title="Users",
    path="/admin/users",
    roles=ADMINS,
    query=users_query,
    columns=[
        Column("display_name", "Name", kind="user", secondary="email", required=True),
        Column("email", "Email", hidden=True),
        Column("roles", "Roles", kind="tags"),
        Column("is_active", "Active", kind="bool", width="90px"),
        Column("sso", "SSO", kind="bool", width="80px"),
        Column("must_change_password", "Must change password", kind="bool", hidden=True),
        Column("last_login_at", "Last sign-in", kind="ago", width="140px"),
        Column("created_at", "Created", kind="date", width="120px", hidden=True),
    ],
    search=["display_name", "email", "roles"],
    filters=[Filter("is_active", "Status", [("true", "Active"), ("false", "Inactive")],
                    multiple=False)],
    views=[View("all", "All"), View("active", "Active", where={"is_active": True}),
           View("inactive", "Inactive", where={"is_active": False})],
    actions=[
        Action("new", "New user", scope="none", href="/admin/users/new", tone="primary",
               icon="plus"),
        Action("open", "Open", scope="single", href="/admin/users/{id}", icon="external"),
        Action("grant", "Grant role", handler=grant_role, icon="key",
               fields=[Field("role", "Role", kind="select", options=role_options, required=True)]),
        Action("revoke", "Remove role", handler=revoke_role, icon="x",
               fields=[Field("role", "Role", kind="select", options=role_options, required=True)]),
        Action("activate", "Activate", handler=activate, icon="check",
               when={"is_active": [False]}),
        Action("deactivate", "Deactivate", handler=deactivate, icon="lock", tone="danger",
               when={"is_active": [True]},
               confirm="Deactivate {count} user(s)? They are signed out immediately."),
        Action("reset", "Reset password", scope="single", handler=reset_password, icon="key",
               confirm="Generate a temporary password? The user's sessions end now."),
        Action("signout", "Sign out everywhere", handler=sign_out_users, icon="logout",
               confirm="End all sessions for {count} user(s)?"),
    ],
    default_sort="display_name",
    row_href="/admin/users/{id}",
    panel_title="{display_name}",
    search_placeholder="Search name, email, role",
))


@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, USERS, "admin.users",
                            subtitle="Accounts, roles and access.")


@router.get("/users/new")
def new_user_form(request: Request, db: Session = Depends(get_db)):
    return render_page(request, "admin/user_form.html", "admin.user", target=None,
                       roles=role_options(db), errors={}, values={}, crumb="New user")


@router.post("/users/new")
async def create_user(request: Request, db: Session = Depends(get_db),
                      user=Depends(current_user)):
    form = await request.form()
    values = {"email": users.normalize_email(form.get("email")),
              "display_name": (form.get("display_name") or "").strip(),
              "password": form.get("password") or "",
              "roles": form.getlist("roles")}
    errors = {}
    if "@" not in values["email"]:
        errors["email"] = "Enter a valid email."
    elif users.by_email(db, values["email"]):
        errors["email"] = "A user with this email exists."
    if not values["display_name"]:
        errors["display_name"] = "Name is required."
    if values["password"] and (problems := policy_errors(values["password"])):
        errors["password"] = "; ".join(problems)
    if errors:
        return render_page(request, "admin/user_form.html", "admin.user", target=None,
                           roles=role_options(db), errors=errors, values=values,
                           crumb="New user", status_code=400)
    new = users.create(db, values["email"], values["display_name"],
                       password=values["password"] or None, roles=values["roles"],
                       must_change_password=bool(values["password"]))
    audit.record(db, user.id, "user.created", f"Created {new.email}", "users", new.id,
                 {"roles": new.role_codes})
    db.commit()
    return RedirectResponse(f"/admin/users/{new.id}", status_code=303)


def _user(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404)
    return target


def _user_detail_page(request: Request, db: Session, target: User, errors: dict | None = None,
                      status_code: int = 200):
    sessions = active_sessions(db, target.id)
    events = audit.history(db, "users", target.id, actor_id=target.id, limit=25)
    return render_page(request, "admin/user_detail.html", "admin.user", status_code=status_code,
                       target=target, roles=role_options(db), sessions=sessions, events=events,
                       errors=errors or {}, crumb=target.display_name)


@router.get("/users/{user_id}")
def user_detail(user_id: int, request: Request, db: Session = Depends(get_db)):
    return _user_detail_page(request, db, _user(db, user_id))


@router.post("/users/{user_id}")
async def update_user(user_id: int, request: Request, db: Session = Depends(get_db),
                      user=Depends(current_user)):
    target = _user(db, user_id)
    form = await request.form()
    name = (form.get("display_name") or "").strip()
    if not name:
        return _user_detail_page(request, db, target, {"display_name": "Name is required."}, 400)
    target.display_name = name
    wanted = set(form.getlist("roles")) & users.role_codes(db)
    if target.id == user.id:
        wanted.add(ADMIN)            # admins cannot remove their own admin role
    target.roles = [r for r in target.roles if r.role_code in wanted] + [
        UserRole(role_code=r) for r in wanted - set(target.role_codes)]
    active = form.get("is_active") == "on" or target.id == user.id
    if target.is_active and not active:
        revoke_user_sessions(db, target.id)
    target.is_active = active
    audit.record(db, user.id, "user.updated", f"Updated {target.email}", "users", target.id,
                 {"roles": sorted(wanted), "is_active": active})
    db.commit()
    response = RedirectResponse(f"/admin/users/{user_id}", status_code=303)
    flash(response, request, "Changes saved.")
    return response


# ── Roles ────────────────────────────────────────────────────────────────────

def roles_query(db: Session, user):
    members = (select(UserRole.role_code, func.count().label("members"))
               .group_by(UserRole.role_code).subquery())
    return (select(Role.code.label("id"), Role.label, Role.description, Role.sort_order,
                   func.coalesce(members.c.members, 0).label("members"))
            .outerjoin(members, members.c.role_code == Role.code))


ROLES = register(GridSpec(
    key="roles", title="Roles", path="/admin/roles", roles=ADMINS, query=roles_query,
    columns=[Column("id", "Code", kind="mono", width="120px"),
             Column("label", "Role", kind="strong"),
             Column("description", "Grants"),
             Column("members", "Members", kind="number", align="right", width="100px")],
    selection="none", default_sort="sort_order", export=False, search=["id", "label"],
    panel_title="{label}",
))


@router.get("/roles")
def roles_page(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, ROLES, "admin.roles",
                            subtitle="Roles gate pages, menus and actions. "
                                     "Add a role in a migration, then reference it in roles=.")


# ── Sessions ─────────────────────────────────────────────────────────────────

def sessions_query(db: Session, user):
    return (select(UserSession.id, User.display_name.label("user"), User.email,
                   UserSession.auth_method, UserSession.ip_address, UserSession.user_agent,
                   UserSession.created_at, UserSession.last_seen_at, UserSession.expires_at)
            .join(User, User.id == UserSession.user_id)
            .where(is_active_clause()))


def revoke_sessions(ctx):
    mine = [i for i in ctx.ids if i == ctx.user.session_id]
    ids = [i for i in ctx.ids if i not in mine]
    ctx.db.execute(update(UserSession).where(UserSession.id.in_(ids)).values(revoked_at=utcnow()))
    note = " Your current session was kept." if mine else ""
    return f"Revoked {len(ids)} session(s).{note}"


SESSIONS = register(GridSpec(
    key="sessions", title="Sessions", path="/admin/sessions", roles=ADMINS, query=sessions_query,
    columns=[Column("user", "User", kind="user", secondary="email"),
             Column("email", "Email", hidden=True),
             Column("auth_method", "Method", kind="badge",
                    tones={"password": "neutral", "oidc": "accent"},
                    labels=AUTH_METHOD_LABELS, width="110px"),
             Column("ip_address", "IP address", kind="mono", width="140px"),
             Column("user_agent", "Browser", hidden=True),
             Column("created_at", "Signed in", kind="ago", width="130px"),
             Column("last_seen_at", "Last active", kind="ago", width="130px"),
             Column("expires_at", "Expires", kind="datetime", width="170px", hidden=True)],
    search=["user", "email", "ip_address"],
    filters=[Filter("auth_method", "Method", list(AUTH_METHOD_LABELS.items()))],
    actions=[Action("revoke", "Revoke", handler=revoke_sessions, icon="logout", tone="danger",
                    confirm="Revoke {count} session(s)? Those users are signed out.")],
    default_sort="-last_seen_at", panel_title="{user}", export=False,
))


@router.get("/sessions")
def sessions_page(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, SESSIONS, "admin.sessions",
                            subtitle="Active sign-ins across all users.")


# ── Audit log ────────────────────────────────────────────────────────────────

def audit_query(db: Session, user):
    return (select(AuditEvent.id, AuditEvent.at, AuditEvent.action, AuditEvent.summary,
                   AuditEvent.target_type, AuditEvent.target_id, AuditEvent.detail,
                   func.coalesce(User.display_name, "System").label("actor"))
            .outerjoin(User, User.id == AuditEvent.actor_id))


def action_options(db: Session, _user=None):
    return [(a, a) for a in db.scalars(select(AuditEvent.action).distinct()
                                       .order_by(AuditEvent.action))]


AUDIT = register(GridSpec(
    key="audit", title="Audit log", path="/admin/audit", roles=ADMINS, query=audit_query,
    columns=[Column("at", "When", kind="datetime", width="180px"),
             Column("actor", "Actor", kind="user", width="180px"),
             Column("action", "Event", kind="mono", width="220px"),
             Column("summary", "Summary"),
             Column("target_type", "Target", kind="mono", width="120px", secondary="target_id"),
             Column("target_id", "Target id", hidden=True)],
    search=["actor", "action", "summary", "target_id"],
    filters=[Filter("action", "Event", action_options),
             Filter("target_type", "Target", lambda db, u: [
                 (t, t) for t in db.scalars(select(AuditEvent.target_type).distinct()) if t])],
    selection="none", default_sort="-at", panel_title="{action}",
))


@router.get("/audit")
def audit_page(request: Request, db: Session = Depends(get_db)):
    return render_grid_page(request, db, AUDIT, "admin.audit",
                            subtitle="Sign-ins, account changes and every grid action.")


# ── System and UI kit ────────────────────────────────────────────────────────

@router.get("/system")
def system_page(request: Request, db: Session = Depends(get_db)):
    url = db.bind.url
    counts = {name: db.scalar(select(func.count()).select_from(model)) for name, model in
              (("Users", User), ("Active sessions", UserSession), ("Audit events", AuditEvent))}
    return render_page(request, "admin/system.html", "admin.system",
                       db_url=url.render_as_string(hide_password=True), dialect=url.get_backend_name(),
                       counts=counts, grids=sorted(REGISTRY.values(), key=lambda s: s.key),
                       nodes=NODES)


@router.get("/ui-kit")
def ui_kit(request: Request):
    return render_page(request, "admin/ui_kit.html", "admin.uikit")

