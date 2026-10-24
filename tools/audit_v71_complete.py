#!/usr/bin/env python3
from pathlib import Path
import re,csv,json,hashlib,collections,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/mnt/data/ob64_final_release')
SRC=(ROOT/'src/ptbr_runtime.c').read_text(encoding='utf-8')
BSRC=(BASE/'src/ptbr_runtime.c').read_text(encoding='utf-8')
arr=re.compile(r'static const unsigned char (a(\d+)_(en|pt)_(\d+))\[\]=\{(.*?)\};',re.S)
def parse_dialogues(s):
 d={}
 for m in arr.finditer(s):
  _,a,l,j,b=m.groups(); d[(int(a),int(j),l)]=bytes(int(x,16) for x in re.findall(r'0x([0-9A-Fa-f]{2})',b))
 return d
B=parse_dialogues(BSRC); C=parse_dialogues(SRC)
ptkeys=sorted(k for k in C if k[2]=='pt'); enkeys=sorted(k for k in C if k[2]=='en')
changed=[k for k in ptkeys if B.get(k)!=C.get(k)]
ctrl=re.compile(rb'@(?:T[0-9A-Fa-f]{3}|t[0-9A-Fa-f]{3}|w[0-9A-Fa-f]{4}|F[0-9A-Fa-f]{3}|&[0-9A-Fa-f]{2}|%[0-9A-Fa-f]|S0|[12]|n|p|c|a|s|k|/|#|-|x|l.|r|A|=|\*|u|z.|m|!.|\+)|\{T\d+\}')
ctrl_m=[k for k in changed if ctrl.findall(B[k])!=ctrl.findall(C[k])]
ptlen={(a,j):len(v) for (a,j,l),v in C.items() if l=='pt'}
pm=[]
for m in re.finditer(r'\{\s*a(\d+)_en_(\d+),\s*(\d+)u,\s*a\1_pt_\2,\s*(\d+)u\s*\}',SRC):
 a,j,_,plen=map(int,m.groups()); actual=ptlen.get((a,j));
 if actual!=plen: pm.append((a,j,plen,actual))
assets=[]; over=[]
for m in re.finditer(r'\{\s*0x([0-9A-Fa-f]+)u,\s*0x([0-9A-Fa-f]+)u,\s*0x([0-9A-Fa-f]+)u,\s*(\d+)u,\s*a(\d+)_offsets,\s*a\5_patches\s*\}',SRC):
 cap=int(m.group(3),16); cnt=int(m.group(4)); a=int(m.group(5)); used=cnt*4+sum(ptlen[(a,j)]+1 for j in range(cnt)); assets.append((a,cap,used));
 if used>cap: over.append((a,used,cap))

def divgroups(D):
 g=collections.defaultdict(set)
 for (a,j,l),v in D.items():
  if l=='en' and (a,j,'pt') in D:g[v].add(D[(a,j,'pt')])
 return sum(1 for x in g.values() if len(x)>1)
# Story CSV validation
spec=[('MEMORIES_INDEX','memories_index_translation_v45.csv',200),('PEOPLE_PROFILES','people_profiles_translation_v45.csv',1201),('RECOLLECTIONS','recollections_translation_v45.csv',1415),('HISTORY_LORE','history_lore_translation_v45.csv',509)]
story={}; total_rows=total_pending=total_over=total_nonascii=0
for label,fn,expect in spec:
 rows=list(csv.DictReader((ROOT/'story_complete'/fn).open(encoding='utf-8')))
 pending=ov=nonascii=0
 for r in rows:
  pt=r.get('pt','')
  if not pt: pending+=1
  try: cap=int(r['capacity'],0)
  except: cap=int(r['capacity'])
  b=pt.encode('utf-8')
  if len(b)>cap:ov+=1
  if any(x>=128 for x in b):nonascii+=1
 story[label]={'rows':len(rows),'expected_rows':expect,'pending':pending,'overflow':ov,'nonascii':nonascii}
 total_rows+=len(rows);total_pending+=pending;total_over+=ov;total_nonascii+=nonascii
# Finalizer report
rep=json.loads((ROOT/'story_complete/STORY_COMPLETE_REPORT_V71.json').read_text())
report_banks={b['asset_label']:b for b in rep['banks']}
# Include array hashes
inc=(ROOT/'src/ptbr_v71_story_complete.inc').read_text()
def cbytes(name):
 m=re.search(r'static const unsigned char '+re.escape(name)+r'\[\]=\{(.*?)\};',inc,re.S)
 if not m:return None
 return bytes(int(x,16) for x in re.findall(r'0x([0-9A-Fa-f]{2})',m.group(1)))
inc_checks={}
for label,stem in [('MEMORIES_INDEX','memories_index'),('PEOPLE_PROFILES','people_profiles'),('RECOLLECTIONS','recollections'),('HISTORY_LORE','history_lore')]:
 b=report_banks[label]
 guard=cbytes(f'v71_{stem}_guard'); pt=cbytes(f'v71_{stem}_pt')
 inc_checks[label]={
  'guard_len':len(guard or b''),'pt_len':len(pt or b''),
  'guard_sha256':hashlib.sha256(guard or b'').hexdigest(), 'guard_hash_ok':guard is not None and hashlib.sha256(guard).hexdigest()==b['retail_lz_sha256'],
  'pt_sha256':hashlib.sha256(pt or b'').hexdigest(), 'pt_hash_ok':pt is not None and hashlib.sha256(pt).hexdigest()==b['pt_lz_sha256'],
 }
