#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'asm/data/5C230.data.s'
BASE=0x80187C34
STRIDE=0x48
ADDR_RE=re.compile(r'/\*\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]{8})\s*\*/\s*\.(byte|short|word)\s+(.+?)\s*$')
HEX_RE=re.compile(r'0x([0-9A-Fa-f]+)')

def mem():
 m={}
 for line in DATA.read_text(errors='replace').splitlines():
  x=ADDR_RE.search(line)
  if not x: continue
  a=int(x.group(1),16); kind=x.group(2); vals=[int(v,16) for v in HEX_RE.findall(x.group(3))]
  sz={'byte':1,'short':2,'word':4}[kind]
  for n,v in enumerate(vals):
   for j in range(sz): m[a+n*sz+j]=(v>>(8*(sz-1-j)))&255
 return m

def u16(m,a): return (m[a]<<8)|m[a+1]

def main():
 m=mem()
 print('Gatekeeper class-default equipment inspection')
 print('=============================================')
 for name,cid in [('Fighter',0x02),('Dragoon',0x14),('Gatekeeper',0x71),('HiddenDragoon',0x9C)]:
  r=BASE+cid*STRIDE
  vals=[u16(m,r+0x2E+i*2) for i in range(4)]
  print(f'{name:13s} class=0x{cid:02X} record=0x{r:08X} defaults='+' '.join(f'0x{x:04X}' for x in vals))
  print('  head='+ ' '.join(f'{m[r+i]:02X}' for i in range(16)))
  print('  tail='+ ' '.join(f'{m[r+i]:02X}' for i in range(0x40,0x48)))
 print('PASS')
if __name__=='__main__': main()
