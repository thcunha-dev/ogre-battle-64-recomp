#!/usr/bin/env python3
"""Static/runtime contracts for the Playable Knight of Danika restoration.

The full class record begins at D_80187C34 with stride 0x48. D_80187C62,
previously used as the record origin during early research, is actually the
record+0x2E field anchor used by a family of class accessors.

This audit also encodes the fail-closed rule for the eventual playable-class
presentation override: class 0x71 may borrow Dragoon presentation data only
when the runtime participant has been positively identified as allied. Enemy
or unknown ownership must keep the original Gatekeeper/Danika path untouched.
"""

from enum import Enum

CLASS_RECORD_BASE = 0x80187C34
CLASS_STRIDE = 0x48
MAX_COMPLETE_CLASS_ID = 0xFE

# Important field anchors within each true 0x48-byte record.
FIELD_2E_BASE = 0x80187C62
ALIAS_KEY_BASE = 0x80187C79
FIELD_2E_OFFSET = FIELD_2E_BASE - CLASS_RECORD_BASE
ALIAS_KEY_OFFSET = ALIAS_KEY_BASE - CLASS_RECORD_BASE

DRAGOON = 0x14
KNIGHT_OF_DANIKA = 0x71
HIDDEN_DRAGOON = 0x9C

# Runtime research contracts established by the battle probes.
# A participant can be bridged back to a persistent roster record with this
# exact stride. The roster slot is useful evidence, but it is NOT by itself a
# proof of ownership until the player-roster bounds/base are demonstrated.
PERSISTENT_ROSTER_STRIDE = 0x38
BATTLE_VISUAL_SELECTOR_OFFSET = 0x00

# Bank AH: ROM 0x23A370 -> RAM 0x801D0860, size 0xE80.
BANK_AH_ROM_BASE = 0x23A370
BANK_AH_RAM_BASE = 0x801D0860
BANK_AH_SIZE = 0xE80

EXPECTED_RECORD_START = {
    DRAGOON: 0x801881D4,
    KNIGHT_OF_DANIKA: 0x80189BFC,
    HIDDEN_DRAGOON: 0x8018A814,
}

EXPECTED_FIELD_2E = {
    DRAGOON: 0x80188202,
    KNIGHT_OF_DANIKA: 0x80189C2A,
    HIDDEN_DRAGOON: 0x8018A842,
}


class OwnershipSide(Enum):
    ALLY = "ALLY"
    ENEMY = "ENEMY"
    UNKNOWN = "UNKNOWN"


def class_record(class_id: int) -> int:
    if not 0 <= class_id <= MAX_COMPLETE_CLASS_ID:
        raise ValueError(f"class id out of complete-record range: 0x{class_id:X}")
    return CLASS_RECORD_BASE + class_id * CLASS_STRIDE


def class_field(class_id: int, offset: int) -> int:
    if not 0 <= offset < CLASS_STRIDE:
        raise ValueError(f"class field offset outside record: 0x{offset:X}")
    return class_record(class_id) + offset


def bank_ah_rom_to_ram(rom_address: int) -> int:
    """Map a ROM address inside bank AH to its observed runtime RAM address."""
    offset = rom_address - BANK_AH_ROM_BASE
    if not 0 <= offset < BANK_AH_SIZE:
        raise ValueError(f"ROM address outside bank AH: 0x{rom_address:X}")
    return BANK_AH_RAM_BASE + offset


def derive_roster_slot(
    persistent_record_ptr: int | None,
    roster_base: int | None,
    roster_count: int | None = None,
) -> int | None:
    """Return a persistent-roster slot only when the pointer is exactly aligned.

    This deliberately does not classify ownership. A valid 0x38-stride slot is
    structural evidence; ownership becomes ALLY/ENEMY only after separate
    runtime evidence establishes which roster range the slot belongs to.
    """
    if persistent_record_ptr is None or roster_base is None:
        return None
    if persistent_record_ptr < roster_base:
        return None

    delta = persistent_record_ptr - roster_base
    if delta % PERSISTENT_ROSTER_STRIDE:
        return None

    slot = delta // PERSISTENT_ROSTER_STRIDE
    if roster_count is not None and not 0 <= slot < roster_count:
        return None
    return slot


def presentation_override_eligible(class_id: int, ownership: OwnershipSide) -> bool:
    """Fail closed: only a positively allied class 0x71 may use the override."""
    return class_id == KNIGHT_OF_DANIKA and ownership is OwnershipSide.ALLY


def presentation_source_class(class_id: int, ownership: OwnershipSide) -> int:
    """Select presentation source without changing the unit's identity class.

    The eventual runtime hook can use this decision to borrow Dragoon posture,
    animation and weapon presentation. It must still retain class 0x71 for the
    unit itself so Danika identity/palette-specific handling can remain intact.
    """
    if presentation_override_eligible(class_id, ownership):
        return DRAGOON
    return class_id


