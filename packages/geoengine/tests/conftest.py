"""A fresh database per test, migrated with geoengine, on the server GEOENGINE_TEST_URL
names (default: the Lattice workspace's development Postgres)."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

import geoengine

SERVER = os.environ.get("GEOENGINE_TEST_URL",
                        "postgresql+psycopg://lattice:lattice@127.0.0.1:5436/postgres")


@pytest.fixture
def conn():
    admin = create_engine(SERVER, isolation_level="AUTOCOMMIT")
    name = f"geoengine_test_{uuid4().hex[:10]}"
    with admin.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(make_url(SERVER).set(database=name))
    try:
        geoengine.migrate(engine)
        with engine.connect() as connection:
            yield connection
            connection.rollback()
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()
