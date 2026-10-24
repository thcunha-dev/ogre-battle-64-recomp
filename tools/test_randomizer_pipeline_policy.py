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
ABI_AUDIT_TRIGGER = "tools/audit_randomizer_*_abi_rom.py"
ROM_VERIFY_TRIGGER = "tools/verify_randomizer_rev_a_rom.py"
ROM_VERIFY_FILE = "verify_randomizer_rev_a_rom.py"

ABI_AUDIT_FILES = (
    "audit_randomizer_grant_abi_rom.py",
    "audit_randomizer_post_battle_abi_rom.py",
    "audit_randomizer_coupled_a1_abi_rom.py",
    "audit_randomizer_starting_block_abi_rom.py",
)

ARTIFACT_MARKERS = (
    "central_grant_a1=native_consumable_used_flag",
    "bank_r_coupled_grants=two_a1_one_callers_fail_closed",
    "starting_items_scope=forty_literal_a1_zero_no_store_calls",
)


def assert_ordered(path: Path, required_after: tuple[str, ...]) -> None:
    text = path.read_text()
    suite_at = text.find(SUITE)
    assert suite_at >= 0, f"{path.name}: unified host suite missing"
    for token in required_after:
        at = text.find(token)
        assert at >= 0, f"{path.name}: missing {token}"
        assert at > suite_at, f"{path.name}: {token} can occur before host suite"


def main() -> int:
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

    mapping = (WF / "randomizer-mapping.yml").read_text()
    assert SUITE in mapping
    assert ABI_AUDIT_TRIGGER in mapping, "mapping: ABI auditors not in path trigger"
    assert ROM_VERIFY_TRIGGER in mapping, "mapping: one-command ROM verifier not in path trigger"

    for name in (
        "randomizer-package.yml",
        "randomizer-runtime-build.yml",
        "randomizer-windows-test.yml",
    ):
        text = (WF / name).read_text()
        assert "tools/test_randomizer_*.py" in text, f"{name}: randomizer tests not in path trigger"
        assert "tools/test_universal_randomizer_*.py" in text, f"{name}: universal tests not in path trigger"
        assert ABI_AUDIT_TRIGGER in text, f"{name}: ABI auditors not in path trigger"
        assert ELF_TRIGGER in text, f"{name}: ELF verifier not in path trigger"
        assert ELF_VERIFY in text, f"{name}: shared ELF verifier not executed"

    runtime = (WF / "randomizer-runtime-build.yml").read_text()
    windows = (WF / "randomizer-windows-test.yml").read_text()

    for name, text in (("runtime", runtime), ("windows", windows)):
        assert "config_lifecycle=restart_required" in text, f"{name}: lifecycle marker missing"
        assert "host_suite=${suite_count}_tests" in text, f"{name}: suite count not dynamic"
        assert "elf_symbols=critical_replacements_present" in text, f"{name}: ELF marker missing"
        assert "use_repair=native_slot_indexed" in text, f"{name}: native slot-indexed use repair marker missing"
        for marker in ARTIFACT_MARKERS:
            assert marker in text, f"{name}: ABI/Bank-R artifact marker missing: {marker}"
        assert "seed_vectors=123456_locked" in text, f"{name}: golden-vector marker missing"

    assert ROM_VERIFY_TRIGGER in windows, "windows QA: ROM verifier not in path trigger"
    assert "rom_verifier=one_command_four_audits" in windows, "windows QA: ROM verifier marker missing"
    assert f"cp tools/{ROM_VERIFY_FILE} \"$qa/\"" in windows, "QA payload does not ship ROM verifier"

    for token in (
        "QA-CHECKLIST.md",
        "VERIFY-QA.ps1",
        "Self-verify QA payload",
        "./build/qa/universal-item-randomizer-0.3.1/VERIFY-QA.ps1",
        "Verify QA payload",
        "./build/qa/VERIFY-QA.ps1",
    ):
        assert token in windows, f"windows QA pipeline missing {token}"

    for audit in ABI_AUDIT_FILES:
        assert f"cp tools/{audit} \"$qa/\"" in windows, f"QA payload does not ship {audit}"

    verifier = (ROOT / "mods/universal-item-randomizer/VERIFY-QA.ps1").read_text()
    assert '$Manifest["use_repair"] -ne "native_slot_indexed"' in verifier
    assert '$Manifest["central_grant_a1"] -ne "native_consumable_used_flag"' in verifier
    assert '$Manifest["bank_r_coupled_grants"] -ne "two_a1_one_callers_fail_closed"' in verifier
    assert '$Manifest["starting_items_scope"] -ne "forty_literal_a1_zero_no_store_calls"' in verifier
    assert '$Manifest["rom_verifier"] -ne "one_command_four_audits"' in verifier
    assert f'"{ROM_VERIFY_FILE}"' in verifier, "VERIFY-QA does not require ROM verifier"
    for audit in ABI_AUDIT_FILES:
        assert f'"{audit}"' in verifier, f"VERIFY-QA does not require {audit}"

    print("universal randomizer pipeline policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
