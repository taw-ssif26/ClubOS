"""Every way a production database can be 'in the wrong state', run exactly as the host runs it (python -m app.cli migrate).
PostgreSQL only: SQLite can't express most of these situations."""
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]
BASE = os.environ["DATABASE_URL"]
pytestmark = pytest.mark.skipif(not BASE.startswith("postgres"), reason="needs PostgreSQL")
STALE = BACKEND / "migrations" / "versions" / "zzzz99990000_stale_baseline.py"
HEAD = "c0de00000001"
NEW_COLS = {"clubs": ["status", "status_note", "leaderboard_enabled", "location_mode", "place", "address", "latitude", "longitude"],
            "events": ["location_mode", "place", "address", "latitude", "longitude"], "users": ["place", "latitude", "longitude"],
            "posts": ["attachments"], "uploads": ["kind"]}


def _psy(url: str):
    return make_url(url).set(drivername="postgresql+psycopg")


@pytest.fixture
def db():
    name = f"mig_t_{uuid.uuid4().hex[:8]}"
    admin = create_engine(_psy(BASE).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'create database "{name}"'))
    url = str(make_url(BASE).set(database=name).render_as_string(hide_password=False))
    yield url
    with admin.connect() as c:
        c.execute(text(f'drop database if exists "{name}" with (force)'))
    admin.dispose()


def run(url, *cmd):
    env = {**os.environ, "DATABASE_URL": url, "AUTO_CREATE_TABLES": "false"}
    return subprocess.run(list(cmd), cwd=BACKEND, env=env, capture_output=True, text=True)


def migrate(url):
    return run(url, sys.executable, "-m", "app.cli", "migrate")


def alembic(url, *args):
    return run(url, sys.executable, "-m", "alembic", *args)


def create_all(url):
    r = run(url, sys.executable, "-c", "from app.db import Base, engine; from app import models; Base.metadata.create_all(engine)")
    assert r.returncode == 0, r.stderr


def eng(url):
    return create_engine(_psy(url))


def version(url):
    with eng(url).connect() as c:
        return [r[0] for r in c.execute(text("select version_num from alembic_version"))] if inspect(c).has_table("alembic_version") else []


def cols(url, table):
    with eng(url).connect() as c:
        return {x["name"] for x in inspect(c).get_columns(table)}


def insert_legacy_club(url):
    """A row shaped like production data written by the OLD schema (new columns absent)."""
    e = eng(url)
    with e.begin() as c:
        uid, cid = str(uuid.uuid4()), str(uuid.uuid4())
        def fill(table, given):
            need = c.execute(text("select column_name,data_type from information_schema.columns where table_name=:t and is_nullable='NO' and column_default is null"), {"t": table}).all()
            row = dict(given)
            for n, t in need:
                row.setdefault(n, {"uuid": str(uuid.uuid4()), "boolean": False, "integer": 0, "json": "[]", "jsonb": "[]"}.get(t, "now()" if "timestamp" in t else "x"))
            keys = ", ".join(row); vals = ", ".join("now()" if v == "now()" else f":{k}" for k, v in row.items())
            c.execute(text(f"insert into {table} ({keys}) values ({vals})"), {k: v for k, v in row.items() if v != "now()"})
        fill("users", {"id": uid, "email": "legacy@x.com", "username": "legacy", "full_name": "Legacy", "skills": "[]", "social_links": "{}"})
        fill("clubs", {"id": cid, "name": "Legacy Club", "slug": "legacy-club", "created_by": uid, "social_links": "{}", "application_fields": "[]", "theme": "{}", "visibility": "public"})


def club_status(url):
    with eng(url).connect() as c:
        return c.execute(text("select name, status, location_mode from clubs")).all()


def test_fresh_database_then_rerun_is_a_noop(db):
    r = migrate(db)
    assert r.returncode == 0 and version(db) == [HEAD], r.stdout + r.stderr
    again = migrate(db)
    assert again.returncode == 0 and "up to date" in again.stdout
    assert run(db, sys.executable, "-m", "app.cli", "db-status").returncode == 0


def test_normal_upgrade_keeps_existing_clubs_and_marks_them_approved(db):
    assert alembic(db, "upgrade", "2cb0eaba0e78").returncode == 0
    insert_legacy_club(db)
    r = migrate(db)
    assert r.returncode == 0 and "upgrading" in r.stdout, r.stdout + r.stderr
    assert club_status(db) == [("Legacy Club", "approved", "onsite")]       # nothing disappears; existing clubs stay live


def test_state_A_tables_built_outside_alembic(db):
    """The quick-fix scenario: the app's create_all built the schema, so there is no migration record."""
    create_all(db)
    assert version(db) == []
    r = migrate(db)
    assert r.returncode == 0 and "no migration record" in r.stdout, r.stdout + r.stderr
    assert version(db) == [HEAD]


def test_state_A_even_plain_alembic_now_succeeds(db):
    create_all(db)
    r = alembic(db, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-400:]                                  # migrations adopt an existing schema instead of crashing
    assert version(db) == [HEAD]


def test_state_A_old_code_schema_is_topped_up_without_losing_rows(db):
    create_all(db)
    insert_legacy_club(db)
    e = eng(db)
    with e.begin() as c:                                                       # make it look like the schema of an OLDER release
        for table, names in NEW_COLS.items():
            for n in names:
                c.execute(text(f'alter table {table} drop column "{n}"'))
        c.execute(text("drop table point_entries"))
    r = migrate(db)
    assert r.returncode == 0, r.stdout + r.stderr
    for table, names in NEW_COLS.items():
        assert set(names) <= cols(db, table), table
    assert club_status(db) == [("Legacy Club", "approved", "onsite")]
    assert version(db) == [HEAD] and "point_entries" in inspect(eng(db)).get_table_names()


def test_state_B_recorded_revision_no_longer_exists_in_the_code(db):
    assert alembic(db, "upgrade", "2cb0eaba0e78").returncode == 0
    insert_legacy_club(db)
    with eng(db).begin() as c:
        c.execute(text("update alembic_version set version_num='ebd33f85eea4'"))
    assert alembic(db, "upgrade", "head").returncode != 0                      # what plain alembic does: "Can't locate revision"
    r = migrate(db)
    assert r.returncode == 0 and "does not exist in this code" in r.stdout, r.stdout + r.stderr
    assert version(db) == [HEAD] and club_status(db) == [("Legacy Club", "approved", "onsite")]


def test_state_C_two_migration_chains_fails_loudly_and_changes_nothing(db):
    shutil.copy(BACKEND / "migrations/versions/2cb0eaba0e78_baseline_v0_3.py", STALE)
    STALE.write_text(STALE.read_text().replace("2cb0eaba0e78", "zzzz99990000"))
    try:
        r = migrate(db)
        assert r.returncode == 2 and "zzzz99990000_stale_baseline.py" in r.stdout and "delete the rest" in r.stdout
        assert version(db) == [] and not inspect(eng(db)).get_table_names()    # database untouched
    finally:
        STALE.unlink(missing_ok=True)
        shutil.rmtree(BACKEND / "migrations/versions/__pycache__", ignore_errors=True)


def test_concurrent_deploys_do_not_collide(db):
    procs = [subprocess.Popen([sys.executable, "-m", "app.cli", "migrate"], cwd=BACKEND, env={**os.environ, "DATABASE_URL": db, "AUTO_CREATE_TABLES": "false"},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
    outs = [p.communicate() for p in procs]
    assert [p.returncode for p in procs] == [0, 0, 0], [o[0] + o[1] for o in outs]
    assert version(db) == [HEAD]
