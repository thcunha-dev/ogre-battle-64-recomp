#!/usr/bin/env python3
"""Find likely permanent writes to a character's class-id byte (+0x12).

The old smoke test wrote roster RAM directly.  For the real playable Danika mod
we want the native Change Class commit path.  This read-only scanner finds every
function containing `sb ..., 0x12($reg)`, reports local reads/restores, class
helpers and caller/callee context, then ranks writes that look like permanent
menu commits rather than temporary level-up simulation.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
FUNC=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+(func_[0-9A-Fa-f]+)\b')
WRITE=re.compile(r'\bsb\s+\$([a-z0-9]+),\s*0x12\(\$([a-z0-9]+)\)',re.I)
READ=re.compile(r'\b(?:lbu|lb)\s+\$([a-z0-9]+),\s*0x12\(\$([a-z0-9]+)\)',re.I)
CLASS_HELPERS={
 'func_8016D220','func_8016D274','func_8016D2C8','func_8016D31C','func_8016D370',
 'func_8016DC4C','func_8016DEE4','func_8016E250','func_8016E358','func_8016E490',
 'func_8016E52C','func_8016EA54','func_8016EBC4','func_8016F13C'
}


def blocks(path):
 lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); out=[]; i=0
 while i<len(lines):
  m=FUNC.match(lines[i])
  if not m: i+=1; continue
  name=m.group(1); s=i; e=len(lines)-1
  for j in range(i+1,len(lines)):
   if END.match(lines[j]): e=j; break
   if FUNC.match(lines[j]): e=j-1; break
  out.append((name,s+1,e+1,lines[s:e+1])); i=max(e+1,i+1)
 return out


def main():
 funcs={}; callers={}; rows=[]
 for p in sorted(ASM.rglob('*.s')):
  try: bs=blocks(p)
  except OSError: continue
  for name,s,e,body in bs:
   text='\n'.join(body); funcs[name]=(p,s,e,body,text)
   calls=CALL.findall(text)
   for callee in calls: callers.setdefault(callee,[]).append((p,name,s,e))
   writes=list(WRITE.finditer(text))
   if not writes: continue
   reads=list(READ.finditer(text)); helpers=sorted(set(calls)&CLASS_HELPERS)
   # A read of +0x12 followed by multiple writes often means temporary
   # simulation/restoration (known example F13C). A single write with UI-ish
   # callers and helper use is more interesting for a permanent commit.
   score=10
   score += 3 if len(writes)==1 else 0
   score -= 4 if len(writes)>=2 else 0
   score -= 3 if len(reads)>=1 and len(writes)>=2 else 0
   score += 2 if helpers else 0
   if name=='func_8016F13C': score-=12
   rows.append((score,p,name,s,e,len(reads),len(writes),helpers,calls))

 rows.sort(key=lambda r:(-r[0],str(r[1]),r[3]))
 print('Knight of Danika class-id commit write trace')
 print('============================================')
 print('target=permanent native Change Class commit to character+0x12')
 print('known_temporary_simulation=func_8016F13C')
 print()
 print('RANKED_WRITERS')
 for score,p,name,s,e,nr,nw,helpers,calls in rows:
  print(f'WRITER score={score:02d} {p.relative_to(ROOT)}:{s}-{e} function={name} reads12={nr} writes12={nw} helpers={",".join(helpers) or "-"}')
  for cp,cn,cs,ce in callers.get(name,[])[:12]:
   print(f'  CALLER {cp.relative_to(ROOT)}:{cs}-{ce} {cn}')
 print()

 print('WRITER_BODIES')
 for score,p,name,s,e,nr,nw,helpers,calls in rows[:20]:
  body=funcs[name][3]
  print(f'--- score={score} {name} {p.relative_to(ROOT)}:{s}-{e} ---')
  for line in body: print(line)
  print()

 assert rows, 'no class-id writers found'
 assert any(r[2]=='func_8016F13C' for r in rows), 'known temporary writer missing'
 print(f'class_id_writer_count={len(rows)}')
 print('class-id commit write trace: PASS')

if __name__=='__main__': main()
