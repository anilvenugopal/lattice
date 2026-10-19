# 0007. Forms rendered from JSON Schema, JSON in and JSON out

Status: Accepted (18 October 2026, built in step 5)

## Context

Apps need a standard way to show any JSON document as an editable form and save
it back. A document may lack fields the user needs to fill, and may contain
fields no schema describes. The longer-term aim is a form builder usable anywhere
in the app.

## Decision

- **One schema language, JSON Schema 2020-12:**
  - Pydantic models provide schemas through `model_json_schema()`;
  - a template JSON is an example, from which a schema is inferred.
- **Schema resolution, first match wins:**
  1. an explicit `schema=`;
  2. the document's `$schema`;
  3. a registry match on a type or kind field;
  4. a schema inferred from the document.

  The user can apply another schema, and the form re-renders.
- **Round trip:** fields the schema does not describe are shown under "Other
  fields" and returned unchanged. Without a schema, "Add field" adds a property.
- **Layout hints** (order, sections, widget, label, help) live in a separate `ui`
  object, so the schema stays plain JSON Schema.
- **Rendered on the server** by recursive macros. Supported: object, array,
  string with formats, number, integer, boolean, enum, `$ref`/`$defs`, and
  `oneOf` with a discriminator. A raw JSON tab covers the rest.
- **Validation:** the server (`jsonschema` library) is authoritative.
- **CRUD:** `FormSpec(schema, ui, load, save)` is independent of storage.
- **A document store** in the kernel (kind, schema id and version, JSONB data,
  audit) holds configuration, templates and low-volume mixed-shape records.
- **The form builder comes later.** It is the renderer applied to a schema that
  describes the supported subset.

## Consequences

- Any Pydantic model becomes a form with no template, for example:
  - taskline's "Run job" form from a job's declared inputs;
  - app settings;
  - incident forms.
- The supported subset is documented. Anything outside it goes to the raw JSON tab.
- Business entities that are filtered, joined or reported on stay in relational
  tables, not in the document store.

## Rejected

- **RJSF and JSON Forms.** They are React or Angular libraries, which would break
  the server-rendered model.
- **json-editor.** Vanilla JS, but its markup would not follow the design system.
- **Template JSON as a second schema language.** Two mechanisms where one is enough.
