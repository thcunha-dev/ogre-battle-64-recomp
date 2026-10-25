#!/usr/bin/env python3
"""Static contracts for the Playable Knight of Danika restoration project.

The full class record begins at D_80187C34 with stride 0x48.  D_80187C62,
previously used as the record origin during early research, is actually the
record+0x2E field anchor used by a family of class accessors.  Keep both address
sets explicit so future reverse engineering cannot silently regress to the
misaligned model.
"""

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


def class_record(class_id: int) -> int:
    if not 0 <= class_id <= MAX_COMPLETE_CLASS_ID:
        raise ValueError(f"class id out of complete-record range: 0x{class_id:X}")
    return CLASS_RECORD_BASE + class_id * CLASS_STRIDE


def class_field(class_id: int, offset: int) -> int:
    if not 0 <= offset < CLASS_STRIDE:
        raise ValueError(f"class field offset outside record: 0x{offset:X}")
    return class_record(class_id) + offset


def main() -> int:
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

    print("Knight of Danika class-table contracts: PASS")
    print(f"True record base:              0x{CLASS_RECORD_BASE:08X}")
    print(f"Field +0x2E base:              0x{FIELD_2E_BASE:08X}")
    print(f"Alias/key +0x45 base:          0x{ALIAS_KEY_BASE:08X}")
    print(f"Dragoon 0x14 record:           0x{class_record(DRAGOON):08X}")
    print(f"Knight of Danika 0x71 record: 0x{class_record(KNIGHT_OF_DANIKA):08X}")
    print(f"Hidden Dragoon 0x9C record:    0x{class_record(HIDDEN_DRAGOON):08X}")
    print("NOTE: class records and field anchors are metadata, NOT sprite pointers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
