"""Keep new persistent workflow state isolated for every contract test."""
import sys
from pathlib import Path
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'agent'), str(Path(__file__).resolve().parents[1])]


@pytest.fixture(autouse=True)
def isolate_architecture_store(tmp_path, monkeypatch):
    from core.config import settings
    from core import db
    monkeypatch.setattr(settings, 'memory_dir', str(tmp_path / 'architecture-memory'))
    monkeypatch.setattr(db,'DB_PATH',tmp_path/'cortana-test.sqlite3')
    monkeypatch.setattr(db,'_schema_ready',False)