# Historical include identity versus v1.0 base
oldincs=sorted((BASE/'src').glob('ptbr_v*.inc'))
compared=changed_inc=missing_inc=0
for p in oldincs:
 q=ROOT/'src'/p.name
 if not q.exists(): missing_inc+=1; continue
 compared+=1
 if p.read_bytes()!=q.read_bytes():changed_inc+=1
# Fresh binary facts
sections=(ROOT/'build/sections_v71_complete.txt').read_text(errors='ignore')
rel=(ROOT/'build/relocs_v71_complete.txt').read_text(errors='ignore')
nm=(ROOT/'build/nm_v71_complete.txt').read_text(errors='ignore')
dis=(ROOT/'build/disasm_v71_complete.txt').read_text(errors='ignore')
def secsize(name):
 m=re.search(r'\]\s+'+re.escape(name)+r'\s+\S+\s+\S+\s+\S+\s+([0-9A-Fa-f]+)',sections)
 return int(m.group(1),16) if m else 0 if name=='.sbss' else None
rtypes=['R_MIPS_32','R_MIPS_26','R_MIPS_HI16','R_MIPS_LO16','R_MIPS_GPREL16','R_MIPS_GOT16','R_MIPS_CALL16','R_MIPS_LITERAL']
counts={k:len(re.findall(r'\b'+k+r'\b',rel)) for k in rtypes}
# hashes / A-B
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
mod=ROOT/'mod.toml'; mt=mod.read_text()
result={
 'result':'PASS','release':'v1.1 COMPLETE','dialogues_pt':len(ptkeys),'dialogues_en':len(enkeys),'assets':len(assets),
 'dialogues_changed_vs_v1_0':len(changed),'control_mismatches':len(ctrl_m),'pt_len_mismatches':len(pm),'dialogue_overflows':len(over),
 'duplicate_divergence_groups_base':divgroups(B),'duplicate_divergence_groups_v71':divgroups(C),
 'story_rows_total':total_rows,'story_pending_total':total_pending,'story_overflow_total':total_over,'story_nonascii_total':total_nonascii,'story_banks':story,
 'story_report_all_exact_retail':rep.get('all_exact_retail'),'story_report_all_translated':rep.get('all_translated'),'story_report_include_emitted':rep.get('integration_include_emitted'),
 'story_report_rom_sha256':rep.get('rom_sha256'),'story_bank_runtime_arrays':inc_checks,
 'historical_includes_compared':compared,'historical_includes_changed':changed_inc,'historical_includes_missing':missing_inc,
 'v71_include_hooked':SRC.count('patch_v71_story_banks_source_if_original(src);')==1,
 'version_ok':'version = "1.1.0"' in mt,'minimum_recomp_version_ok':'minimum_recomp_version = "0.1.0"' in mt,
 'data_size':secsize('.data'),'bss_size':secsize('.bss'),'sbss_size':secsize('.sbss'),
 'relocations_total':sum(counts[k] for k in ['R_MIPS_32','R_MIPS_26','R_MIPS_HI16','R_MIPS_LO16']),'relocation_counts':counts,
 'forbidden_relocations':sum(counts[k] for k in ['R_MIPS_GPREL16','R_MIPS_GOT16','R_MIPS_CALL16','R_MIPS_LITERAL']),
 'heap_symbols':len(re.findall(r'\b(?:malloc|calloc|realloc|free)\b',nm)),'gp_references':dis.count('$gp'),
 'hooks_in_source':all(x in SRC for x in ['RECOMP_HOOK_RETURN("func_80079950")','RECOMP_HOOK("func_80072944")','RECOMP_HOOK("func_8007A110")']),
 'object_ab_identical':(ROOT/'build/v71_ab/ptbr_runtime_a.o').read_bytes()==(ROOT/'build/v71_ab/ptbr_runtime_b.o').read_bytes(),
 'elf_ab_identical':(ROOT/'build/v71_ab/mod_a.elf').read_bytes()==(ROOT/'build/v71_ab/mod_b.elf').read_bytes(),
 'elf_matches_ab':(ROOT/'build/mod.elf').read_bytes()==(ROOT/'build/v71_ab/mod_a.elf').read_bytes(),
 'elf_sha256':sha(ROOT/'build/mod.elf'),'object_sha256':sha(ROOT/'build/ptbr_runtime.o')
}
fail= any([
 len(ptkeys)!=4569,len(enkeys)!=4569,len(assets)!=348,bool(changed),bool(ctrl_m),bool(pm),bool(over),divgroups(B)!=divgroups(C),
 total_rows!=3325,total_pending!=0,total_over!=0,total_nonascii!=0,
 rep.get('all_exact_retail') is not True,rep.get('all_translated') is not True,rep.get('integration_include_emitted') is not True,
 any(not (b.get('roundtrip_exact') and b.get('fits_retail') and b.get('pending_rows')==0) for b in rep['banks']),
 any(not (x['guard_hash_ok'] and x['pt_hash_ok']) for x in inc_checks.values()),
 changed_inc!=0,missing_inc!=0,not result['v71_include_hooked'],not result['version_ok'],not result['minimum_recomp_version_ok'],
 result['data_size']!=0,result['bss_size']!=0,result['sbss_size']!=0,result['forbidden_relocations']!=0,result['heap_symbols']!=0,result['gp_references']!=0,
 not result['hooks_in_source'],not result['object_ab_identical'],not result['elf_ab_identical'],not result['elf_matches_ab']
])
if fail:result['result']='FAIL'
(ROOT/'build/final_audit_v71_complete.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,indent=2,ensure_ascii=False))
raise SystemExit(2 if fail else 0)
