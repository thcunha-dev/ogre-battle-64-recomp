#!/usr/bin/env python3
"""Trace class-change eligibility helper family for playable Knight of Danika.

Manual Change Class is known to filter ordinary human male/female and Hawkmen,
exclude leaders/specials, then evaluate class requirements.  This read-only
trace emits the nearby 0x8016Fxxx/FFxx helper bodies and every caller, making it
possible to identify the native eligibility/list-builder path by semantics.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
FUNC=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+(func_[0-9A-Fa-f]+)\b')
TARGETS={
 'func_8016F500','func_8016F520','func_8016F5D0','func_8016F5E8','func_8016F600',
 'func_8016F634','func_8016FA54','func_8016FB70','func_8016FE98','func_8016FF14',
 'func_8016FF7C','func_8016DC4C','func_8016DEE4','func_8016E250','func_8016E358',
 'func_8016E490','func_8016E52C'
}
ROSTER=re.compile(r'\bD_80193BE0\b|\bD_80193BF[12]\b')
CLASSBYTE=re.compile(r'\b(?:lbu|lb|sb)\s+[^\n]*0x1[12]\(\$[a-z0-9]+\)',re.I)


def blocks(path):
 lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); out=[]; i=0
 while i<len(lines):
  m=FUNC.match(lines[i])
  if not m: i+=1; continue
  n=m.group(1); s=i; e=len(lines)-1
  for j in range(i+1,len(lines)):
   if END.match(lines[j]): e=j; break
   if FUNC.match(lines[j]): e=j-1; break
  out.append((n,s+1,e+1,lines[s:e+1])); i=max(e+1,i+1)
 return out


def main():
 funcs={}; callers={}
 for p in sorted(ASM.rglob('*.s')):
  try: bs=blocks(p)
  except OSError: continue
  for n,s,e,b in bs:
   t='\n'.join(b); cs=CALL.findall(t)
   funcs[n]={'p':p,'s':s,'e':e,'b':b,'t':t,'calls':cs}
   for c in cs: callers.setdefault(c,[]).append(n)

 print('Knight of Danika class eligibility helper trace')
 print('================================================')
 print('manual_filter=ordinary male/female/Hawkman; no leader/special')
 print()
 print('TARGET_HELPERS')
 for n in sorted(TARGETS):
  f=funcs.get(n)
  if not f:
   print(f'--- {n} MISSING ---'); continue
  print(f'--- {n} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} ---')
  print('CALLERS ' + ','.join(callers.get(n,[])[:80]))
  print('CALLEES ' + ','.join(f['calls']))
  for line in f['b']: print(line)
  print()

 # Rank all direct callers of target helpers. A true menu list builder is likely
 # to combine eligibility helpers, character bytes, and UI/menu state.
 rows=[]
 for n,f in funcs.items():
  hs=sorted(set(f['calls']) & TARGETS)
  if not hs: continue
  roster=bool(ROSTER.search(f['t'])); cb=bool(CLASSBYTE.search(f['t']))
  score=len(hs)*10+(12 if roster else 0)+(8 if cb else 0)
  rows.append((score,n,f,hs,roster,cb))
 rows.sort(key=lambda r:(-r[0],r[1]))
 print('RANKED_ELIGIBILITY_CALLERS')
 for score,n,f,hs,roster,cb in rows[:100]:
  print(f'CAND score={score:03d} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} function={n} helpers={",".join(hs)} roster={int(roster)} char_fields={int(cb)}')
  print('  CALLERS ' + ','.join(callers.get(n,[])[:40]))
  print('  CALLEES ' + ','.join(f['calls']))

 assert all(n in funcs for n in TARGETS)
 print('class eligibility helper trace: PASS')

if __name__=='__main__': main()
