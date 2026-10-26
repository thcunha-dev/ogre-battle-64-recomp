#!/usr/bin/env python3
"""Fail-closed ownership analysis for Knight of Danika battle captures.

The operator labels known participant indices from visible gameplay with
--ally-participant and --enemy-participant. The tool checks two independent
families of evidence:

1. persistent-roster index separation;
2. full 0xF8 participant payload bytes emitted as DANIKA_PART_RAW.

For raw payloads it reports byte offsets whose ally/enemy value sets are
non-overlapping and bit positions that are constant within each side and
opposite between sides. These are candidates only: reproduction in another
battle is required before any offset/bit is promoted to ownership semantics.

The tool never guesses ownership for an unlabeled participant and never turns a
capture-local correlation into permission to patch.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

DANIKA_CLASS_ID = 0x71
DRAGOON_CLASS_ID = 0x14
PERSISTENT_ROSTER_STRIDE = 0x38
PARTICIPANT_SIZE = 0xF8
KNOWN_DYNAMIC_OR_IDENTITY_OFFSETS = {0x31, 0x32, 0xF6}

PART_RE = re.compile(
    r"\b(?P<kind>DANIKA_PART(?:_SNAPSHOT)?)\s+"
    r"i=(?P<i>[0-9A-Fa-f]+)\s+roster=(?P<roster>[0-9A-Fa-f]+)\s+"
    r"rclass=(?P<rclass>[0-9A-Fa-f]+)\s+lvl=(?P<lvl>[0-9A-Fa-f]+)\s+"
    r"exp=(?P<exp>[0-9A-Fa-f]+)\s+head=(?P<head>[0-9A-Fa-f]+)\s+"
    r"tail=(?P<tail>[0-9A-Fa-f]+)"
)
RAW_RE = re.compile(
    r"\bDANIKA_PART_RAW\s+i=(?P<i>[0-9A-Fa-f]+)\s+"
    r"off=(?P<off>[0-9A-Fa-f]+)\s+bytes=(?P<bytes>[0-9A-Fa-f]+)"
)


@dataclass(frozen=True)
class Participant:
    index: int
    roster: int
    class_id: int
    level: int
    exp: int
    head: str
    tail: str


def parse_hex(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError:
        try:
            return int(value, 16)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid integer/hex value: {value}") from exc


def parse_participants(text: str) -> list[Participant]:
    latest: dict[int, Participant] = {}
    for line in text.splitlines():
        match = PART_RE.search(line)
        if not match:
            continue
        p = Participant(
            index=int(match.group("i"), 16),
            roster=int(match.group("roster"), 16),
            class_id=int(match.group("rclass"), 16),
            level=int(match.group("lvl"), 16),
            exp=int(match.group("exp"), 16),
            head=match.group("head").upper(),
            tail=match.group("tail").upper(),
        )
        latest[p.index] = p
    return [latest[i] for i in sorted(latest)]


def parse_raw_payloads(text: str) -> dict[int, bytes]:
    """Reconstruct the latest observed raw payload chunks for each participant."""
    chunks: dict[int, dict[int, bytes]] = {}
    for line in text.splitlines():
        match = RAW_RE.search(line)
        if not match:
            continue
        index = int(match.group("i"), 16)
        offset = int(match.group("off"), 16)
        hex_bytes = match.group("bytes")
        if len(hex_bytes) % 2:
            continue
        data = bytes.fromhex(hex_bytes)
        if offset >= PARTICIPANT_SIZE or offset + len(data) > PARTICIPANT_SIZE:
            continue
        chunks.setdefault(index, {})[offset] = data

    payloads: dict[int, bytes] = {}
    for index, by_offset in chunks.items():
        buf = bytearray(PARTICIPANT_SIZE)
        covered = bytearray(PARTICIPANT_SIZE)
        for offset, data in by_offset.items():
            buf[offset : offset + len(data)] = data
            covered[offset : offset + len(data)] = b"\x01" * len(data)
        if all(covered):
            payloads[index] = bytes(buf)
    return payloads


def labeled_rows(
    participants: list[Participant], indices: set[int]
) -> list[Participant]:
    return [p for p in participants if p.index in indices]


def contiguous_range(values: set[int]) -> tuple[int, int] | None:
    if not values:
        return None
    lo, hi = min(values), max(values)
    if values != set(range(lo, hi + 1)):
        return None
    return lo, hi


def disjoint_roster_evidence(
    allies: list[Participant], enemies: list[Participant]
) -> tuple[bool, tuple[int, int] | None, tuple[int, int] | None]:
    ally_values = {p.roster for p in allies}
    enemy_values = {p.roster for p in enemies}
    ally_range = contiguous_range(ally_values)
    enemy_range = contiguous_range(enemy_values)
    clean = bool(
        ally_values
        and enemy_values
        and ally_values.isdisjoint(enemy_values)
        and ally_range is not None
        and enemy_range is not None
        and (ally_range[1] < enemy_range[0] or enemy_range[1] < ally_range[0])
    )
    return clean, ally_range, enemy_range


def byte_discriminators(
    payloads: dict[int, bytes],
    ally_indices: set[int],
    enemy_indices: set[int],
) -> list[tuple[int, set[int], set[int]]]:
    """Return offsets with disjoint ally/enemy byte-value sets."""
    if not ally_indices or not enemy_indices:
        return []
    if not ally_indices.issubset(payloads) or not enemy_indices.issubset(payloads):
        return []

    result = []
    for offset in range(PARTICIPANT_SIZE):
        if offset in KNOWN_DYNAMIC_OR_IDENTITY_OFFSETS:
            continue
        ally_values = {payloads[i][offset] for i in ally_indices}
        enemy_values = {payloads[i][offset] for i in enemy_indices}
        if ally_values.isdisjoint(enemy_values):
            result.append((offset, ally_values, enemy_values))
    return result


def bit_discriminators(
    payloads: dict[int, bytes],
    ally_indices: set[int],
    enemy_indices: set[int],
) -> list[tuple[int, int, int, int]]:
    """Return (offset, mask, ally_bit, enemy_bit) stable opposite side bits."""
    if not ally_indices or not enemy_indices:
        return []
    if not ally_indices.issubset(payloads) or not enemy_indices.issubset(payloads):
        return []

    result = []
    for offset in range(PARTICIPANT_SIZE):
        if offset in KNOWN_DYNAMIC_OR_IDENTITY_OFFSETS:
            continue
        for bit in range(8):
            mask = 1 << bit
            ally_bits = {(payloads[i][offset] & mask) != 0 for i in ally_indices}
            enemy_bits = {(payloads[i][offset] & mask) != 0 for i in enemy_indices}
            if len(ally_bits) == 1 and len(enemy_bits) == 1 and ally_bits != enemy_bits:
                result.append(
                    (offset, mask, 1 if True in ally_bits else 0, 1 if True in enemy_bits else 0)
                )
    return result


def ownership_for_index(
    index: int, ally_indices: set[int], enemy_indices: set[int]
) -> str:
    if index in ally_indices and index in enemy_indices:
        return "CONFLICT"
    if index in ally_indices:
        return "ALLY"
    if index in enemy_indices:
        return "ENEMY"
    return "UNKNOWN"


def override_eligible(class_id: int, ownership: str) -> bool:
    return class_id == DANIKA_CLASS_ID and ownership == "ALLY"


def fmt_range(value: tuple[int, int] | None) -> str:
    if value is None:
        return "<not-contiguous>"
    return f"0x{value[0]:02X}..0x{value[1]:02X}"


def fmt_values(values: set[int]) -> str:
    return ",".join(f"0x{x:02X}" for x in sorted(values))


def report(
    participants: list[Participant],
    ally_indices: set[int],
    enemy_indices: set[int],
    payloads: dict[int, bytes] | None = None,
) -> str:
    payloads = payloads or {}
    out = [
        "Knight of Danika ownership capture analysis",
        "===========================================",
        f"participants={len(participants)}",
        f"complete_raw_payloads={len(payloads)}",
        f"persistent_roster_stride=0x{PERSISTENT_ROSTER_STRIDE:X}",
        f"participant_size=0x{PARTICIPANT_SIZE:X}",
    ]

    conflicts = ally_indices & enemy_indices
    missing = (ally_indices | enemy_indices) - {p.index for p in participants}
    clean_ally_indices = ally_indices - conflicts
    clean_enemy_indices = enemy_indices - conflicts
    allies = labeled_rows(participants, clean_ally_indices)
    enemies = labeled_rows(participants, clean_enemy_indices)
    clean, ally_range, enemy_range = disjoint_roster_evidence(allies, enemies)
    raw_missing = (clean_ally_indices | clean_enemy_indices) - set(payloads)
    byte_candidates = byte_discriminators(payloads, clean_ally_indices, clean_enemy_indices)
    bit_candidates = bit_discriminators(payloads, clean_ally_indices, clean_enemy_indices)

    if conflicts:
        out.append("label_conflicts=" + ",".join(f"0x{x:02X}" for x in sorted(conflicts)))
    if missing:
        out.append("missing_labeled_indices=" + ",".join(f"0x{x:02X}" for x in sorted(missing)))
    if raw_missing:
        out.append("missing_raw_payloads=" + ",".join(f"0x{x:02X}" for x in sorted(raw_missing)))

    out += [
        f"labeled_allies={len(allies)} roster_range={fmt_range(ally_range)}",
        f"labeled_enemies={len(enemies)} roster_range={fmt_range(enemy_range)}",
        f"roster_ranges_cleanly_separable={'yes' if clean else 'no'}",
        f"raw_byte_candidates={len(byte_candidates)}",
        f"raw_bit_candidates={len(bit_candidates)}",
        "",
        "Participants",
        "------------",
    ]

    for p in participants:
        ownership = ownership_for_index(p.index, ally_indices, enemy_indices)
        eligible = override_eligible(p.class_id, ownership)
        label = "Dragoon" if p.class_id == DRAGOON_CLASS_ID else (
            "Knight of Danika" if p.class_id == DANIKA_CLASS_ID else "class"
        )
        out.append(
            f"i=0x{p.index:02X} ownership={ownership:<8} roster=0x{p.roster:02X} "
            f"class=0x{p.class_id:02X} {label} raw={'yes' if p.index in payloads else 'no'} "
            f"danika_override_eligible={'yes' if eligible else 'no'}"
        )

    out += ["", "Raw participant byte candidates", "-------------------------------"]
    if raw_missing:
        out.append("Raw comparison incomplete because one or more labeled payloads are missing.")
    elif not byte_candidates:
        out.append("No disjoint byte offsets established by these labels.")
    else:
        for offset, av, ev in sorted(
            byte_candidates,
            key=lambda row: (len(row[1]) + len(row[2]), row[0]),
        )[:64]:
            out.append(
                f"BYTE_CANDIDATE off=0x{offset:02X} ally={fmt_values(av)} enemy={fmt_values(ev)}"
            )

    out += ["", "Raw participant bit candidates", "------------------------------"]
    if raw_missing:
        out.append("Raw bit comparison incomplete because labeled payloads are missing.")
    elif not bit_candidates:
        out.append("No stable opposite side bits established by these labels.")
    else:
        for offset, mask, abit, ebit in bit_candidates[:64]:
            out.append(
                f"BIT_CANDIDATE off=0x{offset:02X} mask=0x{mask:02X} "
                f"ally={abit} enemy={ebit}"
            )

    out += ["", "Interpretation", "--------------"]
    if conflicts:
        out.append("FAIL: conflicting side labels exist. Ownership remains UNKNOWN for patching.")
    elif missing:
        out.append("FAIL: one or more labeled participants were absent from the capture.")
    elif len(allies) < 2 or len(enemies) < 2:
        out.append("INCOMPLETE: require at least two known allies and two known enemies.")
    else:
        if clean:
            out.append("EVIDENCE: this capture has clean, disjoint contiguous roster ranges.")
        else:
            out.append("Roster indices alone do not prove a clean side range in this capture.")
        if raw_missing:
            out.append("INCOMPLETE: obtain full DANIKA_PART_RAW payloads for every labeled unit.")
        elif byte_candidates or bit_candidates:
            out.append("EVIDENCE: raw participant side-discriminator candidates were found.")
            out.append("Reproduce the same offset/bit polarity in another battle before promotion.")
        else:
            out.append("No raw participant ownership candidate was established by this capture.")

    out.append(
        "Known level/EXP/roster-index offsets 0x31/0x32/0xF6 are excluded from raw candidates."
    )
    out.append(
        "Fail-closed rule remains: only class 0x71 + independently proven ALLY may borrow "
        "Dragoon 0x14 presentation."
    )
    return "\n".join(out) + "\n"


def self_test() -> None:
    sample = [
        Participant(0, 0, DRAGOON_CLASS_ID, 1, 0, "", ""),
        Participant(1, 1, 0x10, 1, 0, "", ""),
        Participant(2, 8, DANIKA_CLASS_ID, 1, 0, "", ""),
        Participant(3, 9, 0x11, 1, 0, "", ""),
    ]
    clean, arange, erange = disjoint_roster_evidence(sample[:2], sample[2:])
    assert clean
    assert arange == (0, 1)
    assert erange == (8, 9)
    assert override_eligible(DANIKA_CLASS_ID, "ALLY")
    assert not override_eligible(DANIKA_CLASS_ID, "ENEMY")
    assert not override_eligible(DANIKA_CLASS_ID, "UNKNOWN")
    assert not override_eligible(DRAGOON_CLASS_ID, "ALLY")

    payloads = {i: bytearray(PARTICIPANT_SIZE) for i in range(4)}
    payloads[0][0x40] = 0x80
    payloads[1][0x40] = 0x81
    payloads[2][0x40] = 0x00
    payloads[3][0x40] = 0x01
    frozen = {i: bytes(v) for i, v in payloads.items()}
    assert any(off == 0x40 for off, _, _ in byte_discriminators(frozen, {0, 1}, {2, 3}))
    assert (0x40, 0x80, 1, 0) in bit_discriminators(frozen, {0, 1}, {2, 3})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", nargs="?", type=Path)
    parser.add_argument(
        "--ally-participant", action="append", default=[], type=parse_hex, metavar="INDEX",
        help="known allied participant index from visible gameplay; repeatable",
    )
    parser.add_argument(
        "--enemy-participant", action="append", default=[], type=parse_hex, metavar="INDEX",
        help="known enemy participant index from visible gameplay; repeatable",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("Danika ownership analyzer self-test: PASS")
        if args.log is None:
            return 0

    if args.log is None:
        parser.error("log is required unless --self-test is used")

    text = args.log.read_text(encoding="utf-8", errors="replace")
    print(
        report(
            parse_participants(text),
            set(args.ally_participant),
            set(args.enemy_participant),
            parse_raw_payloads(text),
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
