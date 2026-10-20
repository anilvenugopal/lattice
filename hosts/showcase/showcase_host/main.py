"""The showcase host: Lattice with the showcase and Comments apps. Run with `make dev`.

It offers a small sample share to the folder picker (ADR 0017), made under var/ on first
start, so the picker can be tried without mounting a real one.
"""

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

app = create_app(apps=[lattice_showcase.APP, lattice_comments.APP],
                 folder_stores={"Claims share (sample)": SAMPLE_SHARE})
