#!/usr/bin/env python3
"""Decode DANIKA_BANKJ snapshots and conservatively trace participant->roster flow.

The ownership-sensitive rule is deliberately strict.  A participant +0xF6 value
is only promoted to a strong persistent-roster bridge when local MIPS dataflow
proves all three facts:
  * the index is bounded by 100;
  * arithmetic derives exactly index * 0x38;
  * the derived record pointer is read at class offset +0x12.

Even a strong bridge is not, by itself, labelled allied.  Side ownership remains
UNKNOWN until separate control-flow/runtime evidence excludes enemy records.
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

LINE_RE = re.compile(
    r"\bDANIKA_BANKJ\s+name=(?P<name>[A-Za-z0-9_]+)\s+"
    r"addr=(?P<addr>[0-9A-Fa-f]{8})\s+off=(?P<off>[0-9A-Fa-f]+)\s+"
    r"bytes=(?P<bytes>[0-9A-Fa-f]+)"
)
REG = [
    "$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3",
    "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7",
    "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7",
    "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra",
]
FIELD_NAMES = {
    0x0031:"PART_LEVEL", 0x0032:"PART_EXP", 0x00F6:"PART_CHARIDX",
    0x00F8:"PART_STRIDE", 0x01C4:"PART_OFF", 0x020C:"PART_VALID",
    0x0012:"ROSTER_CLASS", 0x0013:"ROSTER_LEVEL", 0x0035:"ROSTER_EXP",
    0x0038:"ROSTER_STRIDE", 0x0064:"CHAR_COUNT_100",
}
KNOWN_OPS = {
    0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,
    0x0C,0x0D,0x0E,0x0F,0x20,0x21,0x23,0x24,0x25,0x28,0x29,0x2B,
}
KNOWN_SPECIAL = {0x00,0x02,0x03,0x08,0x09,0x20,0x21,0x22,0x23,0x24,0x25,0x2A,0x2B}

@dataclass
class Insn:
    pc: int
    word: int
    text: str


def sx16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


def parse(text: str) -> dict[str, tuple[int, bytes]]:
    chunks: dict[str, list[tuple[int,int,bytes]]] = defaultdict(list)
    for line in text.splitlines():
        m = LINE_RE.search(line)
        if m:
            chunks[m.group("name")].append((int(m.group("addr"),16), int(m.group("off"),16), bytes.fromhex(m.group("bytes"))))
    out = {}
    for name, entries in chunks.items():
        bases = {x[0] for x in entries}
        if len(bases) != 1:
            raise ValueError(f"{name}: inconsistent base addresses: {sorted(bases)}")
        base = next(iter(bases)); size = max(off+len(raw) for _,off,raw in entries)
        buf = bytearray(size); filled = bytearray(size)
        for _, off, raw in entries:
            for i,b in enumerate(raw):
                p = off+i
                if filled[p] and buf[p] != b:
                    raise ValueError(f"{name}: conflicting byte at +0x{p:X}")
                buf[p]=b; filled[p]=1
        if not all(filled):
            p = next(i for i,v in enumerate(filled) if not v)
            raise ValueError(f"{name}: incomplete dump, first missing +0x{p:X}")
        out[name]=(base,bytes(buf))
    return out


def plausibility(data: bytes, endian: str) -> int:
    score=0
    for off in range(0,len(data)-3,4):
        w=int.from_bytes(data[off:off+4],endian)
        if w==0: score+=2; continue
        op=(w>>26)&0x3F
        if op==0: score += 3 if (w&0x3F) in KNOWN_SPECIAL else -1
        elif op in KNOWN_OPS: score+=3
        else: score-=1
    return score


def reg(n:int)->str: return REG[n&31]


def decode(word:int, pc:int)->str:
    op=(word>>26)&0x3F; rs=(word>>21)&31; rt=(word>>16)&31; rd=(word>>11)&31; sa=(word>>6)&31
    fn=word&0x3F; imm=word&0xFFFF; simm=sx16(imm)
    if word==0: return "nop"
    if op==0:
        tbl={0x00:"sll",0x02:"srl",0x03:"sra",0x08:"jr",0x09:"jalr",0x20:"add",0x21:"addu",0x22:"sub",0x23:"subu",0x24:"and",0x25:"or",0x2A:"slt",0x2B:"sltu"}
        if fn==0x00:return f"sll {reg(rd)}, {reg(rt)}, {sa}"
        if fn==0x02:return f"srl {reg(rd)}, {reg(rt)}, {sa}"
        if fn==0x03:return f"sra {reg(rd)}, {reg(rt)}, {sa}"
        if fn==0x08:return f"jr {reg(rs)}"
        if fn==0x09:return f"jalr {reg(rd)}, {reg(rs)}"
        if fn in (0x20,0x21,0x22,0x23,0x24,0x25,0x2A,0x2B):return f"{tbl[fn]} {reg(rd)}, {reg(rs)}, {reg(rt)}"
        return f"special fn=0x{fn:02X} raw=0x{word:08X}"
    target=((pc+4)&0xF0000000)|((word&0x03FFFFFF)<<2); branch=(pc+4+(simm<<2))&0xFFFFFFFF
    if op==0x01:
        k={0x00:"bltz",0x01:"bgez",0x10:"bltzal",0x11:"bgezal"}.get(rt)
        if k:return f"{k} {reg(rs)}, 0x{branch:08X}"
    if op==0x02:return f"j 0x{target:08X}"
    if op==0x03:return f"jal 0x{target:08X}"
    if op==0x04:return f"beq {reg(rs)}, {reg(rt)}, 0x{branch:08X}"
    if op==0x05:return f"bne {reg(rs)}, {reg(rt)}, 0x{branch:08X}"
    if op==0x06:return f"blez {reg(rs)}, 0x{branch:08X}"
    if op==0x07:return f"bgtz {reg(rs)}, 0x{branch:08X}"
    if op==0x08:return f"addi {reg(rt)}, {reg(rs)}, {simm}"
    if op==0x09:return f"addiu {reg(rt)}, {reg(rs)}, {simm}"
    if op==0x0A:return f"slti {reg(rt)}, {reg(rs)}, {simm}"
    if op==0x0B:return f"sltiu {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op==0x0C:return f"andi {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op==0x0D:return f"ori {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op==0x0E:return f"xori {reg(rt)}, {reg(rs)}, 0x{imm:04X}"
    if op==0x0F:return f"lui {reg(rt)}, 0x{imm:04X}"
    mem={0x20:"lb",0x21:"lh",0x23:"lw",0x24:"lbu",0x25:"lhu",0x28:"sb",0x29:"sh",0x2B:"sw"}.get(op)
    if mem:return f"{mem} {reg(rt)}, {simm}({reg(rs)})"
    return f"op=0x{op:02X} raw=0x{word:08X}"


def field_hits(word:int)->list[str]:
    op=(word>>26)&0x3F; imm=word&0xFFFF
    return [FIELD_NAMES[imm]] if op in KNOWN_OPS and imm in FIELD_NAMES else []


def decoded_stream(base:int,data:bytes,endian:str)->list[Insn]:
    out=[]
    for off in range(0,len(data)-3,4):
        w=int.from_bytes(data[off:off+4],endian); out.append(Insn(base+off,w,decode(w,base+off)))
    return out


def trace_charidx_chains(insns:list[Insn])->list[list[str]]:
    """Track exact linear coefficient of one +0xF6 seed through a bounded window."""
    load_re=re.compile(r"\b(?:lbu|lb) (\$\w+), 246\((\$\w+)\)")
    slti_re=re.compile(r"\bsltiu (\$\w+), (\$\w+), 0x0064\b")
    shift_re=re.compile(r"\bsll (\$\w+), (\$\w+), ([0-9]+)\b")
    alu_re=re.compile(r"\b(addu|subu|or) (\$\w+), (\$\w+), (\$\w+)\b")
    class_re=re.compile(r"\b(?:lbu|lb) (\$\w+), 18\((\$\w+)\)")
    chains=[]
    for i,seed in enumerate(insns):
        m=load_re.search(seed.text)
        if not m: continue
        coeff={m.group(1):1}; range100=False; stride_reg=set(); class12=False
        ev=[f"0x{seed.pc:08X} {seed.text}  [charidx seed coeff=1]"]
        for cur in insns[i+1:min(len(insns),i+48)]:
            t=cur.text
            sm=slti_re.search(t)
            if sm and coeff.get(sm.group(2))==1:
                range100=True; ev.append(f"0x{cur.pc:08X} {t}  [index<100]")
            sh=shift_re.search(t)
            if sh and sh.group(2) in coeff:
                dest,src,amount=sh.groups(); coeff[dest]=coeff[src]*(1<<int(amount))
                if coeff[dest]==56: stride_reg.add(dest)
                ev.append(f"0x{cur.pc:08X} {t}  [coeff={coeff[dest]}]")
            am=alu_re.search(t)
            if am:
                op,dest,left,right=am.groups()
                if op=="or" and right=="$zero" and left in coeff:
                    coeff[dest]=coeff[left]
                elif op=="addu":
                    if left in coeff and right in coeff: coeff[dest]=coeff[left]+coeff[right]
                    elif left in coeff or right in coeff:
                        # adding a non-derived base creates a pointer whose offset
                        # still has the derived coefficient; retain that coefficient.
                        coeff[dest]=coeff.get(left,coeff.get(right))
                elif op=="subu" and left in coeff and right in coeff:
                    coeff[dest]=coeff[left]-coeff[right]
                if dest in coeff:
                    if coeff[dest]==56: stride_reg.add(dest)
                    ev.append(f"0x{cur.pc:08X} {t}  [coeff={coeff[dest]}]")
            cl=class_re.search(t)
            if cl and cl.group(2) in coeff and coeff[cl.group(2)]==56:
                class12=True; ev.append(f"0x{cur.pc:08X} {t}  [roster class +0x12 from 56*index pointer]")
        status=[]
        if range100: status.append("range100")
        if stride_reg: status.append("stride38")
        if class12: status.append("class12")
        ev.insert(0,"chain="+("+".join(status) if status else "seed_only")); chains.append(ev)
    return chains


def summarize(windows:dict[str,tuple[int,bytes]])->str:
    out=["Knight of Danika bank-J runtime dump analysis","=============================================="]
    if not windows:
        out.append("No DANIKA_BANKJ records found."); return "\n".join(out)+"\n"
    strong=0
    for name in sorted(windows):
        base,data=windows[name]; be=plausibility(data,"big"); le=plausibility(data,"little"); endian="big" if be>=le else "little"
        signal=len(set(data))>2 and any(data) and any(b!=0xFF for b in data)
        out += ["",f"[{name}] base=0x{base:08X} bytes=0x{len(data):X}",f"signal={'yes' if signal else 'no'} mips_score_big={be} mips_score_little={le} chosen={endian}"]
        insns=decoded_stream(base,data,endian); hits=[]
        for ins in insns:
            marks=field_hits(ins.word); suffix=f"  ; >>> {','.join(marks)}" if marks else ""
            out.append(f"0x{ins.pc:08X}: {ins.word:08X}  {ins.text}{suffix}")
            if marks:hits.append((ins.pc,marks,ins.text))
        out.append(f"field_hits={len(hits)}")
        for pc,marks,text in hits: out.append(f"  HIT 0x{pc:08X} {','.join(marks)} :: {text}")
        chains=trace_charidx_chains(insns); out.append(f"charidx_chains={len(chains)}")
        for chain in chains:
            is_strong=all(x in chain[0] for x in ("range100","stride38","class12"))
            if is_strong: strong+=1
            out.append("  ROSTER_BRIDGE_CHAIN="+("STRONG" if is_strong else "PARTIAL")); out.extend("    "+x for x in chain)
    out += ["","Ownership synthesis","-------------------",f"strong_participant_to_roster_chains={strong}",
            "participant_charidx_to_persistent_roster="+("SUPPORTED" if strong else "UNPROVEN"),"ownership_side=UNKNOWN","",
            "Interpretation rule","-------------------",
            "A STRONG chain proves participant+0xF6 is bounded to 100 and reaches",
            "a 0x38-stride persistent roster record's class +0x12. It does NOT alone",
            "prove allied ownership. DANIKA_SIDE_ALLIED still requires independent",
            "side/control-flow evidence that excludes opposing/generated records."]
    return "\n".join(out)+"\n"


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("log",type=Path); ap.add_argument("-o","--output",type=Path); args=ap.parse_args()
    report=summarize(parse(args.log.read_text(encoding="utf-8",errors="replace")))
    if args.output: args.output.write_text(report,encoding="utf-8")
    else: print(report,end="")
    return 0

if __name__=="__main__": raise SystemExit(main())
