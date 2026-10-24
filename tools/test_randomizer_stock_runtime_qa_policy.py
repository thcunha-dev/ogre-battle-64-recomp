#!/usr/bin/env python3
"""Policy contract for the official-v0.8.3 stock-runtime QA variant.

This variant exists only to unlock real gameplay QA before a custom Windows
runtime with Bank-N replacement support is available. Keep it deliberately
separate from the release mod and fail closed if the workflow ever starts
claiming coverage it cannot provide.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/universal-item-randomizer"
WF = ROOT / ".github/workflows/randomizer-stock-runtime-qa.yml"
OFFICIAL_WINDOWS_SHA256 = "d9c269587b2f2b224bc6203c7ac9c4f42022f6990643cd38a870cb56df243169"


def main() -> int:
    manifest = (MOD / "mod-stock-qa.toml").read_text()
    workflow = WF.read_text()
    readme = (MOD / "STOCK-RUNTIME-QA.md").read_text()

    # Never share runtime config/state with the final mod.
    assert 'id = "ogre_universal_item_randomizer_stock_qa"' in manifest
    assert 'mod_filename = "universal-item-randomizer-stock-qa"' in manifest
    assert 'display_name = "Universal Item Randomizer - Stock Runtime QA"' in manifest
    assert 'version = "0.3.1"' in manifest

    # Direct Bank-N starting/setup grants cannot be tested on the stock runtime.
    assert 'id = "starting_items"' not in manifest
    assert "Bank-R starting/setup direct grants" in readme
    assert "intentionally does NOT validate" in readme

    # Build from the exact same source tree, then alter only the two intended
    # central-grant properties in the temporary copy.
    assert 'cp mods/universal-item-randomizer/src/*.c' in workflow
    assert 'unexpected starting_items init shape' in workflow
    assert 'stock-runtime QA: direct Bank-N grants disabled' in workflow
    assert "unexpected central Bank-N patch shape" in workflow
    assert "text.replace(patch_old, patch_new)" in workflow

    # The stock reference file must contain only resolvable base sections.
    assert 'name = ".main"' in workflow
    assert 'name = ".streamedB"' in workflow
    stock_ref_block = workflow.split("cat >mods/reference/dump-stock-qa.toml <<'EOF'", 1)[1].split("EOF", 1)[0]
    assert "func_80072944" in stock_ref_block
    assert "func_80172820" in stock_ref_block
    assert "func_ovlN_801DC740" not in stock_ref_block
    assert ".bankN_record7" not in stock_ref_block

    # The artifact must advertise its reduced scope in machine-readable form.
    for marker in (
        "variant=stock_runtime_qa",
        "target_runtime=official_v0.8.3",
        "central_bank_n_patch=disabled",
        "starting_items=unsupported_in_this_variant",
        "post_battle_patch=enabled",
        "source_rewrites=table_o_table_p_reward",
        "native_save_metadata=none",
        "use_repair=native_slot_indexed",
    ):
        assert marker in workflow, f"stock QA manifest marker missing: {marker}"

    # The ready-to-run Windows bundle must be based byte-for-byte on the
    # published official v0.8.3 runtime before our .nrm is inserted.
    assert OFFICIAL_WINDOWS_SHA256 in workflow
    assert "ogre-battle-64-recomp-windows-x86_64.zip" in workflow
    assert 'echo "$expected  $official" | sha256sum -c -' in workflow
    assert "Assemble ready-to-run Windows QA bundle from official v0.8.3" in workflow
    assert 'mkdir -p "$appdir/mods"' in workflow
    assert 'universal-item-randomizer-stock-qa.nrm "$appdir/mods/"' in workflow
    assert "-iname '*.z64'" in workflow and "-iname '*.n64'" in workflow and "-iname '*.v64'" in workflow
    assert "ogre-battle-64-v0.8.3-stock-runtime-randomizer-qa-windows" in workflow
    assert f"official_windows_runtime_sha256={OFFICIAL_WINDOWS_SHA256}" in workflow

    # Source and policy changes must retrigger the QA artifact.
    for trigger in (
        "mods/universal-item-randomizer/src/**",
        "mods/universal-item-randomizer/include/**",
        "mods/universal-item-randomizer/mod-stock-qa.toml",
        "tools/test_randomizer_*.py",
        "tools/test_universal_randomizer_*.py",
    ):
        assert trigger in workflow, f"stock QA path trigger missing: {trigger}"

    assert "python3 tools/test_universal_randomizer_all.py" in workflow
    assert workflow.count("actions/upload-artifact@v4") >= 2
    assert "universal-item-randomizer-0.3.1-stock-runtime-qa" in workflow

    print("stock-runtime QA policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
