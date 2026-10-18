"""Administration: users, roles, sessions, audit log, system info, UI kit.

Every route requires the admin role. The lists use the standard grid.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from lattice.components.grid import (
    REGISTRY,
    Action,
    ActionContext,
    ActionResult,
    Column,
    Field,
    Filter,
    GridSpec,
    View,
    render_grid_page,
)
from lattice.components.manifest import AppManifest
from lattice.kernel.auth.csrf import csrf_protect
from lattice.kernel.auth.deps import current_user, require
from lattice.kernel.auth.passwords import hash_password, policy_errors
from lattice.kernel.auth.permissions import Permission
from lattice.kernel.auth.roles import ADMIN
from lattice.kernel.auth.sessions import AUTH_METHOD_LABELS, revoke_sessions, revoke_user_sessions
from lattice.kernel.auth.sessions import active as active_sessions
from lattice.kernel.database import Db, engine, get_db
from lattice.kernel.nav import NODES, NavNode
from lattice.kernel.queries import SQL
from lattice.kernel.services import audit, users
from lattice.kernel.web import flash, render_page

router = APIRouter(dependencies=[Depends(csrf_protect)])
USERS_MANAGE, ROLES_MANAGE = "lattice.users.manage", "lattice.roles.manage"
SESSIONS_MANAGE, AUDIT_VIEW, SYSTEM_VIEW = ("lattice.sessions.manage", "lattice.audit.view",
                                            "lattice.system.view")


# ── Users ────────────────────────────────────────────────────────────────────

def _not_self(ctx: ActionContext) -> list[int]:
    return [i for i in ctx.ids if i != ctx.user.id]


def activate(ctx):
    ctx.db.run(SQL.users.set_active, ids=ctx.ids, active=True)
    return f"Activated {ctx.count} user(s)."


def deactivate(ctx):
    ids = _not_self(ctx)
    ctx.db.run(SQL.users.set_active, ids=ids, active=False)
    revoke_user_sessions(ctx.db, ids)
    skipped = " Your own account was skipped." if len(ids) < ctx.count else ""
    return f"Deactivated {len(ids)} user(s).{skipped}"


def grant_role(ctx):
    role = ctx.values["role"]
    granted = ctx.db.run(SQL.users.grant_role, ids=ctx.ids, role=role)
    return f"Granted {role} to {granted} user(s)."


def revoke_role(ctx):
    role = ctx.values["role"]
    ids = _not_self(ctx) if role == ADMIN else ctx.ids
    removed = ctx.db.run(SQL.users.remove_role, ids=ids, role=role)
    return f"Removed {role} from {removed} user(s)."


def reset_password(ctx):
    temp = secrets.token_urlsafe(9) + "A1"
    user = users.by_id(ctx.db, ctx.ids[0])
    ctx.db.run(SQL.users.set_password, id=user["id"], password_hash=hash_password(temp),
               must_change=True)
    revoke_user_sessions(ctx.db, [user["id"]])
    return ActionResult(f"Temporary password for {user['email']}: {temp} (shown once; "
                        "they must change it at next sign-in).", tone="info")


def sign_out_users(ctx):
    n = revoke_user_sessions(ctx.db, ctx.ids, keep=ctx.user.session_id)
    return f"Revoked {n} session(s)."


USERS = GridSpec(
    key="users",
    title="Users",
    path="/admin/users",
    permission=USERS_MANAGE,
    query=SQL.admin.users_grid,
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
               fields=[Field("role", "Role", kind="select", options=users.role_options, required=True)]),
        Action("revoke", "Remove role", handler=revoke_role, icon="x",
               fields=[Field("role", "Role", kind="select", options=users.role_options, required=True)]),
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
)


@router.get("/users", dependencies=[Depends(require(USERS_MANAGE))])
def users_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, USERS, "admin.users",
                            subtitle="Accounts, roles and access.")


@router.get("/users/new", dependencies=[Depends(require(USERS_MANAGE))])
def new_user_form(request: Request, db: Db = Depends(get_db)):
    return render_page(request, "admin/user_form.html", "admin.user", target=None,
                       roles=users.role_options(db), errors={}, values={}, crumb="New user")


@router.post("/users/new", dependencies=[Depends(require(USERS_MANAGE))])
async def create_user(request: Request, db: Db = Depends(get_db),
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
                           roles=users.role_options(db), errors=errors, values=values,
                           crumb="New user", status_code=400)
    new = users.create(db, values["email"], values["display_name"],
                       password=values["password"] or None, roles=values["roles"],
                       must_change_password=bool(values["password"]))
    audit.record(db, user.id, "user.created", f"Created {new['email']}", "users", new["id"],
                 {"roles": new["roles"]})
    return RedirectResponse(f"/admin/users/{new['id']}", status_code=303)


def _user_detail_page(request: Request, db: Db, target: dict, errors: dict | None = None,
                      status_code: int = 200):
    sessions = active_sessions(db, target["id"])
    events = audit.history(db, "users", target["id"], actor_id=target["id"], limit=25)
    return render_page(request, "admin/user_detail.html", "admin.user", status_code=status_code,
                       target=target, sign_in_methods=users.sign_in_methods(target),
                       roles=users.role_options(db), sessions=sessions, events=events,
                       errors=errors or {}, crumb=target["display_name"])


@router.get("/users/{user_id}", dependencies=[Depends(require(USERS_MANAGE))])
def user_detail(user_id: int, request: Request, db: Db = Depends(get_db)):
    return _user_detail_page(request, db, users.by_id(db, user_id))


@router.post("/users/{user_id}", dependencies=[Depends(require(USERS_MANAGE))])
async def update_user(user_id: int, request: Request, db: Db = Depends(get_db),
                      user=Depends(current_user)):
    target = users.by_id(db, user_id)
    form = await request.form()
    name = (form.get("display_name") or "").strip()
    if not name:
        return _user_detail_page(request, db, target, {"display_name": "Name is required."}, 400)
    db.run(SQL.users.rename, id=user_id, display_name=name)
    wanted = set(form.getlist("roles")) & users.role_codes(db)
    if user_id == user.id:
        wanted.add(ADMIN)            # admins cannot remove their own admin role
    db.run(SQL.users.keep_only_roles, user_id=user_id, roles=sorted(wanted))
    db.run(SQL.users.add_roles, user_id=user_id, roles=sorted(wanted))
    active = form.get("is_active") == "on" or user_id == user.id
    if target["is_active"] and not active:
        revoke_user_sessions(db, [user_id])
    db.run(SQL.users.set_active, ids=[user_id], active=active)
    audit.record(db, user.id, "user.updated", f"Updated {target['email']}", "users", user_id,
                 {"roles": sorted(wanted), "is_active": active})
    response = RedirectResponse(f"/admin/users/{user_id}", status_code=303)
    flash(response, request, "Changes saved.")
    return response


# ── Roles ────────────────────────────────────────────────────────────────────

ROLES = GridSpec(
    key="roles", title="Roles", path="/admin/roles", permission=ROLES_MANAGE,
    query=SQL.admin.roles_grid,
    columns=[Column("id", "Code", kind="mono", width="120px"),
             Column("label", "Role", kind="strong"),
             Column("description", "Grants"),
             Column("members", "Members", kind="number", align="right", width="100px")],
    selection="none", default_sort="sort_order", export=False, search=["id", "label"],
    panel_title="{label}",
)


@router.get("/roles", dependencies=[Depends(require(ROLES_MANAGE))])
def roles_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, ROLES, "admin.roles",
                            subtitle="Roles gate pages, menus and actions. "
                                     "Add a role in a migration, then reference it in roles=.")


# ── Sessions ─────────────────────────────────────────────────────────────────

def revoke_selected_sessions(ctx):
    ids = [i for i in ctx.ids if i != ctx.user.session_id]
    revoke_sessions(ctx.db, ids)
    note = " Your current session was kept." if len(ids) < ctx.count else ""
    return f"Revoked {len(ids)} session(s).{note}"


SESSIONS = GridSpec(
    key="sessions", title="Sessions", path="/admin/sessions", permission=SESSIONS_MANAGE,
    query=SQL.sessions.grid,
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
    actions=[Action("revoke", "Revoke", handler=revoke_selected_sessions, icon="logout", tone="danger",
                    confirm="Revoke {count} session(s)? Those users are signed out.")],
    default_sort="-last_seen_at", panel_title="{user}", export=False,
)


@router.get("/sessions", dependencies=[Depends(require(SESSIONS_MANAGE))])
def sessions_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, SESSIONS, "admin.sessions",
                            subtitle="Active sign-ins across all users.")


# ── Audit log ────────────────────────────────────────────────────────────────

def _options(db: Db, query) -> list[tuple[str, str]]:
    return [(r["value"], r["label"]) for r in db.all(query)]


AUDIT = GridSpec(
    key="audit", title="Audit log", path="/admin/audit", permission=AUDIT_VIEW,
    query=SQL.audit.grid,
    columns=[Column("at", "When", kind="datetime", width="180px"),
             Column("actor", "Actor", kind="user", width="180px"),
             Column("action", "Event", kind="mono", width="220px"),
             Column("summary", "Summary"),
             Column("target_type", "Target", kind="mono", width="120px", secondary="target_id"),
             Column("target_id", "Target id", hidden=True)],
    search=["actor", "action", "summary", "target_id"],
    filters=[Filter("action", "Event", lambda db, u: _options(db, SQL.audit.actions)),
             Filter("target_type", "Target", lambda db, u: _options(db, SQL.audit.target_types))],
    selection="none", default_sort="-at", panel_title="{action}",
)


@router.get("/audit", dependencies=[Depends(require(AUDIT_VIEW))])
def audit_page(request: Request, db: Db = Depends(get_db)):
    return render_grid_page(request, db, AUDIT, "admin.audit",
                            subtitle="Sign-ins, account changes and every grid action.")


# ── System and UI kit ────────────────────────────────────────────────────────

@router.get("/system", dependencies=[Depends(require(SYSTEM_VIEW))])
def system_page(request: Request, db: Db = Depends(get_db)):
    url = engine().url
    totals = db.one(SQL.admin.counts)
    counts = {"Users": totals["users"], "Active sessions": totals["active_sessions"],
              "Audit events": totals["audit_events"]}
    return render_page(request, "admin/system.html", "admin.system",
                       db_url=url.render_as_string(hide_password=True), dialect=url.get_backend_name(),
                       counts=counts, grids=sorted(REGISTRY.values(), key=lambda s: s.key),
                       nodes=NODES)


@router.get("/ui-kit", dependencies=[Depends(require(SYSTEM_VIEW))])
def ui_kit(request: Request):
    return render_page(request, "admin/ui_kit.html", "admin.uikit")



PERMISSIONS = [
    Permission(USERS_MANAGE, "Manage users",
               "Administration › Users: create and edit users, grant roles, deactivate, "
               "reset passwords."),
    Permission(ROLES_MANAGE, "Manage roles",
               "Administration › Roles: create and edit roles and their permissions."),
    Permission(SESSIONS_MANAGE, "Manage sessions",
               "Administration › Sessions: see and revoke anyone's sessions."),
    Permission(AUDIT_VIEW, "Read the audit log",
               "Administration › Audit log: every change, by anyone."),
    Permission(SYSTEM_VIEW, "See system information",
               "Administration › System and UI kit."),
]

APP = AppManifest(
    key="admin", label="Administration", routers=[router], permissions=PERMISSIONS,
    grids=[USERS, ROLES, SESSIONS, AUDIT],
    nav=[
        NavNode("admin", "Administration", "/admin/users", icon="shield",
                description="Users, roles, sessions, audit log and system settings"),
        NavNode("admin.users", "Users", "/admin/users", parent="admin", permission=USERS_MANAGE,
                keywords="accounts people"),
        NavNode("admin.user", "User", "/admin/users", parent="admin.users", permission=USERS_MANAGE,
                hidden=True),
        NavNode("admin.roles", "Roles", "/admin/roles", parent="admin", permission=ROLES_MANAGE,
                keywords="permissions"),
        NavNode("admin.sessions", "Sessions", "/admin/sessions", parent="admin",
                permission=SESSIONS_MANAGE),
        NavNode("admin.audit", "Audit log", "/admin/audit", parent="admin", permission=AUDIT_VIEW,
                keywords="history events"),
        NavNode("admin.system", "System", "/admin/system", parent="admin", permission=SYSTEM_VIEW,
                keywords="configuration settings health"),
        NavNode("admin.uikit", "UI kit", "/admin/ui-kit", parent="admin", permission=SYSTEM_VIEW,
                keywords="components styles gallery"),
    ],
)
