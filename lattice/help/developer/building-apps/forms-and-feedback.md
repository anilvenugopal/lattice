---
title: Forms and feedback
summary: Full-page forms, in-place HTMX forms, validation, CSRF, and telling the user what happened with toasts.
order: 30
keywords: form post validation errors csrf htmx hx-post toast flash redirect 303 400 feedback message
---

Lattice has two kinds of form and one way to report what happened: a toast.

## Full-page forms

Use a full-page form for creating or editing a record. The pattern is
post, then redirect:

```python
EDIT = "helpdesk.tickets.edit"          # declared in the app's permissions


@router.get("/tickets/new", dependencies=[Depends(require(EDIT))])
def new_form(request: Request):
    return render_page(request, "helpdesk/ticket_form.html", "tickets.new",
                       errors={}, values={})


@router.post("/tickets/new", dependencies=[Depends(require(EDIT))])
async def create(request: Request, db: Db = Depends(get_db), user=Depends(current_user)):
    form = await request.form()
    values = {"subject": (form.get("subject") or "").strip()}
    errors = {"subject": "Enter a subject."} if not values["subject"] else {}
    if errors:
        return render_page(request, "helpdesk/ticket_form.html", "tickets.new",
                           status_code=400, errors=errors, values=values)
    ticket_id = db.value(SQL.create, **values)   # INSERT … RETURNING id
    audit.record(db, user.id, "helpdesk.tickets.create", f"Opened {values['subject']}",
                 target_type="helpdesk.tickets", target_id=ticket_id)
    response = RedirectResponse(f"/helpdesk/tickets/{ticket_id}", status_code=303)
    flash(response, request, "Ticket opened.")
    return response
```

The rules:

- **Saving** happens when the route returns: the request is one transaction,
  so the insert and its audit event are saved together, or not at all.
- **On failure**, render the form again with status 400. Pass an `errors`
  dict with one message per field, and the submitted `values`, so nothing the
  user typed is lost.
- **On success**, redirect with 303. The browser's back and refresh buttons
  then behave, and a refresh does not post the form again.
- **To confirm success**, call `flash(response, request, message)` on the
  redirect. The message appears as a toast on the next page.
- **Validate on the server.** HTML attributes such as `required` help the
  user, but the server's check is the one that counts.

The template uses the field macros, which show the label, hint and error:

```jinja
<form method="post" action="/helpdesk/tickets/new" class="stack-lg">
  {{ csrf_field() }}
  {% call card() %}
    <div class="stack">
      {{ field("subject", "Subject", values.subject, error=errors.subject, required=True) }}
      {{ select_field("priority", "Priority", priorities, values.priority) }}
      {{ field("details", "Details", values.details, type="textarea",
               hint="What happened, and what you expected.") }}
    </div>
  {% endcall %}
  <div class="form-actions">
    <a class="btn btn--ghost" href="/helpdesk/tickets">Cancel</a>
    <button class="btn btn--primary" type="submit">Open ticket</button>
  </div>
</form>
```

For a create and an edit form that share one template, see
`work_item_form.html` in the demo. It reads each value from `values` after a
failed post, else from the record.

## In-place forms with HTMX

For a small change that does not leave the page, such as saving a profile
name or revoking a session, post with HTMX and answer with headers:

```jinja
<form hx-post="/account/profile" class="stack">
  {{ field("display_name", "Display name", profile.display_name, required=True) }}
  <div class="form-actions"><button class="btn btn--primary" type="submit">Save</button></div>
</form>
```

```python
@router.post("/profile")
def save_profile(display_name: str = Form(...), db: Db = Depends(get_db),
                 user=Depends(current_user)):
    if not display_name.strip():
        return Response(status_code=400, headers=toast("Display name is required.", "danger"))
    db.run(SQL.users.rename, id=user.id, display_name=display_name.strip())
    return Response(headers={**toast("Profile saved."), "HX-Refresh": "true"})
```

HTMX requests carry the CSRF token in the `X-CSRF-Token` header automatically,
so in-place forms need no `csrf_field()`.

## CSRF

Lattice uses a double-submit cookie: the `lattice_csrf` cookie must match the
`csrf_token` form field or the `X-CSRF-Token` header.

- Every router that changes data declares
  `APIRouter(dependencies=[Depends(csrf_protect)])`. GET requests pass; a post
  without a matching token gets 403.
- Full-page forms include `{{ csrf_field() }}`.
- HTMX, the grid and `app.post()` in JavaScript send the header for you.

## Feedback

After an action, tell the user what happened with a toast. Choose by the kind
of route:

| Route | How |
|---|---|
| A grid action handler | Return the message: `return f"Closed {ctx.count} ticket(s)."`, or `ActionResult(message, tone=…)` |
| An HTMX route | `headers=toast("Saved.")`, or `toast("Failed.", "danger")` |
| A full-page form that redirects | `flash(response, request, "Saved.")` before returning the redirect |
| JavaScript | `app.toast("Copied.", "success")` |

Tones are `success` (the default), `info`, `warning` and `danger`.

Do not use `alert()`, `?saved=1` banners or messages written into the page.

Write messages as what happened, with the count when there is one:
"Assigned 3 items.", "Password changed." When an action skips rows that
fail its `when`, the grid adds "2 skipped (not eligible)." for you.

## Buttons

- **One primary button** per region: the main action.
- **Destructive actions** use the `danger` tone and ask for confirmation.
- **Labels are verbs**: "Approve", "Run job", "Save changes". Never "OK" or "Submit".
