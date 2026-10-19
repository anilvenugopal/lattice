# 0011. Integration standards: URN references, CloudEvents, published views and OpenAPI

Status: Accepted (18 October 2026). The outbox delivery row is superseded by
[0012](0012-taskline-ui-and-contract.md): other processes' state is read from their views, not streamed.

## Context

Lattice's apps must work together, and so must the systems around them:

- apps in the same host (a business app and a Comments panel on its records);
- libraries that run in other processes (Taskline's workers and reaper);
- other Lattice hosts (an Ops console reading several Taskline databases);
- systems outside Lattice (an alerting tool reporting incidents).

The first design ([ADR 0003](0003-app-manifest-and-contracts.md)) named the
contracts: references, record panels, events and registries. It left their
formats open. Inventing formats would make every outside system learn
Lattice's own conventions. Where an established standard fits, Lattice uses
it.

## Decision

### 1. References are URNs

A reference to a record anywhere is a URN ([RFC 8141](https://www.rfc-editor.org/rfc/rfc8141)):

```
urn:lattice:{kind}:{id}          urn:lattice:demo.work_item:42
```

- **The kind** starts with the key of the app that owns the record, then a
  dot: `strategiq.document`, `taskline.run`. Two apps can never define the
  same kind.
- **The id** is the owning app's own identifier, as text.
- **Storage:** a reference is stored and passed as text in that form. Inside a
  host, the owning app registers a resolver that turns it into a title, a link
  and a preview, for users allowed to see the record. Outside a host, the URN
  is simply an identifier.

### 2. Events are CloudEvents

An event says that something happened. It uses the attributes of
[CloudEvents 1.0](https://cloudevents.io) (CNCF):

| Attribute | Lattice value |
|---|---|
| `specversion` | `1.0` |
| `id` | Unique per source: a UUID, or the publisher's monotonic event id |
| `source` | Who published it: `/lattice/{host}/{app}`, or `/taskline/{instance}` |
| `type` | `{app}.{event}`: `comments.added`, `taskline.run.failed` |
| `subject` | The URN of the record it is about, when there is one |
| `time` | RFC 3339, UTC |
| `datacontenttype` | `application/json` |
| `data` | Small: references and a few fields, never whole records |

How events travel depends on where the publisher runs:

| Publisher | Delivery |
|---|---|
| **An app in the same host** | The in-process bus. Published inside the request's transaction, delivered to subscribers after it commits. Each subscriber runs in its own transaction; a failure is logged and does not undo the publisher's work |
| **Another process writing to a database the host can read** (Taskline's workers) | An outbox: the publisher writes events to a table or view, with a monotonic `id`. The host reads new events since its last cursor and puts them on its bus |
| **A remote system** | HTTP, in the CloudEvents HTTP binding (structured JSON), to an endpoint protected by an API token |

There is no delivery guarantee on the in-process bus after a crash between the
commit and a subscriber. An outbox gives the guarantee when an event needs it.

### 3. Reading another system's data: published views

When another system's tables are in a database the host can read (Taskline in
the same Postgres, or several Taskline databases for an Ops console), the
host reads them **only through views that system publishes as its read
contract**. For example, Taskline publishes `taskline_api.run`.

The views must be:

- **stable:** columns are added freely; removing or renaming one is a breaking
  change;
- **indexed** for the filters a UI needs;
- **readable** by a role that cannot write.

A Lattice list then searches, filters, sorts and pages them like any named
query. The other system remains free to change its own tables.

### 4. Calls between processes: HTTP, JSON and OpenAPI

When one process asks another to do something, and they share no Python
process, the call is HTTP with JSON bodies:

- **Described with OpenAPI 3.1,** which FastAPI generates.
- **Versioned paths:** `/api/v1/…`.
- **Authenticated** with API tokens, or the same single sign-on.
- **Problems** reported as RFC 9457 problem details.

Inside one host, apps don't call each other over HTTP. They use the contracts
above and the registries below. A library used in-process (Taskline's command
functions) is called as Python.

### 5. Where no standard fits: small Lattice registries

Some contracts exist only inside a host, and no standard covers them. Lattice
keeps these as small registries, declared in each app's manifest:

- **record panels:** sections one app adds to another app's record pages,
  matched on reference kind;
- **reference resolvers;**
- **event subscriptions;**
- **permissions, navigation, lists, Ctrl+J sources and home tiles,** as today.

The alternative for panels, micro-frontends (iframes or web components served
by each app), is much heavier, and solves a problem Lattice doesn't have,
because its apps share one server.

## Consequences

- **Outside systems use common formats:** an alerting system can post a
  CloudEvent, and a URN means the same thing in every Lattice host.
- **Splitting is easy.** If an app later moves to its own process, its events
  and calls already have a standard form: the bus becomes an outbox or HTTP,
  and calls become OpenAPI endpoints.
- **Taskline integrates without Lattice-specific code:** published views to
  read, Python command functions to act, and an outbox of CloudEvents for its
  run outcomes. See `docs/integrations/taskline-requirements.md`.
- **References become longer strings** in storage (`urn:lattice:` adds 12
  characters), a small cost for an identifier that works everywhere.

## Rejected

- **HTTP APIs between apps in the same host.** It would add network round
  trips, authentication between apps, new ways to fail and versioned APIs, all
  for what is a function call within one process.
- **A Lattice-specific event shape.** CloudEvents costs nothing extra
  in-process, and works unchanged for webhooks and brokers.
- **Bare `kind:id` references.** Not a recognised format, and two apps could
  clash on a kind such as `ticket`.
- **A message broker now.** The apps share one process, and an outbox covers
  the cross-process case ([ADR 0003](0003-app-manifest-and-contracts.md)).
- **GraphQL or gRPC between processes.** HTTP with OpenAPI is enough, and is
  generated by the framework Lattice already uses.
