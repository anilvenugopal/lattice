"""The import contracts in pyproject.toml ([tool.importlinter]) hold (ADR 0002)."""

import subprocess
import sys
from pathlib import Path


def test_import_contracts_are_kept():
    lint = Path(sys.executable).with_name("lint-imports")
    result = subprocess.run([str(lint)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-3000:]
