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
ELF_VERIFY = "bash tools/verify_randomizer_elf.sh"
ELF_TRIGGER = "tools/verify_randomizer_elf.sh"


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
        (ELF_VERIFY, "RecompModTool", "actions/upload-artifact@v4"),
    )
    assert_ordered(
        WF / "randomizer-runtime-build.yml",
        ("Build complete librecomp runtime library", ELF_VERIFY, "actions/upload-artifact@v4"),
    )
    assert_ordered(
        WF / "randomizer-windows-test.yml",
        ("Compile and package 0.3.1", ELF_VERIFY, "Assemble self-contained QA payload", "actions/upload-artifact@v4"),
    )

    # The fast verification workflow must also execute the exact same suite.
    mapping = (WF / "randomizer-mapping.yml").read_text()
    assert SUITE in mapping

    # Artifact workflows must rerun when any randomizer host test or the shared
    # binary contract changes.
    for name in (
        "randomizer-package.yml",
        "randomizer-runtime-build.yml",
        "randomizer-windows-test.yml",
    ):
        text = (WF / name).read_text()
        assert "tools/test_randomizer_*.py" in text, f"{name}: randomizer tests not in path trigger"
        assert "tools/test_universal_randomizer_*.py" in text, f"{name}: universal tests not in path trigger"
        assert ELF_TRIGGER in text, f"{name}: ELF verifier not in path trigger"
        assert ELF_VERIFY in text, f"{name}: shared ELF verifier not executed"

    runtime = (WF / "randomizer-runtime-build.yml").read_text()
    windows = (WF / "randomizer-windows-test.yml").read_text()

    # Traceability markers must be emitted by both QA manifests.
    for name, text in (("runtime", runtime), ("windows", windows)):
        assert "config_lifecycle=restart_required" in text, f"{name}: lifecycle marker missing"
        assert "host_suite=${suite_count}_tests" in text, f"{name}: suite count not dynamic"
        assert "elf_symbols=critical_replacements_present" in text, f"{name}: ELF marker missing"
        assert "seed_vectors=123456_locked" in text, f"{name}: golden-vector marker missing"

    # The self-contained QA artifact must carry its executable integrity check and
    # the short acceptance checklist, and must execute the verifier before upload.
    for token in (
        "QA-CHECKLIST.md",
        "VERIFY-QA.ps1",
        "Self-verify QA payload",
        "./build/qa/universal-item-randomizer-0.3.1/VERIFY-QA.ps1",
        "Verify QA payload",
        "./build/qa/VERIFY-QA.ps1",
    ):
        assert token in windows, f"windows QA pipeline missing {token}"

    print("universal randomizer pipeline policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
