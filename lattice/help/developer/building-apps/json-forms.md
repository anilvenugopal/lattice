---
title: Forms from JSON Schema
summary: Show any JSON document as a form drawn from a JSON Schema or a Pydantic model, validate it on the server, and keep documents in the document store.
order: 32
keywords: form json schema pydantic formspec schemadef build_form parse_form document store documentkind array oneof discriminator raw json other fields infer validation
---

A form drawn from a JSON Schema takes a JSON document in and gives a JSON
document back. You declare the shape once, as a Pydantic model or a JSON
Schema. Lattice draws the fields, reads the post back into JSON and validates
it on the server.

Use it for settings, templates, job inputs and any record whose shape is data.
For an ordinary record form with a handful of fields, the plain form pattern in
[Forms and feedback](forms-and-feedback.md) is still simpler.

```python
from pydantic import BaseModel, Field
from lattice.api import FormSpec, build_form, parse_form

class Settings(BaseModel):
    name: str = Field(min_length=2)
    retries: int = Field(3, ge=0, le=10)
    notify: list[str] = []

SETTINGS = FormSpec("demo.settings", schema=Settings,
                    ui={"notify": {"help": "Email addresses told about failures."}})

APP = AppManifest(key="demo", …, forms=[SETTINGS])
```

## Show and save it

```python
@router.get("/settings")
def show(request: Request, db: Db = Depends(get_db)):
    form = build_form(request, SETTINGS, load_settings(db))
    return render_page(request, "demo/settings.html", "settings", form=form)

@router.post("/settings")
async def save(request: Request, db: Db = Depends(get_db)):
    result = parse_form(request, SETTINGS, await request.form())
    if not result.ok:
        return render_page(request, "demo/settings.html", "settings",
                           form=result.form, status_code=400)
    store_settings(db, result.data)
    response = RedirectResponse("/demo/settings", status_code=303)
    flash(response, request, "Settings saved.")
    return response
```

```jinja
{% from "components/json_form.html" import json_form with context %}
{% call card() %}{{ json_form(form, action="/demo/settings", cancel="/demo") }}{% endcall %}
```

`parse_form` returns a `FormResult`:

| Field | Holds |
|---|---|
| `data` | The document the form describes |
| `ok` | `True` when nothing failed |
| `errors` | Messages by field, shown at each field when `form` is rendered |
| `general` | Messages that belong to no one field, such as malformed JSON |
| `form` | The context to render the form again, with the user's values and the errors |

The route still decides what happens: `parse_form` never saves.

## What draws what

| Schema | Drawn as |
|---|---|
| `object` | A group of fields; nested objects are framed groups |
| `array` | A list with **Add**, move up, move down and remove on each item |
| `string` | A text box; `format` `date`, `date-time`, `time`, `email` or `uri` picks the input; `"x-widget": "textarea"` a text area |
| `number`, `integer` | A number box with `minimum` and `maximum` |
| `boolean` | A checkbox |
| `enum` | A dropdown |
| `const` | Read-only text; the value is always the constant |
| `$ref`, `$defs`, single-item `allOf` | Resolved, so Pydantic's nested models just work |
| `["string", "null"]`, or `anyOf` with `null` | The field, where empty means `null` (Pydantic's `str \| None`) |
| `oneOf`/`anyOf` of objects | A dropdown of the options, then the chosen option's fields; a `discriminator` picks the option from the document |
| Anything else | A JSON text box for that value |

Required fields show `*`. An empty optional field is left out of the
document, or set to `null` where the schema allows null. A field the
document lacks shows the schema's `default`.

## Fields the schema doesn't describe

A document may hold keys its schema doesn't mention. They are listed under
**Other fields** and returned **unchanged**, so a narrower schema never drops
data.

## Layout hints

`ui` is a separate dict, keyed by the field's path (`""` for the document,
`"address/city"`; array items share their array's path). It keeps the schema
plain JSON Schema:

| Hint | Use |
|---|---|
| `label`, `help`, `placeholder` | Override the schema's `title` and `description` |
| `widget` | `textarea`, `date`, `email`… for a string |
| `order` | On an object: its fields' order |
| `sections` | On an object: `[("Contact", ["email", "phone"]), …]`, each a titled group |
| `labels` | On an enum: `{"gbp": "Pounds sterling"}` |
| `item_label` | On an array: "Add **contact**" instead of "Add item" |
| `readonly` | Shown, not edited |

## Changing the shape

Adding or removing an array item, moving it, choosing another `oneOf` option,
adding a field and switching tabs all post the form to
`POST /_form/{key}/render`, which redraws it with nothing lost. Typing never
leaves the page. Register every `FormSpec` in the manifest's `forms=`, so the
endpoint knows it; `permission=` limits who may use it.

## The JSON tab

The **JSON** tab shows the whole document as JSON, including other fields.
Saving from it saves that JSON, validated the same way. Turn it off with
`json_tab=False`.

## Which schema

The first that applies:

1. **A schema the user chose**, when the form has `switchable=True`: a
   **Schema** dropdown lists the registered schemas.
2. **The FormSpec's** `schema`: a dict, a Pydantic model, or the id of a
   registered `SchemaDef`.
3. **The document's `$schema`**, when it names a registered `SchemaDef`.
4. **Inferred from the document**: every key becomes a field of its JSON type,
   and **Add field** adds a new key with a type. Nothing is validated.

Register named schemas in the manifest:
`schemas=[SchemaDef("demo.address", "Address", Address)]`.

## Validation

The server is authoritative. `parse_form` validates with `jsonschema`
(Draft 2020-12, with format checks) and turns each failure into a short
message at its field: "Required.", "At least 2 characters.", "At most 150.",
"Enter a whole number.".

## The document store

For configuration, templates and low-volume records of mixed shape, Lattice
keeps JSON documents in `lattice.document`. An app declares each kind:

```python
from lattice.api import DocumentKind, documents

POLICY = DocumentKind("demo.policy_template", "Policy template", schema=PolicyTemplate,
                      title="{name}", edit="demo.policies.edit")

APP = AppManifest(key="demo", …, documents=[POLICY])
```

| Call | Does |
|---|---|
| `documents.create(db, user, POLICY, data)` | Validates, saves, records `demo.policy_template.created`; returns the id |
| `documents.update(db, user, POLICY, id, data)` | Validates, replaces, records `….updated` |
| `documents.get(db, POLICY, id)` | `id`, `title`, `data`, `schema_version`, timestamps; 404 when missing |
| `documents.all_of(db, POLICY)` | Every document of the kind, newest first |
| `documents.delete(db, user, POLICY, ids)` | Deletes, records `….deleted` |

Invalid data raises `InvalidDocument`, with `errors` by field as `parse_form`
gives them.

- **Its form** is `POLICY.form`: `build_form(request, POLICY.form, data)`.
- **Its title** is `title` formatted with the document, kept in its own column
  for lists.
- **A list of one kind** is a grid on `documents.QUERY` with
  `params={"kind": POLICY.key}`. Give the grid the kind's key, so its actions
  and a [record page](record-pages.md)'s history share the audit trail:

```python
POLICIES = GridSpec(key="demo.policy_template", title="Policy templates",
                    path="/demo/policies", query=documents.QUERY,
                    params={"kind": POLICY.key},
                    columns=[Column("title", "Name", kind="strong"),
                             Column("updated_at", "Updated", kind="ago"),
                             Column("updated_by", "By", kind="user")])
```

> [!IMPORTANT]
> Business entities that people filter, join or report on belong in the app's
> own tables. The document store is for shapes that vary or change often.
