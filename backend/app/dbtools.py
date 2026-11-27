"""Self-healing database migration, run on every start (python -m app.cli migrate).

Plain `alembic upgrade head` fails in states that are easy to end up in by hand: tables created outside Alembic
(e.g. by the app's own create_all), a migration record pointing at a revision that no longer exists in the code, or two
baselines left in the migrations folder. This handles each one without ever dropping or altering existing data:

  empty database            -> run all migrations
  recorded revision known   -> upgrade to head (the normal case)
  tables but no record, or an unknown recorded revision
                            -> add whatever is missing (tables, columns, indexes), then mark the database as current
  more than one head in code-> stop with a clear message naming the stale files
A Postgres advisory lock stops two overlapping deploys from migrating at the same time."""
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from . import models  # noqa: F401 - register tables
from .db import Base, engine

BACKEND = Path(__file__).resolve().parents[1]
LOCK_ID = 727270001


def say(msg: str) -> None:
    print(f"[migrate] {msg}", flush=True)


def _cfg() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


def _versions(conn) -> list[str]:
    if not inspect(conn).has_table("alembic_version"):
        return []
    return [r[0] for r in conn.execute(text("select version_num from alembic_version"))]


def _flat(diffs):
    for d in diffs:
        if isinstance(d, list):
            yield from _flat(d)
        else:
            yield d


def schema_diff(conn) -> list:
    ctx = MigrationContext.configure(conn, opts={"compare_type": False, "compare_server_default": False})
    return list(_flat(compare_metadata(ctx, Base.metadata)))


def additive_sync(conn) -> list[str]:
    """Create what the code expects but the database lacks. Strictly additive: nothing is dropped, renamed or altered."""
    ctx = MigrationContext.configure(conn)
    ops, done = Operations(ctx), []
    for d in schema_diff(conn):
        if d[0] == "add_table":
            d[1].create(conn, checkfirst=True)
            done.append(f"created table {d[1].name}")
        elif d[0] == "add_column":
            _, _schema, table, col = d
            c = col.copy()
            if not c.nullable and c.server_default is None:       # can't add NOT NULL without a default to rows that exist
                c.nullable = True
            ops.add_column(table, c)
            done.append(f"added column {table}.{col.name}")
        elif d[0] == "add_index":
            d[1].create(conn, checkfirst=True)
            done.append(f"created index {d[1].name}")
    return done


def migrate() -> int:
    cfg = _cfg()
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) != 1:
        files = sorted(Path(script.versions).glob("*.py"))
        say(f"ERROR: {len(heads)} migration heads found ({', '.join(heads)}). A stale or duplicate file is in migrations/versions/.")
        say("Keep ONE linear chain and delete the rest. Files present: " + ", ".join(f.name for f in files))
        return 2
    head, known = heads[0], {r.revision for r in script.walk_revisions()}
    lock = engine.connect()
    try:
        if engine.dialect.name == "postgresql":
            lock.execute(text("select pg_advisory_lock(:i)"), {"i": LOCK_ID})
            lock.commit()
        with engine.connect() as conn:
            has_tables, current = inspect(conn).has_table("users"), _versions(conn)
        if not has_tables and not current:
            say("empty database: creating the schema")
            command.upgrade(cfg, "head")
        elif current and set(current) <= known:
            if current == [head]:
                say(f"up to date ({head})")
            else:
                say(f"upgrading {current[0]} -> {head}")
                command.upgrade(cfg, "head")
        else:
            why = "tables exist but there is no migration record" if not current else f"the recorded revision {current} does not exist in this code"
            say(f"{why}: adding anything missing, then marking the database as current")
            with engine.begin() as conn:
                for line in additive_sync(conn):
                    say("  " + line)
            command.stamp(cfg, "head", purge=True)
        with engine.begin() as conn:                                 # last safety net: heal any leftover additive drift
            left = additive_sync(conn)
        if left:
            say("WARNING: the schema was missing items the code needs (generate a migration for them): " + "; ".join(left))
        return 0
    finally:
        if engine.dialect.name == "postgresql":
            lock.execute(text("select pg_advisory_unlock(:i)"), {"i": LOCK_ID})
            lock.commit()
        lock.close()


def status() -> int:
    script = ScriptDirectory.from_config(_cfg())
    heads = script.get_heads()
    with engine.connect() as conn:
        current, tables = _versions(conn), len(inspect(conn).get_table_names())
        diff = [d for d in schema_diff(conn) if d[0].startswith("add_")]
    print(f"migration heads in code : {heads}{'  <-- MORE THAN ONE: delete stale files' if len(heads) != 1 else ''}")
    print(f"revision in database    : {current or 'none recorded'}")
    print(f"tables in database      : {tables}")
    print("schema matches the code" if not diff else "MISSING from the database: " + ", ".join(f"{d[0]} {getattr(d[1], 'name', '')}" if d[0] != 'add_column' else f"column {d[2]}.{d[3].name}" for d in diff))
    ok = len(heads) == 1 and current == heads and not diff
    print("verdict: healthy" if ok else "verdict: run `python -m app.cli migrate` (it repairs this safely)")
    return 0 if ok else 1
