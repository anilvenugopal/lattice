# refdata: public contract

Everything another package may rely on. Anything not listed is internal and may change in
any release. `tests/test_public_contract.py` checks this document against the code and a
migrated database. Version: the package's (`refdata.__version__`), semantic versioning;
before 1.0 a minor release may break the contract and a patch never does.

Requires Python 3.14+ and PostgreSQL 18+.

## Python names

| name | kind | parameters |
|---|---|---|
| migrate | function | target |
| search_places | function | conn, text, limit |
| SCHEMA | constant | "ref" |

`migrate(target)` takes a database URL, an engine or a connection, applies pending
migrations and loads bundled datasets that are missing; it returns what it did. Safe to
repeat.

`search_places(conn, text, limit=8)` returns places whose name starts with `text`, an exact
name first, then towns before counties before zip codes, larger first. `"Name, ST"` narrows
to a state. Each result is a dict with `kind`, `name`, `state`, `lon`, `lat` and `label`.

## Tables in schema ref

Callers may read these in their own SQL; only `migrate` writes them.

### ref.place

| column | type |
|---|---|
| id | bigint |
| kind | character varying |
| name | character varying |
| state | character varying |
| lon | double precision |
| lat | double precision |
| sqmi | real |

`kind` is one of `place`, `county`, `zip`.
