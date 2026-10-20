---
title: Attachments and folders
summary: Files on any record with no code in your app; the attachments service; and the folder picker for mounted shares.
order: 67
keywords: attachments files upload download store folder picker share mounted path x-widget folder
---

## Attachments: nothing to build

Every record page whose `RecordPage` sets `reference_kind` shows an
**Attachments** panel, as it shows Comments
([ADR 0017](/help/lattice/developer/architecture/decisions)). People attach,
preview, download and remove files; Lattice keeps them by the record's URN and
checks, on every request, that the person may open the record through your
reference kind's resolver.

- **Permissions**: `lattice.attachments.add` (editors by default; delete your
  own) and `lattice.attachments.manage` (delete anyone's; Administration ›
  Attachments).
- **Events**: `attachments.added` and `attachments.removed`, with the record as
  subject, so followers are notified (kind `attachments.on_followed`) and
  webhooks receive them. Subscribe if your app must react.
- **Limits**: `LATTICE_ATTACHMENT_MAX_MB` (25) and `LATTICE_ATTACHMENT_TYPES`
  (extensions). Files are stored under random names in `LATTICE_FILES_DIR`;
  only images and PDFs are ever shown in the browser.

When your app deletes a record, remove its files too:

```python
from lattice.api import attachments, urn

attachments.remove_all(db, urn("showcase.claim", claim_id))   # after the commit
attachments.on_subject(db, urn("showcase.claim", claim_id))   # the list, newest first
```

## The folder picker

For a record that points at a folder that already exists, such as a claim's
folder on a network share, use the folder picker. Its value is
`{store}:{path}`: the share, and the folder's path inside it.

```python
# JSON Schema forms
file_folder: str = Field("", json_schema_extra={"x-widget": "folder"})
```

```jinja
{# plain forms #}
{% from "components/macros.html" import folder_picker %}
{{ folder_picker("folder", claim.file_folder, folder_label(claim.file_folder)) }}
```

**Browse…** lists one folder at a time and can create one; the browser fires a
`change` event when a folder is chosen or cleared, so `hx-trigger="change"`
saves it. Check the value on the server before you keep it:

```python
from lattice.api import BadPath, check_folder, folder_label

value = check_folder(form["folder"])    # an existing folder, normalised; else BadPath
folder_label(value)                     # "Claims share / CAT-2610 / Lake Charles"
```

The showcase's claim page does this in its **Claim file** panel
(`apps/showcase/lattice_showcase/claims.py`, `set_folder`).

**The shares** are the host's: `LATTICE_FOLDER_STORES` (JSON, label to path) and
`create_app(folder_stores={"Claims share": "/mnt/claims"})`. A path outside a
share is refused, hidden folders are not listed, and browsing needs
`lattice.folders.browse` (editors by default). Only mounted folders are built;
S3 and SharePoint stores will offer the same browsing.
