---
title: Administration
summary: Manage users and their roles, sign people out, read the audit log, and check the system. For administrators.
order: 50
keywords: admin administration users roles grant revoke deactivate reset password sessions audit log system ui kit
permission: lattice.users.manage
---

**Administration** (the shield icon in the rail) is visible only to
administrators.

## Users

**Users** lists everyone who can sign in. Views show **All**, **Active** and
**Inactive** users.

| To | Do |
|---|---|
| Add a user | **New user**: enter their email, name and roles. Leave the password empty for someone who signs in with single sign-on; otherwise they must change the password you set at first sign-in |
| Give or take away a role | Select users, then **Grant role** or **Remove role**, and choose the role |
| Stop someone signing in | Select them and choose **Deactivate**. They are signed out at once. **Activate** lets them back in |
| Reset a password | Select one user and choose **Reset password**. A temporary password is shown once; give it to the user privately. They must change it at next sign-in |
| Sign someone out | Select them and choose **Sign out everywhere** |
| Change a name, roles or status | Open the user. Their page also shows their sessions and activity |

To protect against lock-out, you cannot remove your own admin role or
deactivate yourself.

People who sign in with single sign-on for the first time get an account
automatically. Depending on how your site is set up, they either get a default
role or wait on **Access pending** until you grant one.

## Roles

**Roles** lists the roles and what each allows. The built-in roles are:

| Role | Can |
|---|---|
| Administrator | Everything, plus Administration |
| Editor | Create and change records; run bulk actions |
| Viewer | Read every page outside Administration |

A user can hold several roles. New roles are added by the developers of your
site.

## Sessions

**Sessions** lists every active sign-in, for all users: who, how they signed
in, from where, and when it was last used. Select sessions and choose
**Revoke** to end them. Your own current session is kept.

## Audit log

**Audit log** records every change made by anyone, in every app: who did it,
what they did, to which record, and when. Filter it by event or by target to
answer "who changed this?".

Each record's own page also shows its history, under **Activity**.

## System

**System** shows how this site is set up:

- **Application**: its name and environment.
- **Sign-in**: the sign-in methods and session limits.
- **Counts**: users, active sessions and audit events.
- **Registered grids** and the **navigation**: every list and page of every app.

Use it to check a configuration change took effect.

## UI kit

**UI kit** shows every shared screen component, for developers and designers.
