import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "deploy/scripts/switch_model.sh"


@pytest.mark.parametrize(
    "name",
    ["", "../x.gguf", "a/b.gguf", "x.txt", "mmproj-a.gguf", "nope.gguf", "a b.gguf"],
)
def test_bad_names_are_refused_before_docker(name):
    r = subprocess.run(  # noqa: S603
        ["bash", str(SCRIPT), name],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2
