"""Attachments on any record, file stores, and the folder picker (ADR 0017)."""

from pathlib import Path

import pytest

from lattice.api import AppManifest, ReferenceKind, Resolved, notifications, sql_queries, urn
from lattice.kernel.config import settings
from lattice.kernel.services import files
from lattice.testing import csrf

CHECK = sql_queries(Path(__file__).parent / "sql").checks
TICKET = urn("desk.ticket", 7)


def resolve_ticket(db, user, ticket_id):
    return Resolved(f"Ticket {ticket_id}", f"/desk/{ticket_id}") if ticket_id == "7" else None


@pytest.fixture
def host_apps():
    return [AppManifest(key="desk", label="Desk",
                        references=[ReferenceKind("desk.ticket", "Ticket", resolve_ticket)])]


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "files_dir", str(tmp_path / "files"))
    return files.attachments_store()


def upload(client, *named, subject=TICKET):
    return client.post("/attachments/add", headers={"X-CSRF-Token": csrf(client)},
                       data={"subject": subject},
                       files=[("files", (name, body)) for name, body in named])


def on(db, subject=TICKET):
    return db.all(CHECK.attachments_on, subject=subject)


# ── The store ────────────────────────────────────────────────────────────────

def test_the_local_store_writes_lists_and_stays_inside_its_root(tmp_path):
    s = files.LocalStore(tmp_path / "share", "Share")
    s.root.mkdir()
    size, digest = s.put("a/b.txt", [b"hello ", b"world"], max_bytes=100)
    assert size == 11 and len(digest) == 64 and s.open("a/b.txt").read() == b"hello world"
    with pytest.raises(files.TooLarge):
        s.put("a/big.bin", [b"x" * 60, b"x" * 60], max_bytes=100)
    assert not (s.root / "a" / "big.bin").exists() and not (s.root / "a" / "big.bin.part").exists()
    s.make_folder("", "Claims")
    s.make_folder("Claims", "CLM-1")
    assert [f.name for f in s.list("")] == ["a", "Claims"]
    assert [f.path for f in s.list("Claims")] == ["Claims/CLM-1"]
    for bad in ("../etc", "Claims/../../x"):
        with pytest.raises(files.BadPath):
            s.list(bad)
    with pytest.raises(files.BadPath):
        s.make_folder("", "..")


# ── Attachments ──────────────────────────────────────────────────────────────

def test_attach_download_preview_and_remove(as_user, users, db, store):
    c = as_user("editor")
    res = upload(c, ("photo.png", b"\x89PNG fake"), ("notes.txt", b"roof damage"))
    assert res.status_code == 200 and "photo.png" in res.text and "notes.txt" in res.text
    photo, notes = on(db)
    assert (photo["content_type"], photo["size"]) == ("image/png", 9)
    assert store.open(photo["store_key"]).read() == b"\x89PNG fake"

    viewer = as_user("viewer")                                  # may open the record: may read
    got = viewer.get(f"/attachments/{notes['id']}")
    assert got.content == b"roof damage" and got.headers["content-disposition"].startswith("attachment;")
    shown = viewer.get(f"/attachments/{photo['id']}?inline=1")
    assert shown.headers["content-disposition"].startswith("inline;")
    assert shown.headers["content-type"] == "image/png" and shown.headers["x-content-type-options"] == "nosniff"
    text_inline = viewer.get(f"/attachments/{notes['id']}?inline=1")
    assert text_inline.headers["content-disposition"].startswith("attachment;")   # only images, PDFs

    assert viewer.post(f"/attachments/{notes['id']}/delete",
                       headers={"X-CSRF-Token": csrf(viewer)}).status_code == 403
    c = as_user("editor")
    c.post(f"/attachments/{notes['id']}/delete", headers={"X-CSRF-Token": csrf(c)})
    assert [a["name"] for a in on(db)] == ["photo.png"]
    assert not (store.root / notes["store_key"]).exists()


def test_types_size_and_records_are_checked(as_user, db, monkeypatch):
    c = as_user("editor")
    res = upload(c, ("page.html", b"<script>"))
    assert "files of type .html are not accepted" in res.headers.get("hx-trigger", "")
    assert on(db) == []
    monkeypatch.setattr(settings, "attachment_max_mb", 1)
    upload(c, ("big.pdf", b"x" * (1024 * 1024 + 1)))
    assert on(db) == []
    assert upload(c, ("a.txt", b"x"), subject=urn("desk.ticket", 8)).status_code == 404
    assert upload(c, ("../../evil.txt", b"x")).status_code == 200
    assert on(db)[0]["name"] == "evil.txt"                     # folders in names are dropped
    assert upload(as_user("viewer"), ("a.txt", b"x")).status_code == 403


def test_followers_hear_of_new_files(as_user, users, db):
    notifications.follow(db, users["viewer"].id, TICKET)
    upload(as_user("editor"), ("estimate.pdf", b"%PDF-1.4"))
    [note] = db.all(CHECK.notifications_of, user_id=users["viewer"].id)
    assert note["title"] == "Editor attached estimate.pdf"


def test_administrators_see_every_file(as_user, db):
    upload(as_user("editor"), ("a.txt", b"x"))
    assert as_user("editor").get("/admin/attachments").status_code == 403
    assert "a.txt" in as_user("admin").get("/admin/attachments").text


# ── The folder picker ────────────────────────────────────────────────────────

@pytest.fixture
def share(tmp_path):
    root = tmp_path / "share"
    (root / "CAT-2610" / "Lake Charles").mkdir(parents=True)
    (root / ".hidden").mkdir()
    files.register_folder_stores({"Claims share": root})
    return root


def test_browse_a_share_one_folder_at_a_time(as_user, share):
    c = as_user("editor")
    assert c.get("/attachments/folders").json() == {"stores": [{"key": "claims-share", "label": "Claims share"}]}
    top = c.get("/attachments/folders/claims-share").json()
    assert [f["name"] for f in top["folders"]] == ["CAT-2610"]          # hidden folders left out
    inside = c.get("/attachments/folders/claims-share", params={"path": "CAT-2610"}).json()
    assert inside["crumbs"] == [{"name": "Claims share", "path": ""}, {"name": "CAT-2610", "path": "CAT-2610"}]
    assert c.get("/attachments/folders/claims-share", params={"path": "../.."}).status_code == 400
    made = c.post("/attachments/folders/claims-share/new", headers={"X-CSRF-Token": csrf(c)},
                  json={"path": "CAT-2610", "name": "Houston"}).json()
    assert made == {"name": "Houston", "path": "CAT-2610/Houston"} and (share / "CAT-2610" / "Houston").is_dir()
    assert as_user("viewer").get("/attachments/folders").status_code == 403


def test_a_chosen_folder_is_checked_and_reads_well(share):
    assert files.check_folder("claims-share:CAT-2610/Lake Charles") == "claims-share:CAT-2610/Lake Charles"
    assert files.folder_label("claims-share:CAT-2610/Lake Charles") == "Claims share / CAT-2610 / Lake Charles"
    for bad in ("claims-share:CAT-2610/Nope", "nowhere:x", "claims-share:../.."):
        with pytest.raises(files.BadPath):
            files.check_folder(bad)
