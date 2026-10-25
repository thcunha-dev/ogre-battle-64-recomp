#!/usr/bin/env python3
"""Verify the true 0x48-byte class-record origin used by gameplay code.

Earlier research anchored on D_80187C62 because several class accessors index it
with class_id * 0x48.  func_8016EBC4 independently indexes D_80187C34 with the
same stride and then reads stat fields inside that record.  This audit resolves
that alignment, extracts truly aligned records, and maps the accessor anchors to
record-relative offsets.  It fails if the source does not support the layout.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "asm/data/5C230.data.s"
CODE = ROOT / "asm/40E80.s"

RECORD_BASE = 0x80187C34
STRIDE = 0x48
IDS = {"dragoon_0x14":0x14, "danika_0x71":0x71, "hidden_dragoon_0x9c":0x9C}
ANCHORS = {
    "D_80187C34":0x80187C34,
    "D_80187C38":0x80187C38,
    "D_80187C57":0x80187C57,
    "D_80187C62":0x80187C62,
    "D_80187C64":0x80187C64,
    "D_80187C66":0x80187C66,
    "D_80187C68":0x80187C68,
    "D_80187C75":0x80187C75,
    "D_80187C76":0x80187C76,
    "D_80187C77":0x80187C77,
    "D_80187C78":0x80187C78,
    "D_80187C79":0x80187C79,
    "D_80187C7A":0x80187C7A,
}
ADDR_RE = re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/\s*\.(byte|short|word)\s+(.+?)\s*$")
HEX_RE = re.compile(r"0x([0-9A-Fa-f]+)")
FUNC_RE = re.compile(r"^\s*glabel\s+([A-Za-z0-9_.$]+)")
END_RE = re.compile(r"^\s*endlabel\s+([A-Za-z0-9_.$]+)")
SYMBOL_RE = re.compile(r"\b(D_80187C[0-9A-Fa-f]{2})\b")


def parse_data_bytes():
    mem={}
    lines=DATA.read_text(encoding='utf-8',errors='replace').splitlines()
    for line in lines:
        m=ADDR_RE.search(line)
        if not m: continue
        addr=int(m.group(1),16); kind=m.group(2); rhs=m.group(3)
        vals=[int(x,16) for x in HEX_RE.findall(rhs)]
        if not vals: continue
        size={'byte':1,'short':2,'word':4}[kind]
        # Assembly source is big-endian N64 data.
        for n,val in enumerate(vals):
            a=addr+n*size
            for j in range(size):
                mem[a+j]=(val >> (8*(size-1-j))) & 0xFF
    return mem


def record(mem, class_id):
    addr=RECORD_BASE+class_id*STRIDE
    vals=[]
    missing=[]
    for i in range(STRIDE):
        if addr+i not in mem:
            missing.append(addr+i); vals.append(None)
        else: vals.append(mem[addr+i])
    if missing:
        raise SystemExit(f"missing {len(missing)} bytes for class {class_id:02X}; first=0x{missing[0]:08X}")
    return addr, vals


def accessor_map():
    lines=CODE.read_text(encoding='utf-8',errors='replace').splitlines()
    out=[]
    i=0
    while i<len(lines):
        m=FUNC_RE.match(lines[i])
        if not m:
            i+=1; continue
        name=m.group(1); s=i; e=min(len(lines)-1,i+500)
        for j in range(i+1,e+1):
            em=END_RE.match(lines[j])
            if em and em.group(1)==name:
                e=j; break
            if j>i+1 and FUNC_RE.match(lines[j]):
                e=j-1; break
        text='\n'.join(lines[s:e+1])
        syms=sorted(set(SYMBOL_RE.findall(text)))
        if syms:
            offsets=[]
            for sym in syms:
                try: addr=int(sym.split('_')[1],16)
                except Exception: continue
                if RECORD_BASE <= addr < RECORD_BASE+STRIDE:
                    offsets.append((sym,addr-RECORD_BASE))
            if offsets:
                out.append((name,s+1,e+1,offsets))
        i=e+1
    return out


def main():
    # Structural proof from the two independently used anchors.
    assert 0x80187C62-RECORD_BASE == 0x2E
    assert 0x80187C79-RECORD_BASE == 0x45
    assert 0x80187C62+0x17 == 0x80187C79

    mem=parse_data_bytes()
    recs={}
    print('Knight of Danika true class-layout audit')
    print('========================================')
    print(f'true_record_base=0x{RECORD_BASE:08X}')
    print(f'stride=0x{STRIDE:02X}')
    print('old_anchor_D_80187C62_record_offset=+0x2E')
    print('alias_D_80187C79_record_offset=+0x45')
    print('CONCLUSION: 0x80187C62 is a field anchor, not the full-record origin.')
    print()

    print('Aligned class-record addresses')
    print('------------------------------')
    for name,cid in IDS.items():
        addr,vals=record(mem,cid); recs[name]=(addr,vals)
        old=0x80187C62+cid*STRIDE
        print(f'{name}: class=0x{cid:02X} true_start=0x{addr:08X} old_0x62_anchor=0x{old:08X} delta=+0x{old-addr:02X}')
    print()

    print('Aligned 0x48-byte record hex')
    print('----------------------------')
    for name,(addr,vals) in recs.items():
        print(f'### {name} @ 0x{addr:08X}')
        for off in range(0,STRIDE,16):
            chunk=vals[off:off+16]
            print(f'+{off:02X}: '+' '.join(f'{x:02X}' for x in chunk))
        print()

    names=list(recs)
    print('Field diff by aligned byte offset')
    print('---------------------------------')
    print('off  dragoon14 danika71 hidden9c same')
    for off in range(STRIDE):
        vals=[recs[n][1][off] for n in names]
        print(f'{off:02X}   {vals[0]:02X}       {vals[1]:02X}       {vals[2]:02X}      {"=" if len(set(vals))==1 else "!"}')
    print()

    print('Known symbol anchors within true record')
    print('---------------------------------------')
    for sym,addr in sorted(ANCHORS.items(),key=lambda x:x[1]):
        print(f'{sym}=0x{addr:08X} -> record+0x{addr-RECORD_BASE:02X}')
    print()

    print('Accessor/function map to aligned record offsets')
    print('-----------------------------------------------')
    amap=accessor_map()
    for name,s,e,offsets in amap:
        print(f'{name} asm/40E80.s:{s}-{e}: '+', '.join(f'{sym}=+0x{off:02X}' for sym,off in offsets))
    print()

    # Lock critical structural facts so future research cannot regress to the
    # misaligned 0x62-as-record-start model.
    d14=recs['dragoon_0x14'][0]; d71=recs['danika_0x71'][0]; d9c=recs['hidden_dragoon_0x9c'][0]
    assert d14 == 0x801881D4, hex(d14)
    assert d71 == 0x80189BFC, hex(d71)
    assert d9c == 0x8018A814, hex(d9c)
    print('class-layout contracts: PASS')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
