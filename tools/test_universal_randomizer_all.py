#!/usr/bin/env python3
"""Run the complete host-side Universal Item Randomizer verification suite."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = (
    "tools/test_randomizer_save_safety.py",
    "tools/test_universal_randomizer_mapping.py",
    "tools/test_randomizer_golden_vectors.py",
    "tools/test_randomizer_release_policy.py",
    "tools/test_randomizer_pipeline_policy.py",
    "tools/test_randomizer_version_consistency.py",
    "tools/test_randomizer_config_lifecycle.py",
    "tools/test_stock_runtime_coverage.py",
    "tools/test_inventory_writer_taxonomy.py",
    "tools/test_randomizer_qa_telemetry.py",
    "tools/test_randomizer_persistence_model.py",
    "tools/test_randomizer_source_shadow_model.py",
    "tools/test_randomizer_drop_table_validation.py",
    "tools/test_randomizer_pickup_reward_validation.py",
    "tools/test_randomizer_grant_validation.py",
    "tools/test_randomizer_shop_model.py",
    "tools/test_randomizer_inventory_capacity_model.py",
    "tools/test_randomizer_use_repair_model.py",
)


def main() -> int:
    if sys.argv[1:] == ["--count"]:
        print(len(TESTS))
        return 0
    if sys.argv[1:]:
        raise SystemExit("usage: test_universal_randomizer_all.py [--count]")

    for rel in TESTS:
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"missing randomizer test: {rel}")
        print(f"==> {rel}", flush=True)
        subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)
    print(f"universal randomizer full host suite: PASS ({len(TESTS)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
