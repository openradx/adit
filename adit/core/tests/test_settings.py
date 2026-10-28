import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "name, value",
    [
        ("C_MOVE_REFETCH_ATTEMPTS", "-1"),
        ("C_MOVE_REFETCH_MAX_MISSING_PERCENT", "-1"),
        ("C_MOVE_REFETCH_MAX_MISSING_PERCENT", "101"),
    ],
)
def test_settings_reject_out_of_range_c_move_values(name: str, value: str):
    result = subprocess.run(
        [sys.executable, "-c", "import adit.settings.base"],
        env={**os.environ, name: value},
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert f"ImproperlyConfigured: {name}" in result.stderr
