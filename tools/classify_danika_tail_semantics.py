#!/usr/bin/env python3
"""Lock the proven semantics of the suspicious class-record tail fields.

The Dragoon/Danika comparison made +0x41..+0x44 look like plausible missing
presentation metadata because playable Dragoon 0x14 and hidden Dragoon 0x9C
share 02 06 05 11 while Danika 0x71 contains zeros.  Static dataflow now shows
that those bytes participate in class-transition selection instead.

This audit deliberately makes only narrow claims:
  * +0x41..+0x44 are candidate class IDs consumed by class-selection logic;
  * the selected result can be written to live-character +0x12 (class ID);
  * +0x45 participates in the already-known class alias/reference mechanism;
  * +0x46 is companion gameplay metadata and can be copied to character +0x1A;
  * none of these observations justify using the tail block as a sprite pointer.

Exact gameplay meaning of +0x46 remains intentionally unnamed.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-tail-semantics.txt"

TARGETS = ("func_8016EA54", "func_8016F13C", "func_8016D274")
FIELDS = {
    "+0x41": "D_80187C75",
    "+0x42": "D_80187C76",
    "+0x43": "D_80187C77",
    "+0x44": "D_80187C78",
    "+0x45": "D_80187C79",
    "+0x46": "D_80187C7A",
}
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
CALL_RE = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
GRAPHICS_HINTS = {
    "func_8009DAF4", "func_8009DBB8", "func_8009DD38",
    "func_801AD13C", "func_801AD368", "func_801AD6C4",
}


def parse_functions():
    funcs = {}
    for path in sorted(ASM_ROOT.rglob("*.s")):
        if "/data/" in path.as_posix():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        starts = {}
        for i, line in enumerate(lines):
            m = FUNC_RE.match(line)
            if m:
                starts[m.group(1)] = i
            e = END_RE.match(line)
            if e and e.group(1) in starts:
                name = e.group(1)
                a = starts[name]
                funcs[name] = (
                    path.relative_to(ROOT).as_posix(), a + 1, i + 1,
                    lines[a:i + 1],
                )
    return funcs


def calls(body):
    return [m.group(1) for line in body if (m := CALL_RE.search(line))]


def require(body: str, pattern: str, message: str):
    assert re.search(pattern, body, re.I | re.M | re.S), message


def main() -> int:
    funcs = parse_functions()
    missing = [name for name in TARGETS if name not in funcs]
    assert not missing, f"missing target functions: {missing}"

    ea = "\n".join(funcs["func_8016EA54"][3])
    f13 = "\n".join(funcs["func_8016F13C"][3])
    d274 = "\n".join(funcs["func_8016D274"][3])

    # +0x41..+0x44 are all consumed by the same class-choice helper.
    for off in ("+0x41", "+0x42", "+0x43", "+0x44"):
        assert FIELDS[off] in ea, f"{off} missing from func_8016EA54"

    # The live-character mutation path consumes the same candidate fields and
    # writes the chosen byte into character+0x12, the established class field.
    for off in ("+0x41", "+0x42", "+0x43", "+0x44"):
        assert FIELDS[off] in f13, f"{off} missing from func_8016F13C"
    require(f13, r"\bsb\s+\$[A-Za-z0-9]+,\s*0x12\(\$s1\)",
            "class write to live-character+0x12 missing")

    # +0x45 and +0x46 remain gameplay-side metadata. +0x46 has a dedicated
    # accessor and is also copied into live-character +0x1A by func_8016F13C.
    assert FIELDS["+0x45"] in f13, "+0x45 alias/reference missing from class mutation path"
    assert FIELDS["+0x46"] in f13, "+0x46 missing from class mutation path"
    assert FIELDS["+0x46"] in d274, "+0x46 dedicated accessor missing"
    require(f13, r"\bsb\s+\$[A-Za-z0-9]+,\s*0x1A\(\$s1\)",
            "+0x46 companion write to live-character+0x1A missing")

    # No direct known graphics/resource loader is called by the three functions
    # that establish these semantics. This is a narrow negative result, not a
    # claim that the fields can never influence rendering indirectly.
    direct_calls = {name: calls(funcs[name][3]) for name in TARGETS}
    direct_graphics = {
        name: sorted(set(cs) & GRAPHICS_HINTS) for name, cs in direct_calls.items()
    }
    assert not any(direct_graphics.values()), (
        f"unexpected direct graphics-loader adjacency: {direct_graphics}"
    )

    out = [
        "Knight of Danika class-tail semantic classification",
        "===================================================",
        "",
        "PROVEN",
        "------",
        "+0x41..+0x44 are consumed together as class-transition/selection candidates.",
        "The chosen class candidate reaches a store to live-character+0x12 (class ID).",
        "+0x45 participates in the class alias/reference path.",
        "+0x46 is companion gameplay metadata: it has its own accessor and reaches live-character+0x1A.",
        "The audited functions do not directly call the known graphics/resource loaders.",
        "",
        "CONSEQUENCE FOR PLAYABLE DANIKA",
        "-------------------------------",
        "Do NOT copy Dragoon bytes 02 06 05 11 into Danika +0x41..+0x44 as a sprite fix.",
        "Doing so would alter class-transition behavior rather than restore a rear battle sprite.",
        "Do NOT globally copy Dragoon +0x45/+0x46 either; they are gameplay-side metadata.",
        "The fighter visual/animation selector must be located outside this tail block.",
        "",
        "UNRESOLVED",
        "----------",
        "The exact human-readable meaning of +0x46 is not named yet.",
        "No claim is made that these fields can never affect rendering indirectly.",
        "",
    ]

    for name in TARGETS:
        rel, start, end, body = funcs[name]
        out += [f"## {name} {rel}:{start}-{end}"]
        out.append("calls=" + (",".join(direct_calls[name]) or "-"))
        for n, line in enumerate(body, start=start):
            if any(sym in line for sym in FIELDS.values()) or \
               re.search(r"\bsb\s+\$[A-Za-z0-9]+,\s*0x(?:12|1A)\(\$s1\)", line, re.I):
                out.append(f"{n}: {line}")
        out.append("")

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Danika class-tail semantics: PASS")
    print("classification=+41..+44 class-transition candidates; +45/+46 gameplay metadata")
    print("graphics_fix_candidate=REJECT tail block")
    print("report=" + OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
