#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'; OUT=ROOT/'gatekeeper-roster-battle-copy.txt'
SEEDS={'func_8019BB9C'}
FRE=re.compile(r'^\s*glabel\s+(\S+)'); ERE=re.compile(r'^\s*endlabel\s+(\S+)'); CALL=re.compile(r'\bjal\s+(\S+)')

def parse():
 f={}
 for p in ASM.rglob('*.s'):
  ls=p.read_text(errors='replace').splitlines(); starts={}
  for i,l in enumerate(ls):
   m=FRE.match(l)
   if m: starts[m.group(1)]=i
   e=ERE.match(l)
   if e and e.group(1) in starts:
    n=e.group(1); a=starts[n]; f[n]=(p.relative_to(ROOT),a+1,i+1,ls[a:i+1])
 return f

def main():
 f=parse(); rev={}
 for n,(_,_,_,b) in f.items():
  for l in b:
   m=CALL.search(l)
   if m: rev.setdefault(m.group(1),[]).append(n)
 seeds=set(SEEDS); frontier=set(seeds); seen=set(seeds)
 for _ in range(4):
  nxt=set()
  for n in frontier:
   if n not in f: continue
   for c in CALL.findall('\n'.join(f[n][3])):
    if c in f and c not in seen: nxt.add(c)
   for c in rev.get(n,[]):
    if c not in seen: nxt.add(c)
  seen|=nxt; frontier=nxt
 r=['Gatekeeper roster -> battle-copy trace','====================================','']
 for n in sorted(seen):
  if n not in f: continue
  p,s,e,b=f[n]; text='\n'.join(b)
  interesting=('D_80193BE0' in text or n in SEEDS or n.startswith('func_8019') or n.startswith('func_801A') or n.startswith('func_801B'))
  if not interesting: continue
  r += [f'## {n} {p}:{s}-{e}', 'callers='+','.join(rev.get(n,[])), 'callees='+','.join(CALL.findall(text)), '']
  for ln,l in enumerate(b,start=s):
   tags=[]
   if 'D_80193BE0' in l: tags.append('ROSTER')
   if any(x in l for x in ['0x12(', '0x13(', '0x35(', '0xF6(', '0x1C4(', '0x20C(']): tags.append('FIELD')
   if any(op in l for op in [' sb ', ' sh ', ' sw ', ' lbu ', ' lhu ', ' lw ']): tags.append('MEM')
   if 'jal' in l: tags.append('CALL')
   if tags or 'D_80193BE0' in text:
    r.append(f'{ln:6d}: {"["+"/".join(tags)+"] " if tags else ""}{l}')
  r.append('')
 OUT.write_text('\n'.join(r)+'\n'); print('\n'.join(r))
if __name__=='__main__': main()
