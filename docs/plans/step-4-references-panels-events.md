# Step 4 plan: references, record panels and events

Status: **superseded, not built.** The order of work changed on 18 October
2026: step 4 became the integration standards (ADR 0011), and references,
panels and events moved to step 7, the integration framework. Keep this draft as
input for step 7. It predates ADR 0011, so its references are `kind:id`
where step 7 uses URNs, and its events are not yet CloudEvents.

## The problem

Apps must work together without importing each other, as ADR 0003 decided.
Some examples:

- **A panel on another app's page:** a strategiq document page shows the
  taskline jobs run for it, and the incidents that name it.
- **A reaction in another app:** a failed job opens an incident.
- **Linking to another app's record:** a comment links back to the record it
  is about.

Lattice has no way to do any of this yet. Step 4 adds the three contracts the
architecture describes (sections 4.2 to 4.4):

| Contract | What it gives | Example |
|---|---|---|
| **References** | A pointer to any record in any app, stored as text: `kind:id` | `demo.work_item:42`, shown anywhere as a link with the item's title |
| **Record panels** | A section one app adds to other apps' record pages | A **Comments** panel on every work item page, added by another app |
| **Events** | One app announces something happened; others react | `comments.added` makes the demo send a message to the item's owner |

## Proving it: a real second app, Comments

All three contracts need two apps to mean anything. The plan builds
**Comments**, a small service app from the architecture's list of planned
features ("Comments on any record, keyed by reference"):

- **What users see:** a **Comments** panel on the record pages of any app that
  shows panels. People read and add comments there. Authors can delete their
  own, and administrators can delete any.
- **What it stores:** each comment holds only a *reference* to its record
  (`demo.work_item:42`). It never imports the demo app or joins its tables.
- **What it announces:** `comments.added` after a comment is saved.
- **What the demo does with that:** it subscribes to `comments.added`, and when
  the comment is on a work item, puts a message in the item owner's Inbox:
  "Avery commented on WI-00042".

Neither app imports the other. Remove Comments from the host and the work item
page simply has no Comments panel.

## How it looks

**An app that owns records registers a reference kind:**

```python
def resolve_work_item(db, user, item_id) -> Resolved | None:
    row = db.first(SQL.work_items.by_id, id=item_id)
    return Resolved(title=f"{row['ref']} · {row['title']}", url=f"/demo/work/{item_id}") if row else None

APP = AppManifest(key="demo", …,
    reference_kinds=[ReferenceKind("demo.work_item", "Work item", resolve_work_item)])
```

The resolver returns `None` when the record doesn't exist **or the user may not
see it**. A reference never leaks a record its viewer couldn't open.

**Any template shows a reference as a link:** `{{ ref("demo.work_item:42") }}`
renders "WI-00042 · Renewal – Marine", linked to the item. It shows a plain
"Unavailable" when the record is gone or not visible to this user.

**An app adds a panel to other apps' record pages:**

```python
RecordPanel("comments", "Comments", kinds="*", render=comments_panel,
            permission="comments.read")
```

**A record page shows every panel for its record** with one line:
`{{ record_panels("demo.work_item:" ~ item.id) }}`. Panels from other apps
appear in the host's app order, each only to users with its permission.

**Events are published inside the request's transaction, and delivered after
it commits:**

```python
db.publish("comments.added", ref="demo.work_item:42", data={"comment_id": 7, "author_id": 3})

# in another app's manifest
subscribes={"comments.added": notify_owner}       # notify_owner(db, event)
```

If the request fails, nothing was saved, so nothing is delivered. Each
subscriber runs in its own transaction. A failing subscriber is logged and
doesn't undo the request.

## Rules, checked when the host starts

- Reference kinds start with the app's key (`demo.…`), and are declared once.
- Event names start with the publishing app's key (`comments.added`), and an
  app declares what it publishes (`publishes=[…]`).
- An app may only subscribe to events that some app publishes.
- Panels name kinds that exist, or `"*"` for every kind.
- Publishing an event the app didn't declare fails, so typos are caught.

## Stages

On a branch, `step-4`, one commit per stage, merged when you approve.

| # | Stage | Contents |
|---|---|---|
| 1 | **References and events** in the kernel | `ReferenceKind`, `Resolved`, the registry and `resolve(db, user, "kind:id")`; `db.publish(…)` queued on the request's transaction and delivered after commit; `AppManifest` `reference_kinds`, `publishes`, `subscribes`; the start-up checks; tests |
| 2 | **Record panels** | `RecordPanel`; `ref()` and `record_panels()` in templates; the demo registers `demo.work_item` and its work item page shows panels |
| 3 | **The Comments app** | `apps/comments`: its schema and named queries, the Comments panel (read, add, delete your own), permissions `comments.read` (default viewer and editor) and `comments.write` (default editor), `publishes=["comments.added"]`, help, tests; added to the demo host |
| 4 | **The demo reacts** | The demo subscribes to `comments.added` and messages the work item's owner; an end-to-end test: comment as one user, the owner sees it in their Inbox |
| 5 | **Docs** | A new **Working across apps** page (references, panels, events); the Comments user guide; Reference pages; AGENTS.md; ARCHITECTURE.md and the Decisions page |

## Not in step 4

- **A full record page component** (a Python spec for the whole detail page).
  Record pages stay the documented pattern, plus `record_panels()`; see
  decision 4.
- **Previews on hover** for references. Links only; previews can come later.
- **Guaranteed delivery** (an outbox table). Events after a crash are lost, as
  ADR 0003 accepts; an app adds an outbox only for an event that needs one.
- **Attachments.** Comments only.
- **Events between processes** (a message broker). Everything runs in one
  process, as ADR 0003 decided.

## Decisions for you

1. **The second app: build Comments for real** (recommended). It's on the
   architecture's feature list, it's small, and it proves all three contracts
   with something useful. The alternative is a throwaway test-only app, which
   proves the contracts but leaves nothing usable.
2. **Reference kinds start with the app's key**, such as `demo.work_item`
   (recommended), so two apps can never both define `ticket`. The alternative
   is bare names like the architecture's examples (`submission`).
3. **Events delivered right after the commit, in the same request**
   (recommended). It's simple, and tests are exact. The alternative is
   delivering them after the response is sent, which is faster for the user
   but harder to test and to reason about.
4. **Record pages: `record_panels()` plus the existing documented page pattern**
   (recommended, simplest). The alternative is a full record page component
   that draws the header, properties and panels from a Python spec.
5. **Who may comment by default:** viewers read comments; editors read and
   write (recommended). The alternative is everyone writing, viewers included.
