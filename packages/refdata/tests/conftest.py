"""A fresh database per test session, migrated with refdata, on the server REFDATA_TEST_URL
names (default: the Lattice workspace's development Postgres)."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

import refdata

SERVER = os.environ.get("REFDATA_TEST_URL",
                        "postgresql+psycopg://lattice:lattice@127.0.0.1:5436/postgres")


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(SERVER, isolation_level="AUTOCOMMIT")
    name = f"refdata_test_{uuid4().hex[:10]}"
    with admin.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = create_engine(make_url(SERVER).set(database=name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.dispose()


@pytest.fixture(scope="session")
def migrated(engine):
    return refdata.migrate(engine)


@pytest.fixture
def conn(engine, migrated):
    with engine.connect() as connection:
        yield connection
