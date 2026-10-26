#!/usr/bin/env python3
"""Map callers of Ogre Battle 64 class metadata helpers.

The manual Change Class UI should consume several of the class getters near
0x8016Dxxx-0x8016Exxx.  This read-only analysis maps every direct caller,
groups callers by function/module, and ranks callers that combine multiple
class helpers with roster/menu state.  It is deliberately broader than direct
D_80187Cxx references because most real UI code goes through getter helpers.
"""
from pathlib import Path
import re
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
FUNC=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+(func_[0-9A-Fa-f]+)\b')
HELPER_RE=re.compile(r'^func_8016(?:D[0-9A-Fa-f]{3}|E[0-9A-Fa-f]{3})$')
ROSTER=re.compile(r'\bD_80193(?:BE0|BF1|BF2|9[0-9A-Fa-f]{2}|A[0-9A-Fa-f]{2})\b')
CLASS_BYTE=re.compile(r'\b(?:lbu|lb|sb)\s+[^\n]*0x12\(\$[a-z0-9]+\)',re.I)
MENU_GLOBAL=re.compile(r'\bD_8019(?:39|3A|3B|6A|6B)[0-9A-Fa-f]{2}\b')
STORE=re.compile(r'\bsb\s+')

# Getter/eligibility helpers known to expose class metadata. Including aliases
# and the richer requirements/transition helpers gives the UI call graph enough
# surface to stand out from one-off gameplay code.
KEY={
 'func_8016D220','func_8016D274','func_8016D2C8','func_8016D31C','func_8016D370',
 'func_8016D3C4','func_8016D418','func_8016D46C','func_8016D4C0','func_8016D514',
 'func_8016D568','func_8016D5BC','func_8016D610','func_8016D664','func_8016D904',
 'func_8016D958','func_8016DC4C','func_8016DE3C','func_8016DE90','func_8016DEE4',
 'func_8016DFA8','func_8016DFFC','func_8016E050','func_8016E0A4','func_8016E1FC',
 'func_8016E250','func_8016E358','func_8016E490','func_8016E52C','func_8016EA54',
 'func_8016EBC4'
}


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
 funcs={}; reverse=defaultdict(list)
 for p in sorted(ASM.rglob('*.s')):
  try: bs=blocks(p)
  except OSError: continue
  for n,s,e,b in bs:
   t='\n'.join(b); calls=CALL.findall(t)
   funcs[n]={'p':p,'s':s,'e':e,'b':b,'t':t,'calls':calls}
   for c in calls: reverse[c].append(n)

 rows=[]
 for n,f in funcs.items():
  hs=sorted(set(f['calls']) & KEY)
  if not hs: continue
  roster=sorted(set(ROSTER.findall(f['t']))); cls=bool(CLASS_BYTE.search(f['t']))
  menus=sorted(set(MENU_GLOBAL.findall(f['t']))); stores=len(STORE.findall(f['t']))
  # Multi-helper consumers are the strongest candidates for a class-detail or
  # eligibility UI. Roster/menu state increases confidence; text parser is known.
  score=len(hs)*8 + (12 if roster else 0) + (8 if cls else 0) + min(len(menus)*2,10) + min(stores,5)
  if n=='func_8017FC48': score-=20
  if n in {'func_8016F13C','func_8016EBC4'}: score-=20
  rows.append((score,n,f,hs,roster,cls,menus,stores))
 rows.sort(key=lambda r:(-r[0],r[1]))

 print('Knight of Danika class-helper caller map')
 print('========================================')
 print('goal=find native manual Change Class UI/eligibility path')
 print('known_text_formatter=func_8017FC48')
 print('known_progression=func_8016F13C,func_8016EBC4')
 print()
 print('RANKED_CALLERS')
 for score,n,f,hs,roster,cls,menus,stores in rows[:120]:
  print(f'CAND score={score:03d} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} function={n} helpers={",".join(hs)} roster={",".join(roster) or "-"} class_byte={int(cls)} menus={",".join(menus) or "-"} stores={stores}')
  print('  CALLERS ' + ','.join(reverse.get(n,[])[:30]))
  print('  CALLEES ' + ','.join(f['calls']))
 print()

 print('HIGH_SIGNAL_BODIES')
 for score,n,f,hs,roster,cls,menus,stores in rows:
  if score<32: continue
  print(f'--- score={score} {n} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} ---')
  print('CALLERS ' + ','.join(reverse.get(n,[])[:30]))
  print('CALLEES ' + ','.join(f['calls']))
  for line in f['b']: print(line)
  print()

 print('KEY_HELPER_REVERSE_MAP')
 for h in sorted(KEY):
  cs=reverse.get(h,[])
  if cs: print(h + ': ' + ','.join(cs))

 assert rows
 assert any(r[1]=='func_8017FC48' for r in rows)
 print(f'class_helper_caller_count={len(rows)}')
 print('class-helper caller map: PASS')

if __name__=='__main__': main()
