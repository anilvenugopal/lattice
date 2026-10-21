"""The showcase host: Lattice with the showcase and Comments apps. Run with `make dev`.

The folder picker (ADR 0017) offers a small sample share, made under var/ on first start.
With SHOWCASE_SHAREPOINT_SITE set (e.g. "contoso.sharepoint.com:/sites/claims"), it also
offers that site's library through m365graph, signing in with the app credentials in
M365_ENV_FILE (TENANT_ID, CLIENT_ID, CLIENT_SECRET). m365graph is installed only then.
"""

import os
from pathlib import Path

import lattice_comments
import lattice_showcase
from lattice.host import create_app

SAMPLE_SHARE = Path("var/sample-share")
SAMPLE_FOLDERS = ["CAT-2610 Hurricane Delta/Lake Charles", "CAT-2610 Hurricane Delta/Beaumont–Port Arthur",
                  "CAT-2610 Hurricane Delta/Houston", "CAT-2608 Glass Fire/Napa",
                  "CAT-2608 Glass Fire/Sonoma", "CAT-2604 DFW Hail", "Templates"]
for folder in SAMPLE_FOLDERS:
    (SAMPLE_SHARE / folder).mkdir(parents=True, exist_ok=True)

folder_stores: dict = {"Claims share (sample)": SAMPLE_SHARE}
if site := os.getenv("SHOWCASE_SHAREPOINT_SITE"):
    from m365graph import DriveStore, GraphClient  # uv pip install -e ../m365graph python-dotenv

    graph = GraphClient.from_env(os.getenv("M365_ENV_FILE", ".env.m365"))
    library = DriveStore.for_site(graph, site, os.getenv("SHOWCASE_SHAREPOINT_LIBRARY", ""),
                                  root=os.getenv("SHOWCASE_SHAREPOINT_ROOT", ""))
    folder_stores[library.label] = library

app = create_app(apps=[lattice_showcase.APP, lattice_comments.APP], folder_stores=folder_stores)
