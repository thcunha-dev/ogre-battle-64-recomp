#!/usr/bin/env python3
"""Reverse-engineering probe for the playable Knight of Danika restoration.

Evidence only: this script never patches graphics. It locates class-table accessors,
traces their callers, extracts the complete 0x48-byte records for Dragoon 0x14,
Knight of Danika 0x71 and hidden Dragoon 0x9C, and summarizes the candidate asset
selection routine that consumes the expanded class fields.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CLASS_BASE = 0x80187C62
CLASS_STRIDE = 0x48
ANCHORS = {
    "class_table_base": CLASS_BASE,
    "dragoon_0x14": CLASS_BASE + 0x14 * CLASS_STRIDE,
    "danika_0x71": CLASS_BASE + 0x71 * CLASS_STRIDE,
    "hidden_dragoon_0x9c": CLASS_BASE + 0x9C * CLASS_STRIDE,
}
TARGET_RECORDS = {k: v for k, v in ANCHORS.items() if k != "class_table_base"}
ACCESSORS = (
    "func_8016DFA8", "func_8016DFFC", "func_8016E050", "func_8016E0A4",
    "func_8016E0F8", "func_8016E14C", "func_8016E52C",
)
FOCUS_FUNCTION = "func_8017FC48"
TEXT_ROOTS = ("asm", "config", "include", "mods", "patches")
TEXT_SUFFIXES = {".s", ".S", ".c", ".h", ".toml", ".json", ".yaml", ".yml", ".txt", ".md"}
MAX_CONTEXT = 5
FUNCTION_CONTEXT_BEFORE = 35
FUNCTION_CONTEXT_AFTER = 55
CALL_CONTEXT_BEFORE = 18
CALL_CONTEXT_AFTER = 24


@dataclass(frozen=True)
class Hit:
    kind: str
    anchor: str
    path: str
    line: int
    text: str


def iter_text_files(root: Path) -> Iterable[Path]:
    for rel in TEXT_ROOTS:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                yield path


def address_spellings(addr: int) -> set[str]:
    return {f"0x{addr:08x}", f"0x{addr:08X}", f"{addr:08x}", f"{addr:08X}", f"D_{addr:08X}", f"D_{addr:08x}"}


def mips_halves(addr: int) -> tuple[set[int], int]:
    return {(addr >> 16) & 0xFFFF, ((addr + 0x8000) >> 16) & 0xFFFF}, addr & 0xFFFF


def parse_imm(line: str) -> list[int]:
    vals: list[int] = []
    for token in re.findall(r"(?<![\w])(?:0x[0-9A-Fa-f]+|\$[0-9A-Fa-f]+|[-+]?\d+)(?![\w])", line):
        try:
            vals.append((int(token[1:], 16) if token.startswith("$") else int(token, 0)) & 0xFFFF)
        except ValueError:
            pass
    return vals


def scan_file(root: Path, path: Path) -> list[Hit]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rel = path.relative_to(root).as_posix()
    hits: list[Hit] = []
    for idx, line in enumerate(lines):
        low = line.lower()
        for name, addr in ANCHORS.items():
            if any(spelling.lower() in low for spelling in address_spellings(addr)):
                hits.append(Hit("direct", name, rel, idx + 1, line.strip()))
    for name, addr in ANCHORS.items():
        his, lo = mips_halves(addr)
        for idx, line in enumerate(lines):
            if "lui" not in line.lower() or not any(imm in his for imm in parse_imm(line)):
                continue
            for j in range(idx + 1, min(len(lines), idx + 1 + MAX_CONTEXT)):
                next_low = lines[j].lower()
                if any(op in next_low for op in ("addiu", "addi", "ori", "daddiu")) and lo in parse_imm(lines[j]):
                    hits.append(Hit("mips-hi-lo", name, rel, idx + 1, f"{line.strip()}  ||  {lines[j].strip()}"))
    stride_pat = re.compile(r"(?i)(?:,|\s)(?:0x48|\$48|72)(?:\s|$)")
    for idx, line in enumerate(lines):
        if stride_pat.search(line) and any(op in line.lower() for op in ("mult", "mul", "add", "sll", "li", "ori", "addiu")):
            hits.append(Hit("stride-0x48", "class_stride", rel, idx + 1, line.strip()))
    return hits


def nearest_function(lines: list[str], one_based_line: int) -> tuple[int, str]:
    idx = max(0, one_based_line - 1)
    for j in range(idx, max(-1, idx - 1200), -1):
        m = re.match(r"\s*(?:glabel|dlabel|nonmatching)\s+([A-Za-z0-9_.$]+)", lines[j])
        if m:
            return j, m.group(1)
    return max(0, idx - FUNCTION_CONTEXT_BEFORE), "<unknown>"


def bounded_context(lines: list[str], hit_idx: int, before: int, after: int, floor: int = 0) -> list[str]:
    start = max(floor, hit_idx - before)
    end = min(len(lines), hit_idx + after + 1)
    return [f"{'>>>' if i == hit_idx else '   '} {i + 1:6d}: {lines[i]}" for i in range(start, end)]


def executable_contexts(root: Path, direct: list[Hit]) -> list[str]:
    blocks: list[str] = []
    seen: set[tuple[str, str]] = set()
    for hit in direct:
        if not hit.path.startswith("asm/") or "/data/" in hit.path:
            continue
        path = root / hit.path
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        fn_start, fn_name = nearest_function(lines, hit.line)
        key = (hit.path, fn_name)
        if key in seen:
            continue
        seen.add(key)
        blocks.append(f"### {hit.path}:{hit.line} function={fn_name}")
        blocks.extend(bounded_context(lines, hit.line - 1, FUNCTION_CONTEXT_BEFORE, FUNCTION_CONTEXT_AFTER, fn_start))
        blocks.append("")
    return blocks


def caller_contexts(root: Path) -> tuple[list[str], dict[str, int]]:
    blocks: list[str] = []
    counts = {symbol: 0 for symbol in ACCESSORS}
    call_re = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
    for path in sorted((root / "asm").rglob("*.s")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rel = path.relative_to(root).as_posix()
        for idx, line in enumerate(lines):
            m = call_re.search(line)
            if not m or m.group(1) not in counts:
                continue
            symbol = m.group(1)
            counts[symbol] += 1
            fn_start, fn_name = nearest_function(lines, idx + 1)
            blocks.append(f"### caller={fn_name} -> {symbol} at {rel}:{idx + 1}")
            blocks.extend(bounded_context(lines, idx, CALL_CONTEXT_BEFORE, CALL_CONTEXT_AFTER, fn_start))
            blocks.append("")
    return blocks, counts


RAM_COMMENT_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s+\*/\s*(.*)$")
DIRECTIVE_RE = re.compile(r"\.(byte|short|half|word)\s+(.+)$", re.IGNORECASE)


def directive_width(kind: str) -> int:
    return {"byte": 1, "short": 2, "half": 2, "word": 4}[kind.lower()]


def parse_int_token(token: str) -> int | None:
    token = token.strip().split("#", 1)[0].strip()
    try:
        return int(token, 0)
    except ValueError:
        return None


def extract_record_bytes(data_lines: list[str], start_addr: int) -> tuple[dict[int, int], list[str]]:
    end_addr = start_addr + CLASS_STRIDE
    out: dict[int, int] = {}
    source: list[str] = []
    for line in data_lines:
        m = RAM_COMMENT_RE.search(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        tail = m.group(2).strip()
        if not (start_addr <= addr < end_addr):
            continue
        source.append(line.strip())
        dm = DIRECTIVE_RE.search(tail)
        if not dm:
            continue
        width = directive_width(dm.group(1))
        cursor = addr
        for raw in dm.group(2).split(","):
            value = parse_int_token(raw)
            if value is None:
                cursor += width
                continue
            masked = value & ((1 << (width * 8)) - 1)
            for shift in range((width - 1) * 8, -1, -8):
                if start_addr <= cursor < end_addr:
                    out[cursor - start_addr] = (masked >> shift) & 0xFF
                cursor += 1
    return out, source


def class_record_report(root: Path) -> list[str]:
    data_path = root / "asm/data/5C230.data.s"
    if not data_path.exists():
        return ["class-record source not found: asm/data/5C230.data.s", ""]
    lines = data_path.read_text(encoding="utf-8", errors="replace").splitlines()
    parsed: dict[str, dict[int, int]] = {}
    sources: dict[str, list[str]] = {}
    for name, addr in TARGET_RECORDS.items():
        parsed[name], sources[name] = extract_record_bytes(lines, addr)
    names = list(TARGET_RECORDS)
    out = ["Class-record byte coverage", "--------------------------"]
    for name, addr in TARGET_RECORDS.items():
        out.append(f"{name}: addr=0x{addr:08X} parsed_bytes={len(parsed[name])}/{CLASS_STRIDE}")
    out += ["", "Field-by-field byte diff (0x00..0x47)", "--------------------------------------", "off  dragoon14 danika71 hidden9c same"]
    for off in range(CLASS_STRIDE):
        vals = [parsed[name].get(off) for name in names]
        fmt = ["??" if v is None else f"{v:02X}" for v in vals]
        same = "=" if all(v is not None for v in vals) and len(set(vals)) == 1 else "!"
        out.append(f"{off:02X}   {fmt[0]:>2}       {fmt[1]:>2}       {fmt[2]:>2}      {same}")
    out += ["", "16-bit aligned view", "-------------------", "off  dragoon14 danika71 hidden9c same"]
    for off in range(0, CLASS_STRIDE, 2):
        vals16: list[int | None] = []
        for name in names:
            b0, b1 = parsed[name].get(off), parsed[name].get(off + 1)
            vals16.append(None if b0 is None or b1 is None else (b0 << 8) | b1)
        fmt = ["????" if v is None else f"{v:04X}" for v in vals16]
        same = "=" if all(v is not None for v in vals16) and len(set(vals16)) == 1 else "!"
        out.append(f"{off:02X}   {fmt[0]}     {fmt[1]}     {fmt[2]}    {same}")
    out += ["", "Raw source lines per target record", "----------------------------------"]
    for name in names:
        out.append(f"### {name}")
        out.extend(sources[name] or ["(none)"])
        out.append("")
    return out


def focus_function_report(root: Path) -> list[str]:
    """Summarize func_8017FC48 without assuming what its ROM-like constants mean."""
    path = root / "asm/40E80.s"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(rf"\s*glabel\s+{re.escape(FOCUS_FUNCTION)}\b", line)), None)
    if start is None:
        return [f"{FOCUS_FUNCTION}: not found", ""]
    end = next((i for i in range(start + 1, len(lines)) if re.match(rf"\s*endlabel\s+{re.escape(FOCUS_FUNCTION)}\b", lines[i])), len(lines) - 1)
    body = lines[start:end + 1]
    call_re = re.compile(r"\bjal\s+([A-Za-z0-9_.$]+)")
    calls: dict[str, list[int]] = {}
    constants: list[tuple[int, str]] = []
    global_refs: list[tuple[int, str]] = []
    for rel_idx, line in enumerate(body):
        absolute_line = start + rel_idx + 1
        m = call_re.search(line)
        if m:
            calls.setdefault(m.group(1), []).append(absolute_line)
        if re.search(r"0x1DE[0-9A-Fa-f]{3,5}", line):
            constants.append((absolute_line, line.strip()))
        if re.search(r"D_8019[0-9A-Fa-f]{4}", line):
            global_refs.append((absolute_line, line.strip()))
    out = [
        f"Focused candidate routine: {FOCUS_FUNCTION}",
        "------------------------------------------",
        f"source=asm/40E80.s:{start + 1}-{end + 1}",
        f"instructions_or_labels={len(body)}",
        f"unique_jal_targets={len(calls)}",
        f"rom_like_0x1DE_constants={len(constants)}",
        f"D_8019_global_refs={len(global_refs)}",
        "",
        "Call targets:",
    ]
    for target, line_numbers in sorted(calls.items()):
        out.append(f"{target}: count={len(line_numbers)} lines={','.join(map(str, line_numbers))}")
    out += ["", "0x1DE... constant materializations:"]
    out.extend(f"line {ln}: {text}" for ln, text in constants)
    out += ["", "D_8019... state references:"]
    out.extend(f"line {ln}: {text}" for ln, text in global_refs[:120])
    if len(global_refs) > 120:
        out.append(f"... {len(global_refs) - 120} additional global refs omitted")
    out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output", type=Path, default=Path("danika-battle-lookup-report.txt"))
    args = ap.parse_args()
    root = args.root.resolve()
    files = sorted(set(iter_text_files(root)))
    hits: list[Hit] = []
    for path in files:
        hits.extend(scan_file(root, path))
    direct = [h for h in hits if h.kind == "direct"]
    hilo = [h for h in hits if h.kind == "mips-hi-lo"]
    stride = [h for h in hits if h.kind == "stride-0x48"]
    callers, call_counts = caller_contexts(root)
    out: list[str] = [
        "Knight of Danika battle-lookup reverse-engineering probe",
        "========================================================",
        f"files_scanned={len(files)}", f"direct_anchor_hits={len(direct)}",
        f"mips_hi_lo_hits={len(hilo)}", f"stride_0x48_hits={len(stride)}", "",
    ]
    for name, addr in ANCHORS.items():
        out.append(f"{name}=0x{addr:08X}")
    out.append("")
    def section(title: str, rows: list[Hit], cap: int = 250) -> None:
        out.extend((title, "-" * len(title)))
        if not rows:
            out.append("(none)")
        else:
            for hit in rows[:cap]:
                out.append(f"{hit.anchor}\t{hit.path}:{hit.line}\t{hit.text}")
            if len(rows) > cap:
                out.append(f"... {len(rows) - cap} additional hits omitted")
        out.append("")
    section("Direct anchor references", direct)
    section("MIPS split-address candidates", hilo)
    section("0x48 stride candidates (triage only)", stride)
    out.extend(("Accessor caller counts", "----------------------"))
    for symbol in ACCESSORS:
        out.append(f"{symbol}={call_counts[symbol]}")
    out.append("")
    out.extend(class_record_report(root))
    out.extend(focus_function_report(root))
    contexts = executable_contexts(root, direct)
    out.extend(("Executable direct-reference contexts", "------------------------------------"))
    out.extend(contexts or ["(none)", ""])
    out.extend(("Accessor caller contexts", "------------------------"))
    out.extend(callers or ["(none)", ""])
    out.append("INTERPRETATION: prove which class fields and caller branches feed battle-side asset selection before applying any graphics override. Unknown or unrelated paths remain vanilla.")
    text = "\n".join(out) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
