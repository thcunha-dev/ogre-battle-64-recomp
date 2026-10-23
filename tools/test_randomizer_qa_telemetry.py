#!/usr/bin/env python3
"""Static contract for Universal Item Randomizer QA telemetry.

The diagnostic layer exists only to prove which acquisition route was exercised
while testing. It must stay bounded and observational: no save metadata, no
inventory-delta heuristic, and no route may depend on formatted/unbounded logs.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mods/universal-item-randomizer/src/universal_item_randomizer.c"
POST = ROOT / "mods/universal-item-randomizer/src/post_battle_add.c"

main = SRC.read_text(encoding="utf-8")
post = POST.read_text(encoding="utf-8")

required_messages = (
    "universal-item-randomizer: map/drop source mapped",
    "universal-item-randomizer: ground pickup source mapped",
    "universal-item-randomizer: battle reward source mapped",
    "universal-item-randomizer: starting/setup direct grant mapped",
    "universal-item-randomizer: post-battle equipment add mapped",
    "universal-item-randomizer: coupled Bank-R unit loadout left vanilla",
)

for message in required_messages:
    assert message in main, f"missing QA route diagnostic: {message}"

assert "static void log_bounded(" in main
assert "*counter >= 4u" in main, "QA route logging must remain bounded"
assert "universal_item_randomizer_log_post_battle" in main
assert "universal_item_randomizer_log_post_battle();" in post

# Diagnostics may identify a route, but must never become a save/load detector or
# inventory-delta watcher. The randomizer's save-safety contract depends on
# acquisition sources/patches rather than observing reconstructed inventory.
for forbidden in (
    'RECOMP_HOOK("func_800749C0")',
    "inventory_shadow",
    "BULK_SLOTS",
    "save_seed",
    "seed_in_save",
):
    assert forbidden not in main
    assert forbidden not in post

# The logger is deliberately string-only. Do not introduce sprintf-family
# formatting into the freestanding mod merely for QA telemetry.
for forbidden in ("sprintf(", "snprintf(", "printf("):
    assert forbidden not in main
    assert forbidden not in post

print("randomizer QA telemetry contract: OK")