def run_self_tests() -> None:
    # True class-table geometry.
    assert len({DRAGOON, KNIGHT_OF_DANIKA, HIDDEN_DRAGOON}) == 3
    assert FIELD_2E_OFFSET == 0x2E
    assert ALIAS_KEY_OFFSET == 0x45
    assert FIELD_2E_BASE + 0x17 == ALIAS_KEY_BASE

    for class_id, expected in EXPECTED_RECORD_START.items():
        actual = class_record(class_id)
        assert actual == expected, (
            f"class 0x{class_id:02X}: expected true record 0x{expected:08X}, "
            f"got 0x{actual:08X}"
        )
        assert (actual - CLASS_RECORD_BASE) % CLASS_STRIDE == 0
        assert class_field(class_id, FIELD_2E_OFFSET) == EXPECTED_FIELD_2E[class_id]

    try:
        class_record(0xFF)
    except ValueError:
        pass
    else:
        raise AssertionError("0xFF must not be treated as a complete class record")

    # Bank AH mapping contracts.
    assert bank_ah_rom_to_ram(BANK_AH_ROM_BASE) == BANK_AH_RAM_BASE
    assert bank_ah_rom_to_ram(BANK_AH_ROM_BASE + BANK_AH_SIZE - 1) == (
        BANK_AH_RAM_BASE + BANK_AH_SIZE - 1
    )

    # Participant -> persistent roster bridge geometry.
    sample_base = 0x80100000
    assert derive_roster_slot(sample_base, sample_base) == 0
    assert derive_roster_slot(sample_base + 5 * PERSISTENT_ROSTER_STRIDE, sample_base) == 5
    assert derive_roster_slot(sample_base + 5 * PERSISTENT_ROSTER_STRIDE + 1, sample_base) is None
    assert derive_roster_slot(sample_base - PERSISTENT_ROSTER_STRIDE, sample_base) is None
    assert derive_roster_slot(sample_base + 3 * PERSISTENT_ROSTER_STRIDE, sample_base, 3) is None

    # Critical preservation rule: enemy and unknown class 0x71 are untouched.
    assert presentation_override_eligible(KNIGHT_OF_DANIKA, OwnershipSide.ALLY)
    assert not presentation_override_eligible(KNIGHT_OF_DANIKA, OwnershipSide.ENEMY)
    assert not presentation_override_eligible(KNIGHT_OF_DANIKA, OwnershipSide.UNKNOWN)
    assert not presentation_override_eligible(DRAGOON, OwnershipSide.ALLY)

    assert presentation_source_class(KNIGHT_OF_DANIKA, OwnershipSide.ALLY) == DRAGOON
    assert presentation_source_class(KNIGHT_OF_DANIKA, OwnershipSide.ENEMY) == KNIGHT_OF_DANIKA
    assert presentation_source_class(KNIGHT_OF_DANIKA, OwnershipSide.UNKNOWN) == KNIGHT_OF_DANIKA
    assert presentation_source_class(DRAGOON, OwnershipSide.ALLY) == DRAGOON


def main() -> int:
    run_self_tests()

    print("Knight of Danika restoration contracts: PASS")
    print(f"True record base:              0x{CLASS_RECORD_BASE:08X}")
    print(f"Field +0x2E base:              0x{FIELD_2E_BASE:08X}")
    print(f"Alias/key +0x45 base:          0x{ALIAS_KEY_BASE:08X}")
    print(f"Dragoon 0x14 record:           0x{class_record(DRAGOON):08X}")
    print(f"Knight of Danika 0x71 record: 0x{class_record(KNIGHT_OF_DANIKA):08X}")
    print(f"Hidden Dragoon 0x9C record:    0x{class_record(HIDDEN_DRAGOON):08X}")
    print(f"Persistent roster stride:      0x{PERSISTENT_ROSTER_STRIDE:X}")
    print(f"Battle visual selector offset: +0x{BATTLE_VISUAL_SELECTOR_OFFSET:02X}")
    print(
        "Bank AH mapping:                "
        f"ROM 0x{BANK_AH_ROM_BASE:06X} -> RAM 0x{BANK_AH_RAM_BASE:08X}, "
        f"size 0x{BANK_AH_SIZE:X}"
    )
    print("Override policy: class 0x71 + proven ALLY only -> presentation source 0x14")
    print("Enemy/UNKNOWN class 0x71: original path preserved (fail closed).")
    print("NOTE: visual selector +0x00 is presentation evidence, NOT ownership proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
