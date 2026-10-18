---
title: Testing
summary: Test an app with Lattice's pytest fixtures, including pages, forms, grid actions and permissions.
order: 100
keywords: tests pytest fixtures as_user client db users csrf post_json host_apps
---

Every route, action and permission you add gets a test. `make test` runs
Lattice's tests and every app's tests, and must pass before a change is handed
off.

## Setting up

The root `conftest.py` loads the fixtures with
`pytest_plugins = ["lattice.testing"]`. An app's `tests/conftest.py` says
which apps the test host runs:

```python
import pytest

import lattice_helpdesk


@pytest.fixture
def host_apps():
    return [lattice_helpdesk.APP]
```

Add the app's `tests` folder to `testpaths` in the root `pyproject.toml`.

## Fixtures

| Fixture | Gives |
|---|---|
| `db` | A session on a fresh SQLite database for each test, built by running the migrations |
| `users` | `{"admin": …, "editor": …, "viewer": …}`: three users with those roles |
| `client` | A `TestClient` for a host built with `host_apps` |
| `as_user` | `as_user("editor")` signs the client in as that user and returns it |
| `host_apps` | The apps the host runs. Lattice's own tests use none |

Helpers in `lattice.testing`:

| Helper | Does |
|---|---|
| `csrf(client)` | The client's CSRF token, for form posts |
| `post_json(client, url, body)` | A JSON post with the CSRF header, for grid actions |
| `login(client, email)` | Signs in with the test password |
| `make_user(db, email, roles)` | Another user |
| `current(user)` | A `CurrentUser` for calling grid code directly, without a request |

## What to test

For each feature, test what a user can do and what they must not be able to
do.

**Pages render for the roles that can see them:**

```python
@pytest.mark.parametrize("role", ["viewer", "editor", "admin"])
def test_ticket_list(as_user, role):
    assert as_user(role).get("/helpdesk/tickets").status_code == 200


def test_only_editors_open_the_form(as_user):
    assert as_user("viewer").get("/helpdesk/tickets/new").status_code == 403
    assert as_user("editor").get("/helpdesk/tickets/new").status_code == 200
```

**Forms validate, then redirect:**

```python
def test_open_ticket(as_user, db):
    c = as_user("editor")
    resp = c.post("/helpdesk/tickets/new", data={"subject": "", "csrf_token": csrf(c)})
    assert resp.status_code == 400 and "Enter a subject" in resp.text
    resp = c.post("/helpdesk/tickets/new", data={"subject": "Printer", "csrf_token": csrf(c)},
                  follow_redirects=False)
    assert resp.status_code == 303
```

**Actions change the right rows and skip the rest:**

```python
def test_close_skips_closed_tickets(as_user, db, tickets):
    open_, closed = tickets
    body = post_json(as_user("editor"), "/_grid/helpdesk.tickets/action/close",
                     {"ids": [open_.id, closed.id]}).json()
    assert "1 skipped" in body["message"]
    db.refresh(open_)
    assert open_.status == "closed"
```

**Roles are enforced on the server:**

```python
def test_viewers_cannot_close(as_user, tickets):
    resp = post_json(as_user("viewer"), "/_grid/helpdesk.tickets/action/close",
                     {"ids": [tickets[0].id]})
    assert resp.status_code == 403
```

**Row scoping holds** for the list, the panel and your own routes:

```python
def test_users_see_only_their_messages(as_user, messages):
    mine, theirs = messages
    c = as_user("viewer")
    assert c.get(f"/_grid/mail.messages/panel/{theirs.id}").status_code == 404
```

Build test data in fixtures in `conftest.py`, through the `db` session, and
commit.

## Lattice's own checks

These run with `make test` and `make lint` and cover every app:

| Test | Checks |
|---|---|
| `tests/test_import_contracts.py`, `make lint` | Layers, and that apps import only `lattice.api` |
| `tests/test_css_architecture.py` | The five CSS layers |
| `tests/test_app_loader.py`, `tests/test_theming.py` | The manifest and namespace rules, host themes, slots and icons |
| `tests/test_help.py` | Help loading, links, the page map |
| `tests/test_reference.py` | The Reference pages match the code |

Building the host in your app's tests also runs every `create_app` check on
your app, including its help folder and stylesheets.
