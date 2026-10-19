# Step 6 plan: the showcase replaces the demo

Status: **done** on the `step-6` branch (18 October 2026), after step 5. You
asked me to proceed without stopping until Taskline is needed, so the choices
below are mine and can be reversed at review. How the result differs is at the
end.

## The problem

The demo app pretends to be an insurance work queue. It shows the grid well,
but its story gets in the way: nobody needs to understand underwriting to see
what a component does. It also shows none of step 5's components.

## What replaces it

**One app, `showcase`, organised by capability, not by a business story.**
Each page names the feature it demonstrates, says in one line how it is built,
and links to the help page that explains it. The data is plain sample data:
"Items" with every kind of column, messages, jobs and documents.

| Section | Page | Shows |
|---|---|---|
| **Overview** | `/showcase` | A card per page: what it shows and the components behind it |
| **Grids** | Items | Every column kind; search, filters, views, saved views; bulk actions with input fields; `when` rules; confirm; star toggle; side panel; CSV export; Ctrl+J |
| | Reading pane | Split layout; rows scoped to the signed-in user; unread styling; a panel that changes its row |
| | Live updates | A polling grid; state-dependent actions; a toolbar action that collects input |
| **Charts** | Dashboard | Every chart kind on the Items grid, linked to its filters, with a threshold and a world map |
| **Records** | Item page | `RecordPage`: header actions, properties, panels (notes, a lifecycle stepper, child items, related items embedded and fixed), history |
| | New and edit item | The plain form pattern: validation, flash, redirect |
| **Forms** | Specs | Documents in the document store: a grid of one kind, and a JSON Schema form with nested objects, arrays, a discriminated union, other fields and the JSON tab |
| | Free-form | A form without a schema: inferred from the document, with **Add field** |
| **Flows** | Flows | A stepper, a tree of items and their children, and a graph of item dependencies whose node actions are the Items grid's actions |

## Data

Schema `showcase`, seeded by `lattice seed` with fixed pseudo-random data
(the same every time):

- `item`: 400 rows with a reference, name, category, status, priority, owner,
  amount, progress, score, tags, star, country, parent item, due date,
  timestamps and notes;
- `item_link`: dependencies between items, for the graph;
- `message`: a mailbox per user (as the demo's Inbox);
- `job`: background jobs moved along in development (as the demo's Jobs);
- documents of two kinds in `lattice.document`.

## Permissions

| Permission | Allows | Default |
|---|---|---|
| `showcase.items.edit` | Create, edit, assign and change items | editor |
| `showcase.items.delete` | Delete items | none (admin) |
| `showcase.specs.edit` | Create and change spec documents | editor |

## What moves

- `apps/demo` → `apps/showcase` (package `lattice_showcase`), `hosts/demo` →
  `hosts/showcase` (`showcase_host`). The default `LATTICE_HOST` becomes
  `showcase_host.main:app`.
- The demo's tests move with it and grow to cover the new pages.
- Docs that point at demo files point at the showcase's.
- **Your database:** after pulling, run `make reset`. It builds the `showcase`
  schema and seeds it. The old `demo` schema is not touched; drop it with
  `DROP SCHEMA demo CASCADE` if you want it gone.

## Stages

| # | Stage |
|---|---|
| 1 | Move and rename the app and host; new schema and seed; Items, Reading pane and Live updates pages |
| 2 | Item record page, plain forms, charts dashboard |
| 3 | Specs (document store and JSON Schema form), free-form form, flows |
| 4 | Overview page, the app's help, tests, and every doc that pointed at the demo |

## How the result differs from the plan

| Area | Plan | Result, and why |
|---|---|---|
| Graph data | Dependencies between many items | Items 1–20 only: at 60 nodes the graph was too dense to read at a glance |
| Live updates and Reading pane | — | Kept from the demo's Jobs and Inbox, renamed and pointed at the `showcase` schema; they already showed their features well |
| Form validation | — | Lattice change: a failure inside a `oneOf` now reports every error of the branch the document chose (its discriminator), not one guessed error |
| Document store | — | Lattice change: `documents.delete(…, record=False)` for grid handlers, so a grid's delete is audited once, not twice |
| Your database | `make reset` | Still the simplest. Without it, `lattice migrate` adds the `showcase` schema and the showcase's seed can run on its own; the old `demo` schema stays until you drop it |
