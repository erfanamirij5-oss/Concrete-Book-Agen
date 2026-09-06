from pathlib import Path
import json, re
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'source'/'بتن.docx'
MANIFEST=ROOT/'book_manifest.json'
STATE=ROOT/'state.json'
GUIDE=ROOT/'book'/'source_guidance'
GUIDE.mkdir(parents=True,exist_ok=True)

def clean(s): return re.sub(r'\s+',' ',s.strip())
paras=[clean(p.text) for p in Document(SRC).paragraphs if p.text and p.text.strip()]
# Source uses numbered section headings such as 1.1, 1.2 ...; preserve exact source order.
rx=re.compile(r'^\.?\s*(\d+\.\d+(?:\.\d+)*)\s*[-–—:]?\s*(.*)$')
heads=[]
seen=set()
for i,t in enumerate(paras):
    m=rx.match(t)
    if not m: continue
    sid,title=m.group(1),m.group(2).strip()
    if sid in seen or not title: continue
    seen.add(sid); heads.append((i,sid,title))
if not heads: raise SystemExit('No numbered section headings detected in source DOCX')
chapters={}
for n,(start,sid,title) in enumerate(heads):
    end=heads[n+1][0] if n+1<len(heads) else len(paras)
    excerpt='\n'.join(paras[start:end][:80])
    (GUIDE/f'{sid}.txt').write_text(excerpt,encoding='utf-8')
    ch=int(sid.split('.')[0])
    chapters.setdefault(ch,[]).append({'id':sid,'title':title,'status':'pending'})
manifest={'title':'بتن؛ فلسفه، جامعه و ماده','author':'عرفان امیری','outline_lock':True,'source':'source/بتن.docx','chapters':[{'chapter':c,'title':f'فصل {c}','sections':chapters[c]} for c in sorted(chapters)]}
if MANIFEST.exists():
    old=json.loads(MANIFEST.read_text(encoding='utf-8'))
    old_status={s['id']:s.get('status','pending') for ch in old.get('chapters',[]) for s in ch.get('sections',[])}
    for ch in manifest['chapters']:
        for s in ch['sections']: s['status']=old_status.get(s['id'],s['status'])
MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
if not STATE.exists():
    STATE.write_text(json.dumps({'status':'ready','next_section':heads[0][1],'last_completed_section':None,'notes':[]},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Bootstrap OK: {len(chapters)} chapters, {len(heads)} sections')
