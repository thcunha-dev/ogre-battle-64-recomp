#!/usr/bin/env python3
"""Host-side invariants for the Universal Item Randomizer mapping.

This mirrors the tiny integer mixer/xorshift/Sattolo code used by the MIPS mod.
It is deliberately ROM-independent, so GitHub Actions can prove the properties
we rely on for save/restart determinism without shipping game data.
"""

from __future__ import annotations

from pathlib import Path

MASK = 0xFFFFFFFF
EQUIP_SALT = 0x45515549
CONSUMABLE_SALT = 0x434F4E53
KEY_SALT = 0x4B455953


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


def cycle(seed: int, sources: list[int], salt: int) -> dict[int, int]:
    targets = list(sources)
    if len(targets) > 1:
        state = mix32(u32(seed ^ salt ^ u32(len(targets) * 0x9E3779B9)))
        if state == 0:
            state = 0xA341316C
        # Exact C loop: i=count-1 .. 1 and j in [0, i-1].
        for i in range(len(targets) - 1, 0, -1):
            state = rng_next(state)
            j = state % i
            targets[i], targets[j] = targets[j], targets[i]
    return dict(zip(sources, targets, strict=True))


def assert_cycle_properties(seed: int, size: int, salt: int) -> None:
    src = list(range(1, size + 1))
    a = cycle(seed, src, salt)
    b = cycle(seed, src, salt)
    assert a == b, (seed, size, "same seed was not deterministic")
    assert set(a) == set(src)
    assert set(a.values()) == set(src), (seed, size, "mapping was not bijective")
    if size > 1:
        assert all(k != v for k, v in a.items()), (seed, size, "fixed point")


def assert_sources_use_shared_constants(repo: Path) -> None:
    files = {
        "central": repo / "mods/universal-item-randomizer/src/universal_item_randomizer.c",
        "post_battle": repo / "mods/universal-item-randomizer/src/post_battle_add.c",
        "shop": repo / "mods/universal-item-randomizer/src/shop_stock.c",
    }
    texts = {name: path.read_text() for name, path in files.items()}

    # Equipment can arrive through all three paths and therefore must use the
    # same deterministic cycle salt and mixer constants everywhere.
    for name, text in texts.items():
        for token in (
            "0x45515549u",
            "0x7FEB352Du",
            "0x846CA68Bu",
            "0x9E3779B9u",
            "0xA341316Cu",
        ):
            assert token in text, f"{name}: missing shared mapping constant {token}"

    # Only the central and shop paths need consumable/key pools.
    for name in ("central", "shop"):
        text = texts[name]
        assert "0x434F4E53u" in text, f"{name}: wrong/missing consumable salt"
        assert "0x4B455953u" in text, f"{name}: wrong/missing key-item salt"


def main() -> int:
    for seed in (1, 2, 123456, 654321, 0xFFFFFFFF, 0xA5A5A5A5):
        for size in (1, 2, 3, 7, 15, 40, 64, 128, 277):
            assert_cycle_properties(seed, size, EQUIP_SALT)
        for size in (1, 2, 7, 15, 40):
            assert_cycle_properties(seed, size, CONSUMABLE_SALT)
            assert_cycle_properties(seed, size, KEY_SALT)

    assert_sources_use_shared_constants(Path(__file__).resolve().parents[1])
    print("universal randomizer mapping invariants: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
