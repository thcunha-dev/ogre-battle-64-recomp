#!/usr/bin/env python3
"""Golden deterministic vectors for the Universal Item Randomizer mapper.

These values intentionally lock the public seed semantics. If the mixer, salts,
or Sattolo ordering change accidentally, CI must fail instead of silently making
old seeds produce different equipment mappings.
"""

MASK = 0xFFFFFFFF
EQUIP_SALT = 0x45515549


def u32(x: int) -> int:
    return x & MASK


def mix32(x: int) -> int:
    x = u32(x ^ (x >> 16))
    x = u32(x * 0x7FEB352D)
    x = u32(x ^ (x >> 15))
    x = u32(x * 0x846CA68B)
    x = u32(x ^ (x >> 16))
    return x


def rng_next(state: int) -> int:
    x = state
    x = u32(x ^ (x << 13))
    x = u32(x ^ (x >> 17))
    x = u32(x ^ (x << 5))
    return x


def equipment_map(seed: int) -> dict[int, int]:
    sources = list(range(1, 278))
    targets = list(sources)
    state = mix32(u32(seed ^ EQUIP_SALT ^ u32(len(targets) * 0x9E3779B9)))
    if state == 0:
        state = 0xA341316C
    for i in range(len(targets) - 1, 0, -1):
        state = rng_next(state)
        j = state % i
        targets[i], targets[j] = targets[j], targets[i]
    return dict(zip(sources, targets, strict=True))


def main() -> int:
    # TESTING.md uses seed 123456, so keep a compact set of exact vectors for it.
    expected_123456 = {
        1: 270,
        2: 239,
        3: 37,
        4: 115,
        5: 112,
        6: 125,
        7: 40,
        8: 186,
        10: 60,
        20: 138,
        50: 146,
        100: 189,
        150: 243,
        200: 223,
        250: 259,
        277: 245,
    }
    mapping = equipment_map(123456)
    for original, replacement in expected_123456.items():
        assert mapping[original] == replacement, (original, mapping[original], replacement)
        # Equipment item words preserve bit15 around the mapped low 15 bits.
        raw = 0x8000 | original
        mapped_raw = 0x8000 | mapping[original]
        assert raw & 0x8000
        assert mapped_raw == (0x8000 | replacement)

    # A second seed catches accidental hard-coding of one fixture.
    expected_12345 = {1: 95, 2: 30, 3: 179, 100: 185, 200: 162, 277: 253}
    mapping2 = equipment_map(12345)
    for original, replacement in expected_12345.items():
        assert mapping2[original] == replacement, (original, mapping2[original], replacement)

    assert all(k != v for k, v in mapping.items())
    assert len(set(mapping.values())) == 277
    print("universal randomizer golden seed vectors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
