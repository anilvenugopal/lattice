"""Lattice's own named queries, from lattice/sql/*.sql: `SQL.users.by_email`."""

from pathlib import Path

from lattice.kernel.sql import sql_queries

SQL = sql_queries(Path(__file__).parents[1] / "sql")
