"""The generated Reference pages match the code (run `lattice docs build` after changing it)."""

from lattice import reference
from lattice.cli import build_parser


def test_reference_pages_are_up_to_date():
    assert reference.stale(build_parser()) == [], "Run `uv run lattice docs build` and commit the pages."


def test_reference_covers_every_public_name():
    api_page = reference.pages(build_parser())["api.md"]
    for name in reference.api.__all__:
        assert f"`{name}`" in api_page
