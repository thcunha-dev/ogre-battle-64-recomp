#!/usr/bin/env python3
"""CI pipeline policy for Universal Item Randomizer artifacts.

Artifact-producing workflows must run the unified host suite before compiling or
uploading a randomizer package. This prevents a future YAML edit from bypassing
release-safety checks while leaving the source tests intact.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows"
SUITE = "python3 tools/test_universal_randomizer_all.py"


def assert_ordered(path: Path, required_after: tuple[str, ...]) -> None:
    text = path.read_text()
    suite_at = text.find(SUITE)
    assert suite_at >= 0, f"{path.name}: unified host suite missing"
    for token in required_after:
        at = text.find(token)
        assert at >= 0, f"{path.name}: missing {token}"
        assert at > suite_at, f"{path.name}: {token} can occur before host suite"


def main() -> int:
    # Every artifact-producing randomizer workflow is gated by the same suite.
    assert_ordered(
        WF / "randomizer-package.yml",
        ("RecompModTool", "actions/upload-artifact@v4"),
    )
    assert_ordered(
        WF / "randomizer-runtime-build.yml",
        ("Build complete librecomp runtime library", "actions/upload-artifact@v4"),
    )
    assert_ordered(
        WF / "randomizer-windows-test.yml",
        ("Compile and package 0.3.1", "Assemble self-contained QA payload", "actions/upload-artifact@v4"),
    )

    # The fast verification workflow must also execute the exact same suite.
    mapping = (WF / "randomizer-mapping.yml").read_text()
    assert SUITE in mapping

    # Artifact workflows must rerun when any randomizer host test changes.
    for name in (
        "randomizer-package.yml",
        "randomizer-runtime-build.yml",
        "randomizer-windows-test.yml",
    ):
        text = (WF / name).read_text()
        assert "tools/test_randomizer_*.py" in text, f"{name}: randomizer tests not in path trigger"
        assert "tools/test_universal_randomizer_*.py" in text, f"{name}: universal tests not in path trigger"

    print("universal randomizer pipeline policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
