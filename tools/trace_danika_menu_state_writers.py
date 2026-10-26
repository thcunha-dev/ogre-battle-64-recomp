#!/usr/bin/env python3
"""Trace writers/readers of selected-character UI state D_801939F4..FF.

The class text formatter consumes these globals but is not the controller. This
scanner finds the functions that write them, reports exact reference lines with
surrounding context, and emits caller/callee bodies for the most likely menu
controllers.  The goal is to locate candidate class selection/confirmation
without modifying roster RAM speculatively.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
ASM=ROOT/'asm'
FUNC=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)')
END=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+(func_[0-9A-Fa-f]+)\b')
SYM=re.compile(r'\bD_801939F[0-9A-Fa-f]\b')
STORE_LINE=re.compile(r'\b(?:sb|sh|sw)\b.*%lo\(D_801939F[0-9A-Fa-f]')
LOAD_LINE=re.compile(r'\b(?:lb|lbu|lh|lhu|lw)\b.*%lo\(D_801939F[0-9A-Fa-f]')
ROSTER=re.compile(r'\bD_80193BE0\b|\bD_80193BF[12]\b')
CLASS_HELP=re.compile(r'\bfunc_8016(?:D[0-9A-Fa-f]{3}|E[0-9A-Fa-f]{3}|F[0-9A-Fa-f]{3})\b')


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
 funcs={}; callers={}; rows=[]
 for p in sorted(ASM.rglob('*.s')):
  try: bs=blocks(p)
  except OSError: continue
  for n,s,e,b in bs:
   t='\n'.join(b); calls=CALL.findall(t)
   funcs[n]={'p':p,'s':s,'e':e,'b':b,'t':t,'calls':calls}
   for c in calls: callers.setdefault(c,[]).append(n)
   syms=sorted(set(SYM.findall(t)))
   if not syms: continue
   writes=[]; reads=[]
   for idx,line in enumerate(b):
    if STORE_LINE.search(line): writes.append((idx,line))
    if LOAD_LINE.search(line): reads.append((idx,line))
   helpers=sorted(set(CLASS_HELP.findall(t)))
   roster=bool(ROSTER.search(t))
   score=len(writes)*12 + len(reads)*2 + (10 if roster else 0) + (8 if helpers else 0)
   if n=='func_8017FC48': score-=15
   rows.append((score,n,syms,writes,reads,helpers,roster))
 rows.sort(key=lambda r:(-r[0],r[1]))

 print('Knight of Danika menu-state writer trace')
 print('========================================')
 print('state_range=D_801939F0..D_801939FF')
 print('selected_index=D_801939F4')
 print()
 print('RANKED_STATE_USERS')
 for score,n,syms,writes,reads,helpers,roster in rows:
  f=funcs[n]
  print(f'CAND score={score:03d} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} function={n} syms={",".join(syms)} writes={len(writes)} reads={len(reads)} roster={int(roster)} helpers={",".join(helpers) or "-"}')
  print('  CALLERS ' + ','.join(callers.get(n,[])[:40]))
  print('  CALLEES ' + ','.join(f['calls']))
  for idx,line in writes:
   lo=max(0,idx-4); hi=min(len(f['b']),idx+5)
   print('  WRITE_CONTEXT')
   for x in f['b'][lo:hi]: print('    '+x)
 print()

 print('WRITER_BODIES')
 writer_names=[]
 for _,n,_,writes,_,_,_ in rows:
  if writes and n not in writer_names: writer_names.append(n)
 for n in writer_names[:30]:
  f=funcs[n]
  print(f'--- {n} {f["p"].relative_to(ROOT)}:{f["s"]}-{f["e"]} ---')
  print('CALLERS ' + ','.join(callers.get(n,[])[:40]))
  print('CALLEES ' + ','.join(f['calls']))
  for line in f['b']: print(line)
  print()

 assert rows
 assert any(n=='func_8017FC48' for _,n,*_ in rows)
 assert any(w for _,_,_,w,*_ in rows), 'no menu-state writers found'
 print(f'menu_state_user_count={len(rows)}')
 print('menu-state writer trace: PASS')

if __name__=='__main__': main()
