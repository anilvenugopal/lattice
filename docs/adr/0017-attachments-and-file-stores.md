# 0017. Attachments on any record, file stores, and a folder picker for mounted shares

Status: Accepted (20 October 2026). Local storage, mounted shares and SharePoint libraries
(through m365graph) built; S3 later.

## Context

People need to keep files with records (photos and estimates with a claim, a contract
with a policy), whichever app owns the record. They also need to point a record at a
folder that already exists elsewhere, such as a claim's folder on a network share, or to
choose where an export goes.

## Decision

**A file store interface**, in Lattice's kernel: `put`, `open` and `delete` a file by key,
and `list` and `make_folder` for browsing. File contents never go in Postgres; their
metadata does.

| Store | Use | When |
|---|---|---|
| Local folder (`LATTICE_FILES_DIR`) | Attachments | Now |
| Mounted shares (`LATTICE_FOLDER_STORES`, or `create_app(folder_stores=…)`) | Folder picker | Now |
| S3-compatible (AWS, MinIO, Azure through its S3 layer) | Attachments, picker | When a host needs it |
| SharePoint and OneDrive (Microsoft Graph) | Picker, then attachments | When a host needs it; needs an app registration in the tenant |

**Attachments are a platform app in Lattice** (key `attachments`), beside Home, Account and
Administration:

- **A record panel on every record page** with a reference kind, as Comments: add files
  (drop or choose), download, preview images and PDFs, delete.
- **Linked by the record's URN**, never a foreign key.
- **Access follows the record**: a user sees and downloads a record's attachments only if
  the owning app's resolver lets them open the record, on every request.
- **Permissions**: `lattice.attachments.add` (default role editor; delete your own) and
  `lattice.attachments.manage` (delete anyone's, and Administration › Attachments).
- **Safety**: a size limit (`LATTICE_ATTACHMENT_MAX_MB`, 25) and an allowed list of file
  types (`LATTICE_ATTACHMENT_TYPES`); files are stored under random names; downloads are
  served as attachments, with only images and PDFs shown inline, and never as HTML or SVG.
- **Events and notifications**: `attachments.added` and `attachments.removed`; followers of
  the record are told of new files; webhooks receive the events.
- **History**: adding and deleting are in the audit log, on the record's history.

**The folder picker** is a form widget (`x-widget: folder` in JSON Schema forms, and a
macro for plain forms). Its value is `{store}:{path}`. **Browse…** opens a dialog that lists
one folder at a time from a mounted share and may create a folder. The server refuses any
path outside the share's root, and listing needs `lattice.folders.browse` (default role
editor).

## Not chosen

- **Files in Postgres**: the database would grow fast and large files would be slow.
- **Attachments as a separate app outside core**: the record page and every app need them,
  and apps cannot import each other (as for notifications, ADR 0016).
- **Building SharePoint first**: it needs a tenant's app registration and consent; a mounted
  share covers the need now.

## Consequences

- Deleting a record does not delete its attachments; the owning app removes them if it
  must (`attachments.remove_all(db, urn)`).
- Backups must include `LATTICE_FILES_DIR` as well as the database.

## SharePoint, as built (20 October 2026)

- **m365graph**, its own repository (a Graph client package shared with the mail engine),
  provides `DriveStore`: one SharePoint library, under a root folder, with the methods of
  Lattice's local store. Neither package imports the other; a host passes the object to
  `create_app(folder_stores=…, attachment_store=…)`.
- Lattice enforces its own attachment size limit whatever the store, and turns a store that
  does not answer into a clear error in the picker.
- Checked read-only against a real tenant: browsing a site's library, and checking and
  labelling a chosen folder.
