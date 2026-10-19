"""The showcase host: Lattice with the showcase app. Run with `make dev`."""

import lattice_showcase
from lattice.host import create_app

app = create_app(apps=[lattice_showcase.APP])
