---
title: Notifications
summary: Tell people about what needs them: notify() from your app, kinds tied to your events, following records, and how notifications clear.
order: 66
keywords: notifications notify follow followers bell inbox kind NotificationKind event clears unread collapse email webhook
---

**Events say what happened; notifications decide who is told.** Every user has
an inbox in Lattice: the bell in the top bar, **Account › Notifications**, and a
home tile ([ADR 0016](/help/lattice/developer/architecture/decisions)). Your app
puts things in it three ways.

| Way | Use when | Who is told |
|---|---|---|
| `notifications.notify(db, user_ids, kind, title, …)` | Your app knows who: the new owner, the on-call role | The people you name |
| Following a record | People want to hear about one record | Its followers |
| A kind tied to an event | Every follower should hear when your event happens | Followers of the event's subject |

## Declare kinds

Every notification has a kind your app declares, like a permission. Its key
starts with your app's key:

```python
from lattice.api import AppManifest, NotificationKind

APP = AppManifest(
    key="comments", …, publishes=["comments.added"],
    notifications=[NotificationKind(
        "comments.on_followed", "New comment on a record you follow",
        event="comments.added", title="{author} commented", body="{excerpt}")],
)
```

| Field | Means |
|---|---|
| `key`, `label`, `description` | The kind, as people will see it when they choose how to be told |
| `event` | When your app publishes this event, the people following its subject are told |
| `title`, `body` | Formatted with the event's `data`; a missing key is empty |
| `clears` | Events that resolve open notifications of this kind about the same record, such as `["incidents.resolved"]` |
| `email` | How people are told unless they choose otherwise: `"app"` (the default), `"email"` right away, or `"digest"`, a daily summary |

The person who caused the event (`data["actor_id"]` or `data["author_id"]`) is
not told about their own action. `create_app` refuses a kind outside your
namespace, or one naming an event your app does not publish.

## Notify directly

```python
from lattice.api import notifications, urn

notifications.notify(db, [owner_id], "incidents.assigned", "INC-42 is yours",
                     body="Database connections failing on prod-eu",
                     subject=urn("incidents.incident", 42), actor_id=user.id)
```

It writes in your transaction, so a failed request tells nobody. An unread
notification of the same kind about the same record is updated, with its count
raised, instead of repeated.

**Notifications refer, they do not copy.** Keep `title` and `body` short and
free of anything the reader may not see; the record itself is drawn from
`subject` when the notification is read, through `ref()`, with the reader's
access at that moment.

## Following

Every record page whose `RecordPage` sets `reference_kind` shows **Follow**;
people choose for themselves. Your app can follow records for people too:

```python
notifications.follow(db, user.id, urn("showcase.claim", claim_id))   # or a list of ids
notifications.unfollow(db, user.id, urn("showcase.claim", claim_id))
notifications.following(db, user.id, urn("showcase.claim", claim_id))
```

The showcase's **Take** action follows the claims it gives you, so comments on
them reach you through the Comments app's kind above.

## How they clear

- Opening one marks it read and goes to its record.
- **Mark read**, **Mark all read** and **Dismiss** in the list.
- A `clears` event, or `notifications.resolve(db, subject, ["incidents.assigned"])`.
- After `LATTICE_NOTIFICATION_DAYS` (90) days they are deleted.

## Email

Every notification appears under the bell. Each person also chooses, per kind,
in **Account › Notification settings**: in the app only, an email right away,
or a daily summary. Your kind's `email=` is the choice for people who have not
made one; keep it `"app"` unless the kind is urgent for everyone.

- **Queued, then sent in the background** every 30 seconds, with up to five
  tries, waiting longer each time. A mail server that is down never fails the
  request that notified.
- **Title and link only.** An email carries the notification's title and a link
  to it (`LATTICE_PUBLIC_URL`), never its body or the record's content.
- **One at a time.** While an email for a notification waits to go, more
  notifications folded into it do not queue another.
- **The daily summary** goes out once a day after
  `LATTICE_NOTIFICATION_DIGEST_HOUR` (UTC), listing what the person has not read
  or had emailed.
- **The mail server** is `LATTICE_SMTP_HOST`, `_PORT`, `_USERNAME`,
  `_PASSWORD` and `_STARTTLS`, with `LATTICE_MAIL_FROM`. Without a host nothing
  is sent: emails are kept as **logged**, readable in **Administration › Email**
  (permission `lattice.email.view`), which also sends a test email.

## Webhooks

Administrators register webhooks in **Administration › Webhooks** (permission
`lattice.webhooks.manage`): an address, the event types it takes (or every
event), and a format. Every event your app publishes reaches them; there is
nothing for an app to add, beyond publishing events.

| Format | Body posted |
|---|---|
| `cloudevents` | The CloudEvent's JSON (`event.to_dict()`), `Content-Type: application/cloudevents+json` |
| `chat` | `{"text": "[Site] Ann commented: Roof photos attached."}`, from the title and body of the notification kind tied to the event, else the event type |

Every post carries `X-Lattice-Timestamp` and `X-Lattice-Signature:
sha256=<hex>`, the HMAC-SHA256 of `"{timestamp}.{body}"` with the webhook's
secret. A receiver checks it like this:

```python
expected = "sha256=" + hmac.new(secret, f"{ts}.{body}".encode(), "sha256").hexdigest()
ok = hmac.compare_digest(expected, request.headers["X-Lattice-Signature"])
```

Posts are queued when the event is delivered and sent by the background loop
every 30 seconds, with up to five tries; a 2xx answer delivers them. Keep event
`data` small and free of what other systems should not see: it is posted as
is.
