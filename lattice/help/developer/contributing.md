---
title: Contributing
summary: Change Lattice itself. Where things live, the rules, tests, docs, and how changes are committed.
order: 60
keywords: contribute contributing change lattice core development rules code quality tests docs commit agents
---

This page is for changing Lattice itself: the `lattice` package, the demo app
and these docs. To build an app on Lattice, see [Building apps](building-apps/index.md).

## Where things live

| Path | Owns |
|---|---|
| `lattice/api.py` | The only module apps import. Changing or removing a name is a breaking change |
| `lattice/kernel/` | Config, database, Lattice's tables, `auth/`, `nav/`, `services/` (audit, users, preferences), `web.py` (rendering, flash, toast), icons, slots, CSS rules. No UI components |
| `lattice/components/` | `grid/`, `search/` (Ctrl+J), `help/`, `tiles.py`, `manifest.py` |
| `lattice/platform/` | Lattice's own apps: `home.py`, `account.py`, `admin.py` |
| `lattice/host.py` | `create_app` and the checks on every app |
| `lattice/cli.py`, `lattice/testing.py`, `lattice/reference.py` | The command, the test fixtures, the Reference generator |
| `lattice/templates/`, `lattice/static/` | The shell, macros, grid templates; the five CSS layers; the scripts |
| `lattice/help/` | These docs: the user guide and the developer guide |
| `apps/demo/`, `hosts/demo/` | The demo app and the host that runs it |
| `alembic/` | Migrations |
| `docs/ARCHITECTURE.md`, `docs/adr/` | The target design and the decision records |
| `AGENTS.md` | Rules and recipes for coding agents; `CLAUDE.md` points to it |

The layers, and what each may import, are described in
[Architecture](architecture/index.md).

## Rules

The rules for apps in [Building apps](building-apps/index.md) apply to Lattice's
own code too. In addition:

- **Grids.** A grid feature goes in `lattice/components/grid/`, for every app.
  Never add a list of records outside the grid.
- **Macros.** A new UI piece becomes a macro in `components/macros.html`, and
  appears on the UI kit page.
- **CSS.** New CSS follows the five layers; `tests/test_css_architecture.py`
  checks it.
- **Public API.** Change `lattice.api` only on purpose: adding a name is
  cheap, removing or changing one breaks apps.
- **Decisions.** A decision that changes the architecture gets a record in
  `docs/adr/`, and is agreed before the code is written.

## Code quality

Implement the smallest change that satisfies the requirement.

- **No speculation.** Do not add behaviour for hypothetical scale or future
  needs.
- **No needless abstraction.** Do not add one for a single caller unless it
  makes that caller simpler.
- **Comments.** They explain constraints that names and structure cannot. Do
  not narrate the code.
- **Subtract before hand-off.** Review the diff for things to remove:
  - comments that restate the code;
  - helpers that only rename a call;
  - options nobody asked for.

## Tests

```bash
make test      # every test, core and apps
make lint      # ruff and the import contracts
```

Add or update a test for every route, action and permission you add. Core
tests are in `tests/`; the demo app's are in `apps/demo/tests/`. Both commands
must pass before a change is handed off. Report the count ("196 passed").

## Docs

The docs are help topics in `lattice/help/`. They are served in the app, so a
docs change is visible as soon as the host restarts.

- **Written pages.** Edit the Markdown. `create_app` checks the front matter,
  the links between topics and `help.toml`, so `make test` catches a broken
  link. See [Writing help](building-apps/writing-help.md).
- **Reference pages** are generated from the code: docstrings, field comments,
  settings descriptions, command help, macro comments and CSS tokens. After
  changing any of these, run:

  ```bash
  uv run lattice docs build
  ```

  and commit the changed pages. `tests/test_reference.py` fails while they are
  out of date.
- **Code and docs together.** A change to behaviour updates the docs that
  describe it in the same change.

### Writing style

The same voice everywhere: code comments, docs, commit messages.

- **Name the real thing**: the table, route, column, button.
- **Lead with the answer.**
- **No filler words** such as "robust", "leverage", "seamless" or
  "comprehensive".
- **Short sentences.** Lists for steps and sets, tables for comparisons.

## Database changes

1. Edit the models: `lattice/kernel/models.py` for Lattice's tables, the
   app's `models.py` for an app's.
2. Run `make revision m="what changes"`.
3. Read the generated file and fix anything autogenerate got wrong.
4. Run `make migrate`.

Never edit a migration that has been merged. Seed lookup rows in the migration
that creates their table.

## Commits

- **Subject.** 72 characters or fewer, saying what changes.
- **Body.** Says why.
- **No AI attribution.** No `Co-Authored-By` or "Generated with" lines naming
  an AI tool, in commits or pull request descriptions.

## Coding agents

`AGENTS.md` holds the rules and recipes in the form coding agents read. It
points here for depth. `.claude/skills/add-grid-page/` is a step-by-step skill
for the most common change.

When a rule changes, update both `AGENTS.md` and these pages.
