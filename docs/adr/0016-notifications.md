# 0016. Notifications: an inbox in Lattice's core, fed by apps and by following records

Status: Accepted (20 October 2026). Phases 1 (in-app) and 2 (email and each person's
choices) built; phase 3 (webhooks) follows. Changes the plan in ARCHITECTURE.md section 9,
which had Notifications as a separate service app.

## Context

People need to be told when something needs them: a comment on a claim they handle, an
incident assigned to them, a run that failed. Events (ADR 0011) say what happened, between
apps; nothing yet decides who is told, or how. The showcase had its own Notices table, and
Incidents (ARCHITECTURE.md section 8) will need the same.

## Decision

**Events say what happened; notifications decide who is told and how.**

**The inbox is part of Lattice**, like the audit log: a table of notifications per user in
schema `lattice`, the kernel service `notifications` in `lattice.api`, a bell with the unread
count in the top bar, the Account › Notifications page (a standard grid, rows scoped to the
user) and a home tile. Every app and the shell need it, and apps cannot import each other:
as a separate app it could only be reached by events, which cannot say "tell exactly this
person".

**Three ways in:**

| Way | Example | Recipients chosen by |
|---|---|---|
| `notifications.notify(db, user_ids, kind, title, …)` | Incidents tells the new owner | The app, which knows its domain |
| Following a record | A user follows a claim; comments on it reach them | The user (Follow on any record page with a reference kind) or the app (`notifications.follow`) |
| A kind tied to an event | `NotificationKind("comments.on_followed", event="comments.added", …)`: the event's subject's followers are told | The kind's declaration |

**Apps declare their kinds** (`AppManifest.notifications=[NotificationKind(…)]`): a key in
the app's namespace, a label, optionally the event that notifies followers (with title
and body templates over the event's data) and the events that clear it. Kinds are the list
users will set channel preferences against (phase 2).

**A notification refers, it does not copy**: a title, a short text and the record's URN,
drawn at read time through `ref()`, so the reader's permissions apply then.

**Cleared** by opening it (read), **Mark read**, **Dismiss**, an app's closing event
(`clears=["incidents.resolved"]` resolves open notifications of that kind about that
record), and age (`LATTICE_NOTIFICATION_DAYS`, 90). Unread notifications of one kind about
one record **collapse** into one with a count.

**Channels** come in phases behind one delivery step: in-app (phase 1); email, immediate
or a daily digest, with per-user, per-kind preferences (phase 2); signed CloudEvents
webhooks with retries for Slack, Teams and other systems (phase 3). Email carries the title
and a link, never record content.

**Incidents** opens, escalates and resolves incidents with events and `notify()`; severity
will choose channels; resolving clears. Notifications never poll Taskline: Incidents turns
failures into something a person must act on.

## Not chosen

- **A separate Notifications app**: it could not be called directly by other apps.
- **Copying record content into notifications**: it would outlive the reader's access.
- **Subscribing people to raw events**: events are for apps; kinds give people names and
  choices.

## Consequences

- The showcase's Notices table goes: a claim's handler follows the claim, and the Comments
  app's kind tells followers of new comments.
- Apps that want people told declare kinds and call `notify()` or publish events.

## Phase 2, as built (20 October 2026)

- **Choices**: each person picks, per kind, in the app only, email right away, or a daily
  summary (Account › Notification settings); a kind's `email=` is the default.
- **A queue**, `lattice.email`, sent by the notifications background loop every 30 seconds,
  five tries with growing waits; nothing is sent inside the notifying request.
- **Content**: the title and a link (`LATTICE_PUBLIC_URL`), never the body or the record.
- **No mail server** (`LATTICE_SMTP_HOST` empty): emails are kept as logged, readable with
  the new permission `lattice.email.view` in Administration › Email, which also sends a
  test email.
