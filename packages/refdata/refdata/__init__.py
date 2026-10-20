"""refdata: public reference data loaded into Postgres (schema `ref`), with simple lookups.

Today: US towns, counties and zip codes to search by (Census gazetteer). It knows nothing
of Lattice or its apps. The public contract is docs/public_contract.md.
"""

from refdata.migrate import SCHEMA, migrate
from refdata.places import search_places

__version__ = "0.1.0"

__all__ = ["SCHEMA", "__version__", "migrate", "search_places"]
