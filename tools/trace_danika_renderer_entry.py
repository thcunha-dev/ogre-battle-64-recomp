#!/usr/bin/env python3
"""Trace the sole caller of the class-aware renderer func_801AD6C4.

func_801AD6C4 is a real display-list renderer and reads class selectors from the
descriptor pointer stored at renderer-object +0x34.  It has one caller,
func_801B3868.  This report emits that caller completely, its incoming callers,
and every nearby producer/consumer of +0x34 pointers so the battle descriptor
construction path can be followed upstream.
"""
from __future__ import annotations
import re
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]; ASM=ROOT/'asm'
TARGET='func_801B3868'; RENDER='func_801AD6C4'
GL=re.compile(r'^\s*glabel\s+([A-Za-z0-9_.$]+)'); EN=re.compile(r'^\s*endlabel\s+([A-Za-z0-9_.$]+)')
CALL=re.compile(r'\bjal\s+([A-Za-z0-9_.$]+)')
MEM34=re.compile(r'\b(lw|sw|lbu|sb|lhu|sh)\s+\$([A-Za-z0-9]+),\s*0x34\(\$([A-Za-z0-9]+)\)',re.I)

def files(): return sorted(ASM.rglob('*.s'))
def funcs(path):
 lines=path.read_text(encoding='utf-8',errors='replace').splitlines(); st=[]
 for i,l in enumerate(lines):
  m=GL.match(l)
  if m: st.append((i,m.group(1)))
 for n,(s,name) in enumerate(st):
  e=st[n+1][0]-1 if n+1<len(st) else len(lines)-1
  for j in range(s+1,e+1):
   m=EN.match(lines[j])
   if m and m.group(1)==name: e=j; break
  yield name,s,e,lines

def main():
 defs={}; incoming=defaultdict(list); mem34=[]
 for path in files():
  rel=path.relative_to(ROOT).as_posix()
  for name,s,e,lines in funcs(path):
   defs[name]=(rel,s,e,lines)
   for i in range(s,e+1):
    m=CALL.search(lines[i])
    if m: incoming[m.group(1)].append((name,rel,i))
    q=MEM34.search(lines[i])
    if q: mem34.append((name,rel,s,e,i,q.groups(),lines))
 out=['Danika renderer-entry trace','===========================','',
      f'renderer={RENDER} incoming={len(incoming.get(RENDER,[]))}',
      f'entry={TARGET} incoming={len(incoming.get(TARGET,[]))}','']
 for key in [RENDER,TARGET]:
  out.append(f'Incoming callers of {key}')
  out.append('-'*(20+len(key)))
  for caller,rel,i in incoming.get(key,[]): out.append(f'{caller} {rel}:{i+1}')
  out.append('')
 if TARGET in defs:
  rel,s,e,lines=defs[TARGET]
  marks={i for i in range(s,e+1) if RENDER in lines[i] or MEM34.search(lines[i]) or CALL.search(lines[i])}
  out += [f'Complete {TARGET} body {rel}:{s+1}-{e+1}','-'*60]
  for i in range(s,e+1): out.append(f"{'>>>' if i in marks else '   '} {i+1:6d}: {lines[i]}")
  out.append('')
  calls=CALL.findall('\n'.join(lines[s:e+1]))
  out += ['Entry callees','-------------',', '.join(calls),'']
 else: out.append('TARGET definition not found')
 out += ['Repository functions accessing structure offset +0x34','--------------------------------------------------']
 # Rank +0x34 access functions if they call TARGET/RENDER or share direct callers.
 grouped=defaultdict(list)
 for row in mem34: grouped[(row[0],row[1],row[2],row[3],id(row[6]))].append(row)
 summaries=[]
 for rows in grouped.values():
  name,rel,s,e,_,_,lines=rows[0]; text='\n'.join(lines[s:e+1]); calls=CALL.findall(text)
  score=len(rows)*3 + (50 if TARGET in calls else 0)+(80 if RENDER in calls else 0)
  if name in {TARGET,RENDER}: score+=100
  summaries.append((score,name,rel,s,e,rows,lines,calls))
 summaries.sort(reverse=True,key=lambda x:x[0])
 for score,name,rel,s,e,rows,lines,calls in summaries[:80]:
  out.append(f'### score={score} {name} {rel}:{s+1}-{e+1} +0x34_accesses={len(rows)}')
  out.append('  calls='+', '.join(sorted(set(calls))[:25]))
  emitted=set()
  for _,_,_,_,mark,groups,_ in rows:
   lo=max(s,mark-14); hi=min(e,mark+24)
   for i in range(lo,hi+1):
    if i in emitted: continue
    emitted.add(i); out.append(f"{'>>>' if i==mark else '   '} {i+1:6d}: {lines[i]}")
   out.append('')
 out += ['Decision rule','-------------',
         'The next patch target must be upstream of the renderer if the descriptor already',
         'contains resolved visual resources. Follow the +0x34 descriptor producer and its',
         'class selectors before touching display-list code. Preserve enemy/front behavior.','']
 text='\n'.join(out); (ROOT/'danika-renderer-entry-report.txt').write_text(text,encoding='utf-8'); print(text); return 0
if __name__=='__main__': raise SystemExit(main())
