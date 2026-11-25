# Migrations

`versions/` must contain **one linear chain**. Before the first production deploy there is a single baseline
(`2cb0eaba0e78_baseline_v0_3.py`).

**Once a real database exists (Neon), never regenerate the baseline again.** Add incremental migrations only:

    alembic revision --autogenerate -m "describe the change"   # review the generated file
    alembic upgrade head                                        # runs automatically on every API start

If you ever see "Multiple head revisions are present": a stale or duplicate migration file is in `versions/`.
Delete the extras (keep the newest chain), commit, push. `tests/test_migrations.py` fails CI on this.
