from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_exactly_one_migration_head():
    """Render runs `alembic upgrade head` on every start; two heads (e.g. stale baselines left over from an
    older checkout) make that fail and the API never boots."""
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"multiple migration heads: {heads}. Delete stale files in migrations/versions/."
    roots = [r for r in script.walk_revisions() if r.down_revision is None]
    assert len(roots) == 1, f"multiple baseline migrations: {[r.revision for r in roots]}"
