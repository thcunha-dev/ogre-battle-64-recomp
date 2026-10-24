#!/usr/bin/env python3
"""Version-consistency contract for Universal Item Randomizer release surfaces."""

from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/universal-item-randomizer"
WF = ROOT / ".github/workflows"


def main() -> int:
    data = tomllib.loads((MOD / "mod.toml").read_text())
    version = data["manifest"]["version"]
    assert version == "0.3.1"

    docs = {
        "TESTING.md": (MOD / "TESTING.md").read_text(),
        "STATUS.md": (MOD / "STATUS.md").read_text(),
        "SEED-VECTORS.md": (MOD / "SEED-VECTORS.md").read_text(),
    }
    for name, text in docs.items():
        assert version in text, f"{name}: current mod version {version} not documented"

    package = (WF / "randomizer-package.yml").read_text()
    runtime = (WF / "randomizer-runtime-build.yml").read_text()
    windows = (WF / "randomizer-windows-test.yml").read_text()

    for name, text in (
        ("package", package),
        ("runtime", runtime),
        ("windows", windows),
    ):
        assert f'version = "{version}"' in text or f"version={version}" in text, (
            name,
            "workflow does not assert/write current version",
        )

    assert f"universal-item-randomizer-{version}-nrm" in package
    assert f"universal-item-randomizer-{version}-integrated" in runtime
    assert f"universal-item-randomizer-{version}-qa-payload" in windows
    assert f"ogre-battle-64-randomizer-{version}-windows-test" in windows
    assert f"universal-item-randomizer-{version}" in windows

    # Reject stale release names in the three artifact-producing workflows.
    for stale in ("0.3.0", "0.2.0", "0.1.0"):
        assert stale not in package
        assert stale not in runtime
        assert stale not in windows

    print(f"universal randomizer version consistency: PASS ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
