"""The demo host: Lattice with the demo app."""

from lattice.features import APP as DEMO
from lattice.host import create_app

app = create_app(apps=[DEMO])
