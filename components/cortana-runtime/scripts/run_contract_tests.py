"""Run tests with scratch files confined to this workspace."""
import sys
import tempfile
import faulthandler
from pathlib import Path
root = Path(__file__).resolve().parents[1]
scratch = root / 'tests' / '.runtime-fixture' / 'local-architecture'
scratch.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(scratch)
faulthandler.dump_traceback_later(45,repeat=True)
import pytest
raise SystemExit(pytest.main(sys.argv[1:] or ['tests','-q']))
