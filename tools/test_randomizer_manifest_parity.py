#!/usr/bin/env python3
"""Require release artifacts to advertise the same core safety guarantees."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows"

COMMON = (
    "version=0.3.1",
    "host_suite=${suite_count}_tests",
    "use_repair=native_slot_indexed",
    "persistence_model=5000_on_off_on_sequences",
    "postgame_persistence_model=2000_finished_game_on_off_on_sequences",
    "campaign_stress_model=1000_campaigns_x_600_events",
)

FULL_ARTIFACTS = (
    "randomizer-package.yml",
    "randomizer-runtime-build.yml",
    "randomizer-windows-test.yml",
)


def main() -> int:
    texts = {name: (WF / name).read_text() for name in FULL_ARTIFACTS}
    stock = (WF / "randomizer-stock-runtime-qa.yml").read_text()

    for name, text in (*texts.items(), ("randomizer-stock-runtime-qa.yml", stock)):
        for marker in COMMON:
            assert marker in text, f"{name}: manifest parity marker missing: {marker}"

    for name, text in texts.items():
        assert "save_policy=no_randomizer_metadata_in_native_save" in text, f"{name}: save policy missing"
        assert "config_lifecycle=restart_required" in text, f"{name}: restart lifecycle missing"
        assert "source_commit=${GITHUB_SHA}" in text, f"{name}: source commit provenance missing"
        assert "nrm_sha256=${nrm_sha}" in text, f"{name}: NRM digest provenance missing"
        assert "central_grant_a1=native_consumable_used_flag" in text, f"{name}: a1 contract missing"
        assert "bank_r_coupled_grants=two_a1_one_callers_fail_closed" in text, f"{name}: coupled grant contract missing"
        assert "starting_items_scope=forty_literal_a1_zero_no_store_calls" in text, f"{name}: starter scope missing"

    # Stock QA intentionally excludes the Bank-N central replacement, but it
    # must preserve the equivalent native-save guarantee and identify the exact
    # source commit used to assemble the QA bundle.
    assert "native_save_metadata=none" in stock
    assert "central_bank_n_patch=disabled" in stock
    assert "head_sha=${GITHUB_SHA}" in stock
    assert "official_windows_runtime_sha256=d9c269587b2f2b224bc6203c7ac9c4f42022f6990643cd38a870cb56df243169" in stock

    print("randomizer artifact manifest parity: PASS (4 artifact families aligned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
