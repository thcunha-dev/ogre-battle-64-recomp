#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
OUT=ROOT/'gatekeeper-combatant-path.txt'
TARGETS={
'func_8019F928','func_8019FC68','func_801B28F8','func_8019B198','func_8019B074',
'func_801AD558','func_801AD6C4','func_801B3868','func_80197B90','func_80197BE4',
'func_8016DE3C'
}
FRE=re.compile(r'^\s*glabel\s+(\S+)')
ERE=re.compile(r'^\s*endlabel\s+(\S+)')
CALL=re.compile(r'\bjal\s+(\S+)')

def parse():
 out={}
 for p in ASM.rglob('*.s'):
  lines=p.read_text(errors='replace').splitlines(); starts={}
  for i,l in enumerate(lines):
   m=FRE.match(l)
   if m: starts[m.group(1)]=i
   e=ERE.match(l)
   if e and e.group(1) in starts:
    n=e.group(1); a=starts[n]; out[n]=(p.relative_to(ROOT),a+1,i+1,lines[a:i+1])
 return out

def main():
 funcs=parse(); missing=TARGETS-set(funcs); assert not missing, missing
 rev={}
 for n,(_,_,_,b) in funcs.items():
  for l in b:
   m=CALL.search(l)
   if m: rev.setdefault(m.group(1),[]).append(n)
 r=['Gatekeeper true combatant/model path','====================================','']
 for n in sorted(TARGETS):
  p,s,e,b=funcs[n]; text='\n'.join(b)
  r += [f'## {n} {p}:{s}-{e}', 'callers='+','.join(rev.get(n,[])), 'callees='+','.join(CALL.findall(text)), '']
  for ln,l in enumerate(b,start=s):
   mark=[]
   if '0x12(' in l: mark.append('CLASS?')
   if any(x in l for x in ['0x34(', '0x4B(', '0x4C(', '0x4F(', '0x50(', 'D_801BA718','D_801B80B8']): mark.append('MODEL')
   if 'jal' in l: mark.append('CALL')
   r.append(f'{ln:6d}: {"["+"/".join(mark)+"] " if mark else ""}{l}')
  r.append('')
 OUT.write_text('\n'.join(r)+'\n'); print('\n'.join(r))
if __name__=='__main__': main()
