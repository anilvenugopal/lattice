"""The showcase host: Lattice with the showcase and Comments apps. Run with `make dev`.

The folder picker (ADR 0017) offers a small sample share, made under var/ on first start, and,
when SHOWCASE_SHAREPOINT_SITE is set in .env, that site's library through m365graph, signing in
with the SHOWCASE_M365_* app registration (showcase_host/settings.py).
"""

from pathlib import Path

from m365graph import DriveStore, GraphClient

import lattice_comments
import lattice_showcase
from lattice.host import create_app
from showcase_host.settings import settings

SAMPLE_SHARE = Path("var/sample-share")
SAMPLE_FOLDERS = ["CAT-2610 Hurricane Delta/Lake Charles", "CAT-2610 Hurricane Delta/Beaumont–Port Arthur",
                  "CAT-2610 Hurricane Delta/Houston", "CAT-2608 Glass Fire/Napa",
                  "CAT-2608 Glass Fire/Sonoma", "CAT-2604 DFW Hail", "Templates"]
for folder in SAMPLE_FOLDERS:
    (SAMPLE_SHARE / folder).mkdir(parents=True, exist_ok=True)

folder_stores: dict = {"Claims share (sample)": SAMPLE_SHARE}
if settings.sharepoint_site:
    graph = GraphClient(settings.m365_tenant_id, settings.m365_client_id,
                        settings.m365_client_secret.get_secret_value())
    library = DriveStore.for_site(graph, settings.sharepoint_site, settings.sharepoint_library,
                                  root=settings.sharepoint_root)
    folder_stores[library.label] = library

app = create_app(apps=[lattice_showcase.APP, lattice_comments.APP], folder_stores=folder_stores)
