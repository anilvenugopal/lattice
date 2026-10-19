import pytest

import lattice_comments
import lattice_showcase


@pytest.fixture
def host_apps():
    # Comments with an app whose records it can comment on.
    return [lattice_showcase.APP, lattice_comments.APP]
