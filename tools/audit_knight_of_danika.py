#!/usr/bin/env python3
"""Static contracts for the Playable Knight of Danika restoration project.

This deliberately validates only facts we have already established. It does not
pretend that class records are sprite pointers; graphics lookup discovery is a
separate reverse-engineering milestone.
"""

CLASS_BASE = 0x80187C62
CLASS_STRIDE = 0x48
MAX_COMPLETE_CLASS_ID = 0xFE

DRAGOON = 0x14
KNIGHT_OF_DANIKA = 0x71
HIDDEN_DRAGOON = 0x9C

EXPECTED = {
    DRAGOON: 0x80188202,
    KNIGHT_OF_DANIKA: 0x80189C2A,
    HIDDEN_DRAGOON: 0x8018A842,
}


def class_record(class_id: int) -> int:
    if not 0 <= class_id <= MAX_COMPLETE_CLASS_ID:
        raise ValueError(f"class id out of complete-record range: 0x{class_id:X}")
    return CLASS_BASE + class_id * CLASS_STRIDE


def main() -> int:
    assert len({DRAGOON, KNIGHT_OF_DANIKA, HIDDEN_DRAGOON}) == 3
    for class_id, expected in EXPECTED.items():
        actual = class_record(class_id)
        assert actual == expected, (
            f"class 0x{class_id:02X}: expected 0x{expected:08X}, got 0x{actual:08X}"
        )
        assert (actual - CLASS_BASE) % CLASS_STRIDE == 0

    try:
        class_record(0xFF)
    except ValueError:
        pass
    else:
        raise AssertionError("0xFF must not be treated as a complete class record")

    print("Knight of Danika class-table contracts: PASS")
    print(f"Dragoon 0x14 record:           0x{class_record(DRAGOON):08X}")
    print(f"Knight of Danika 0x71 record: 0x{class_record(KNIGHT_OF_DANIKA):08X}")
    print(f"Hidden Dragoon 0x9C record:    0x{class_record(HIDDEN_DRAGOON):08X}")
    print("NOTE: these addresses are class records, NOT sprite pointers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
