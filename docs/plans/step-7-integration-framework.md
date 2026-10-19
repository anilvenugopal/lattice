# Steps 7 and 8 plan: the integration framework, and the showcase using it

Status: **done** on the `step-7` branch (18 October 2026), after step 6. You asked me to
proceed without stopping until Taskline is needed, so the choices below are
mine and can be reversed at review. It builds on the superseded step 4 draft
([step-4-references-panels-events.md](step-4-references-panels-events.md)),
with its recommended answers, and follows
[ADR 0011](../adr/0011-integration-standards.md).

## What it delivers

| Contract | What it gives | Standard |
|---|---|---|
| **References** | `urn:lattice:showcase.item:42` resolves, for this user, to a title, a link and a status; `{{ ref(urn) }}` draws it anywhere | URN |
| **Record panels** | An app adds a panel to other apps' record pages, matched on reference kind | Lattice registry |
| **Events** | `db.publish("comments.added", subject=urn, data={…})`, delivered to subscribers after the request commits | CloudEvents 1.0 |
| **Event feeds** | Lattice reads another system's outbox (a view of CloudEvent rows with a monotonic id) and puts each event on the bus. Taskline's run events arrive this way in step 9 | CloudEvents 1.0, outbox |

## How it looks

```python
def resolve_item(db, user, item_id) -> Resolved | None:
    row = ...  # read through the grid's query, so a hidden item resolves to None
    return Resolved(f"{row['ref']} · {row['name']}", f"/showcase/items/{item_id}",
                    badge=label, tone=tone)

APP = AppManifest(key="showcase", …,
    references=[ReferenceKind("showcase.item", "Item", resolve_item)],
    subscribes={"comments.added": notify_owner},
)

# Another app, never importing the showcase:
APP = AppManifest(key="comments", …,
    panels=[RecordPanel("comments", "Comments", "comments/panel.html", kinds="*",
                        load=load_comments)],
    publishes=["comments.added"],
)
```

- **A RecordPage names its kind** (`reference_kind="showcase.item"`), and shows
  every panel other apps contribute for that kind, after its own.
- **Events are published in the request's transaction** and delivered after it
  commits; if the request fails nothing is delivered. Each subscriber runs in
  its own transaction; a failing subscriber is logged and changes nothing else.
- **Feeds** are declared in a manifest (`feeds=[EventFeed("taskline.runs",
  query)]`), polled by the host, with their cursor in `lattice.event_feed`.

## Rules checked when the host starts

- Reference kinds, event types and panel keys start with the app's key.
- An app publishes only the types it declares; publishing another fails.
- Subscriptions name a declared type; panels name declared kinds or `*`.

## Step 8: the showcase uses it

A second app, **Comments** (`apps/comments`), proves the contracts between
apps that never import each other:

- **Comments** stores comments by URN, shows a **Comments** panel on every
  record page (permissions `comments.read`, viewer; `comments.write`, editor),
  draws each comment's subject with `ref()`, and publishes `comments.added`.
- **The showcase** declares the `showcase.item` and `showcase.spec` reference
  kinds, and subscribes to `comments.added`: a comment on an item puts a
  message in its owner's Reading pane.
- The showcase host runs both.

## Not in these steps

- **CloudEvents over HTTP** from remote systems: it needs API tokens, a planned
  feature.
- **Reference previews on hover**: links first.
- **Guaranteed in-process delivery**: an event that must not be lost goes
  through an outbox and a feed.

## How the result differs from the plan

| Area | Plan | Result, and why |
|---|---|---|
| Start-up checks | Subscriptions and panels name declared types and kinds | Only when they name an app the host runs. The showcase subscribes to `comments.added` and must still start without Comments |
| `ref()` in templates | — | It finds the request through a context variable the auth middleware sets, because grid cells render inside macros imported without the page's context |
| Grid cells | — | The cell macro is imported with context, so a template cell can use the page's helpers |
| Feeds in tests | — | The host doesn't poll feeds when `LATTICE_APP_ENV=test`; tests call `read_feed` themselves |
| Import rules | — | New import contract: apps never import each other |
| Comments | Read, write, delete your own | Also `comments.moderate` (no default role) to delete anyone's, and a Comments list in the rail |
| Event feeds | Built in this step | Removed on 19 October 2026 ([ADR 0012](../adr/0012-taskline-ui-and-contract.md)): a cursor over "after the last id" can miss rows that become visible late, and Taskline publishes no feed. Other processes' state is read from their views |
