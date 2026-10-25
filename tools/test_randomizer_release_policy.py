#!/usr/bin/env python3
"""Release-policy contract for Universal Item Randomizer.

This test protects the safe defaults and packaging metadata that can regress
without touching the runtime C implementation.
"""

from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods/universal-item-randomizer"


def option_map(manifest: dict) -> dict[str, dict]:
    options = manifest["manifest"].get("config_options", [])
    return {entry["id"]: entry for entry in options}


def main() -> int:
    data = tomllib.loads((MOD / "mod.toml").read_text())
    manifest = data["manifest"]
    inputs = data["inputs"]

    assert manifest["id"] == "ogre_universal_item_randomizer"
    assert manifest["version"] == "0.3.1"
    assert manifest["game_id"] == "ogrebattle64"
    assert manifest["enabled_by_default"] is False
    assert manifest["dependencies"] == []
    assert manifest["native_libraries"] == []

    options = option_map(data)
    assert set(options) == {"seed", "shops", "starting_items", "key_items", "log"}

    seed = options["seed"]
    assert seed["type"] == "Number"
    assert seed["min"] == 1
    assert seed["max"] == 4294967295
    assert seed["step"] == 1
    assert seed["precision"] == 0
    assert seed["default"] == 1

    for opt in ("shops", "starting_items", "key_items", "log"):
        assert options[opt]["type"] == "Bool", opt
        assert options[opt]["default"] is False, f"unsafe default enabled: {opt}"

    # RecompModTool compatibility: the empty data-reference array is required
    # by the pinned tool and must remain explicit.
    assert inputs["elf_path"] == "build/mod.elf"
    assert inputs["mod_filename"] == "universal-item-randomizer"
    assert inputs["func_reference_syms_file"] == "../reference/dump.toml"
    assert inputs["data_reference_syms_files"] == []
    assert inputs["additional_files"] == []

    description = manifest["description"]
    for token in (
        "never stores randomizer metadata",
        "protected by default",
        "Unclassified Bank-N grant callers stay vanilla",
    ):
        assert token in description

    print("universal randomizer release policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
