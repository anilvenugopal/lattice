# 0009. Permissions declared by apps, grouped into roles

Status: Proposed

## Context

Lattice checks three fixed roles (`admin`, `editor`, `viewer`) by name. With
several apps, each needs its own rights. For example, taskline needs
"view runs" and "cancel or retry", and the Ops console needs "operate prod"
separately from "operate dev". Role names cannot express that.

## Decision

- Apps declare permissions in their manifest: `taskline.view`, `taskline.operate`.
- A role is a named set of permissions, edited on Administration › Roles. The
  built-in roles become sets of the kernel's and demo app's permissions.
- Routes, nav nodes, grid actions, search providers and record panels check
  permissions with `require("taskline.operate")`, never role names.
- A permission can be scoped to a binding: `taskline.operate@prod`.

## Consequences

- Adding an app adds permissions, without new roles or code changes in other apps.
- A migration converts the current role checks, and `app/auth/roles.py` is replaced
  by the permission catalogue.
- Administration › Roles becomes an editor instead of a read-only list.

## Rejected

- **More fixed roles per app.** The number of roles grows with every app and
  instance.
- **Row-level permissions.** Rows stay scoped in each grid source, as today.
