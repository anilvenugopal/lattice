"""The showcase host: Lattice with the showcase and Comments apps. Run with `make dev`."""

import lattice_comments
import lattice_showcase
from lattice.host import create_app

app = create_app(apps=[lattice_showcase.APP, lattice_comments.APP])
