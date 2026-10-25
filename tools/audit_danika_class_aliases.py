#!/usr/bin/env python3
"""Audit class record+0x45 across the complete class table.

The hidden Dragoon 0x9C carries +0x45 == 0x14, while playable Dragoon 0x14
and Knight of Danika 0x71 carry zero.  This tool determines whether +0x45
systematically aliases hidden/enemy records to another class and reports how
closely each source record matches its target.  It does not patch the field.
"""
from __future__ import annotations
import re
from pathlib import Path
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'asm/data/5C230.data.s'
BASE=0x80187C34
STRIDE=0x48
ALIAS_OFF=0x45
ADDR_RE=re.compile(r"/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/\s*\.(byte|short|word)\s+(.+?)\s*$")
HEX_RE=re.compile(r"0x([0-9A-Fa-f]+)")


def parse_mem():
    mem={}
    for line in DATA.read_text(encoding='utf-8',errors='replace').splitlines():
        m=ADDR_RE.search(line)
        if not m: continue
        addr=int(m.group(1),16); kind=m.group(2); vals=[int(x,16) for x in HEX_RE.findall(m.group(3))]
        size={'byte':1,'short':2,'word':4}[kind]
        for n,val in enumerate(vals):
            a=addr+n*size
            for j in range(size): mem[a+j]=(val>>(8*(size-1-j)))&0xff
    return mem


def get_record(mem,cid):
    a=BASE+cid*STRIDE
    vals=[mem.get(a+i) for i in range(STRIDE)]
    if any(v is None for v in vals): return None
    return vals


def diff(a,b):
    return [i for i,(x,y) in enumerate(zip(a,b)) if x!=y]


def main():
    mem=parse_mem()
    records={cid:r for cid in range(0x100) if (r:=get_record(mem,cid)) is not None}
    print('Knight of Danika class alias audit')
    print('==================================')
    print(f'complete_records={len(records)}')
    print(f'alias_offset=+0x{ALIAS_OFF:02X}')
    print()
    aliases=[]
    for cid,r in records.items():
        a=r[ALIAS_OFF]
        if a:
            aliases.append((cid,a))
    print(f'nonzero_aliases={len(aliases)}')
    print('source -> alias  diff_count  differing_offsets')
    for cid,a in aliases:
        target=records.get(a)
        if target is None:
            print(f'0x{cid:02X} -> 0x{a:02X}  target-missing')
            continue
        ds=diff(records[cid],target)
        # +0x45 is expected to differ when the source names its target.
        print(f'0x{cid:02X} -> 0x{a:02X}  {len(ds):3d}         '+','.join(f'{x:02X}' for x in ds))
    print()
    for cid in (0x14,0x71,0x9C):
        r=records[cid]
        print(f'class 0x{cid:02X}: +45=0x{r[0x45]:02X} +40=0x{r[0x40]:02X} +41=0x{r[0x41]:02X} +42=0x{r[0x42]:02X} +43=0x{r[0x43]:02X} +44=0x{r[0x44]:02X} +46=0x{r[0x46]:02X} +47=0x{r[0x47]:02X}')
    print()
    # Important invariant that motivated the audit.
    assert records[0x9C][0x45] == 0x14
    assert records[0x14][0x45] == 0x00
    assert records[0x71][0x45] == 0x00
    d=diff(records[0x9C],records[0x14])
    print('hidden_dragoon_vs_playable_dragoon_diff_offsets='+','.join(f'0x{x:02X}' for x in d))
    print('NOTE: +0x45 is only classified as an alias/reference field after its global pattern and consumers agree; this tool deliberately makes no graphics-only assumption.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
