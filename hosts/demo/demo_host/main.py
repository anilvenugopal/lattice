"""The demo host: Lattice with the demo app. Run with `make dev`."""

import lattice_demo
from lattice.host import create_app

app = create_app(apps=[lattice_demo.APP])
