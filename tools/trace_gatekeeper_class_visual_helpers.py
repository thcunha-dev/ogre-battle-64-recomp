#!/usr/bin/env python3
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]; ASM=ROOT/'asm'; OUT=ROOT/'gatekeeper-class-visual-helpers.txt'
TARGETS={'func_8016CD30','func_8016CD50','func_8016DE3C','func_8016DC4C','func_8016DEE4','func_8016E250','func_8016E52C','func_8016F600','func_8016F634'}
FRE=re.compile(r'^\s*glabel\s+(\S+)'); ERE=re.compile(r'^\s*endlabel\s+(\S+)'); CALL=re.compile(r'\bjal\s+(\S+)')

def parse():
 f={}
 for p in ASM.rglob('*.s'):
  ls=p.read_text(errors='replace').splitlines(); st={}
  for i,l in enumerate(ls):
   m=FRE.match(l)
   if m: st[m.group(1)]=i
   e=ERE.match(l)
   if e and e.group(1) in st:
    n=e.group(1); a=st[n]; f[n]=(p.relative_to(ROOT),a+1,i+1,ls[a:i+1])
 return f

def main():
 f=parse(); rev={}
 for n,(_,_,_,b) in f.items():
  for l in b:
   m=CALL.search(l)
   if m: rev.setdefault(m.group(1),[]).append(n)
 missing=TARGETS-set(f); assert not missing,missing
 r=['Gatekeeper class->visual helper trace','====================================','']
 for n in sorted(TARGETS):
  p,s,e,b=f[n]; r += [f'## {n} {p}:{s}-{e}','battle_callers='+','.join(x for x in rev.get(n,[]) if x.startswith(('func_8019','func_801A','func_801B'))),'all_callers='+','.join(rev.get(n,[])),'']
  for ln,l in enumerate(b,start=s): r.append(f'{ln:6d}: {l}')
  r.append('')
 # Dump battle callers that invoke targets, but only focused lines/windows.
 callers=sorted({x for t in TARGETS for x in rev.get(t,[]) if x.startswith(('func_8019','func_801A','func_801B'))})
 r += ['BATTLE CALLER WINDOWS','---------------------']
 for n in callers:
  p,s,e,b=f[n]; r.append(f'## {n} {p}:{s}-{e}')
  for i,l in enumerate(b):
   m=CALL.search(l)
   if m and m.group(1) in TARGETS:
    for j in range(max(0,i-12),min(len(b),i+18)): r.append(f'{s+j:6d}: {b[j]}')
    r.append('---')
 OUT.write_text('\n'.join(r)+'\n'); print('\n'.join(r))
if __name__=='__main__': main()
