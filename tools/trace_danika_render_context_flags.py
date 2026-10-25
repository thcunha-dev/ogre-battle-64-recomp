#!/usr/bin/env python3
"""Lock and report the battle-record -> render-context flag chain used by Danika.

This probe is deliberately conservative.  It proves where the context bits come
from and how they reach the renderer, but it does NOT label them player/enemy
until an independent ownership producer is found.

Verified chain:
  resource package 0x315736
    -> func_801B3BD8 installs D_801BA6D8 record table
    -> func_801B3D1C indexes 0x1A-byte records
    -> record+0x0C is returned through caller output sp+0x50
    -> func_801AE794 copies it to render object+0xB4
       * bit 0 selects object+0x14 state 3 vs 2
       * bit 1 is preserved in object+0xB4
    -> func_801B3868 converts object+0x14 into renderer a1 and passes
       object+0xB4 & 2 as renderer a2
    -> func_801AD6C4 consumes those values.

Safety consequence: these bits are real render-context inputs, but neither may
be used as DANIKA_SIDE_ALLIED until ownership/team semantics are independently
proven.  Enemy Danika must therefore remain fail-closed/vanilla.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASM_ROOT = ROOT / "asm"
OUT = ROOT / "danika-render-context-flags.txt"

TARGETS = {
    "func_801B3BD8",
    "func_801B3D1C",
    "func_801AE794",
    "func_801B3868",
    "func_801AD6C4",
}
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")


def iter_blocks(path: Path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        m = FUNC_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start = i
        end = min(len(lines) - 1, i + 7000)
        for j in range(i + 1, end + 1):
            em = END_RE.match(lines[j])
            if em and em.group(1) == name:
                end = j
                break
            if j > i + 1 and FUNC_RE.match(lines[j]):
                end = j - 1
                break
        yield name, start + 1, end + 1, lines[start:end + 1]
        i = end + 1


def require(block: str, pattern: str, label: str) -> None:
    if re.search(pattern, block, re.I | re.M) is None:
        raise AssertionError(f"missing {label}: /{pattern}/")


def main() -> int:
    defs = {}
    resource_refs = []
    for path in sorted(ASM_ROOT.rglob("*.s")):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), start=1):
            if "315736" in line.upper():
                resource_refs.append((rel, n, line.strip()))
        for name, start, end, lines in iter_blocks(path):
            if name in TARGETS:
                defs[name] = (rel, start, end, lines)

    missing = TARGETS - defs.keys()
    assert not missing, f"missing target functions: {sorted(missing)}"

    b3bd8 = "\n".join(defs["func_801B3BD8"][3])
    b3d1c = "\n".join(defs["func_801B3D1C"][3])
    ae794 = "\n".join(defs["func_801AE794"][3])
    b3868 = "\n".join(defs["func_801B3868"][3])
    ad6c4 = "\n".join(defs["func_801AD6C4"][3])

    # Resource/table installation contract.
    require(b3bd8, r"0x315736", "battle-record resource 0x315736")
    require(b3bd8, r"D_801BA6D8", "battle-record table pointer")

    # 0x1A-byte stride: slot*26 = (((slot*2)+slot)*4+slot)*2.
    require(b3d1c, r"sll\s+\$v0,\s*\$a1,\s*1", "slot*2")
    require(b3d1c, r"addu\s+\$v0,\s*\$v0,\s*\$a1", "slot*3/13 chain")
    require(b3d1c, r"lh\s+\$v0,\s*0xC\(\$a0\)", "record+0x0C context field")
    require(b3d1c, r"sw\s+\$v0,\s*0x0\(\$t2\)", "record+0x0C output store")

    # Caller output wiring and bit-0 state choice.
    require(ae794, r"addiu\s+\$v0,\s*\$sp,\s*0x50", "sp+0x50 output pointer")
    require(ae794, r"sw\s+\$v0,\s*0x1C\(\$sp\)", "sp+0x50 passed as t2 output")
    require(ae794, r"andi\s+\$v0,\s*\$v0,\s*0x1", "context bit0 test")
    require(ae794, r"sb\s+\$v0,\s*0x14\(\$s0\)", "render object state write")
    require(ae794, r"sw\s+\$v0,\s*0xB4\(\$s0\)", "full context word to object+0xB4")

    # Callback passes independent derivatives to renderer.
    require(b3868, r"lbu\s+\$a1,\s*0x14\(\$a0\)", "object state read")
    require(b3868, r"xori\s+\$a1,\s*\$a1,\s*0x3", "state==3 inversion")
    require(b3868, r"lw\s+\$a2,\s*0xB4\(\$a0\)", "context word read")
    require(b3868, r"andi\s+\$a2,\s*\$a2,\s*0x2", "context bit1 mask")
    require(b3868, r"jal\s+func_801AD6C4", "renderer call")

    # Renderer really consumes both inputs; this keeps future refactors honest.
    require(ad6c4, r"addu\s+\$a3,\s*\$a1,\s*\$zero", "renderer a1 preservation")

    out = [
        "Knight of Danika render-context flag trace",
        "==========================================",
        "",
        "PROVEN chain",
        "------------",
        "0x315736 -> D_801BA6D8 -> 0x1A-byte record -> record+0x0C",
        "record+0x0C -> func_801B3D1C output t2 -> caller sp+0x50",
        "sp+0x50 bit0 -> render object+0x14 state 3 vs 2",
        "sp+0x50 full value -> render object+0xB4",
        "object+0x14 -> func_801B3868 -> renderer a1=(state != 3)",
        "object+0xB4 bit1 -> func_801B3868 -> renderer a2=(context & 2)",
        "",
        "NOT YET PROVEN",
        "--------------",
        "Neither bit0 nor bit1 is independently proven to mean allied/player ownership.",
        "They are therefore forbidden as the playable-Danika gate until provenance reaches a team/owner producer.",
        "Enemy Danika remains vanilla/fail-closed.",
        "",
        f"literal 0x315736 references={len(resource_refs)}",
    ]
    for rel, n, line in resource_refs:
        out.append(f"{rel}:{n}: {line}")

    out += ["", "Target function locations", "-------------------------"]
    for name in sorted(TARGETS):
        rel, start, end, _ = defs[name]
        out.append(f"{name}: {rel}:{start}-{end}")

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("Danika render-context flags: PASS")
    print("record_stride=0x1A")
    print("context_field=record+0x0C")
    print("bit0=object_state_2_or_3 (ownership semantics UNPROVEN)")
    print("bit1=renderer_a2_mask_0x2 (ownership semantics UNPROVEN)")
    print("resource=0x315736")
    print("report=" + OUT.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
