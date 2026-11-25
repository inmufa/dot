from pathlib import Path

import pytest
from dot_sandbox import jail
from dot_sandbox.errors import SandboxError


def test_unrestricted_allows_paths_outside_root(tmp_path: Path):
    jail.configure(unrestricted=False)
    with pytest.raises(SandboxError):
        jail.resolve(tmp_path, "/etc/hostname")
    jail.configure(unrestricted=True)
    try:
        assert (
            jail.resolve(tmp_path, "/etc/hostname") == Path("/etc/hostname").resolve()
        )
        assert jail.inside(tmp_path, Path("/etc"))
    finally:
        jail.configure(unrestricted=False)
