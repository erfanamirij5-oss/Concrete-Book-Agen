from pathlib import Path
import json, os
from pydantic import BaseModel, Field
from agents import Agent, Runner, WebSearchTool

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'book_manifest.json'; STATE=ROOT/'state.json'; SYS=ROOT/'agent'/'SYSTEM_PROMPT.md'
MODEL=os.getenv('BOOK_AGENT_MODEL','gpt-5.6-luna'); LIMIT=int(os.getenv('BOOK_AGENT_SECTIONS_PER_RUN','8')); RETRIES=int(os.getenv('BOOK_AGENT_MAX_RETRIES','3'))

class Review(BaseModel):
    approved: bool
    issues: list[str]=Field(default_factory=list)
    corrected_text: str=''

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def flat(m): return [(ch,s) for ch in m['chapters'] for s in ch['sections']]
def next_pending(m):
    for _,s in flat(m):
        if s.get('status')!='final': return s['id']
    return None

def find(m,sid):
    for ch,s in flat(m):
        if s['id']==sid:return ch,s
    raise KeyError(sid)

system=SYS.read_text(encoding='utf-8')
writer=Agent(name='Book Writer',model=MODEL,instructions=system+'\nمتن بخش خواسته‌شده را عمیق، منسجم و کتابی بنویس. فقط متن نهایی بخش را بده.')
reviewer=Agent(name='Book Reviewer',model=MODEL,instructions=system+'\nمتن را از نظر انطباق با عنوان، انسجام، صحت علمی/تاریخی و ادعاهای قابل بررسی کنترل کن. اگر لازم است با Web Search بررسی کن. اگر ایراد دارد corrected_text را کامل و اصلاح‌شده برگردان.',tools=[WebSearchTool(search_context_size='medium')],output_type=Review)

m=load(MANIFEST); st=load(STATE); processed=0
for _ in range(LIMIT):
    sid=next_pending(m)
    if not sid:
        st['status']='book_complete'; st['next_section']=None; save(STATE,st)
        (ROOT/'outputs').mkdir(exist_ok=True); save(ROOT/'outputs'/'github_status.json',{'status':'complete','processed':processed})
        print('BOOK COMPLETE'); break
    ch,s=find(m,sid); guide=(ROOT/'book'/'source_guidance'/f'{sid}.txt').read_text(encoding='utf-8')
    prompt=f"بخش {sid}: {s['title']}\nفصل: {ch['title']}\nراهنمای استخراج‌شده از منبع:\n{guide}\n\nاین بخش را بنویس."
    approved_text=None; issues=[]
    for attempt in range(RETRIES):
        draft=Runner.run_sync(writer,prompt,max_turns=10).final_output if approved_text is None else approved_text
        rev=Runner.run_sync(reviewer,f"عنوان: {sid} {s['title']}\nراهنما:\n{guide}\n\nمتن:\n{draft}",max_turns=12).final_output
        if rev.approved:
            approved_text=rev.corrected_text.strip() or str(draft).strip(); issues=rev.issues; break
        approved_text=rev.corrected_text.strip() or None; issues=rev.issues
        prompt=f"متن قبلی برای {sid} رد شد. با حفظ عنوان و محدوده منبع اصلاح کامل انجام بده. ایرادها: {issues}\nراهنما:\n{guide}\nمتن قبلی:\n{draft}"
    if not approved_text:
        st['status']='halted'; st['next_section']=sid; st.setdefault('notes',[]).append({'section':sid,'issues':issues}); save(STATE,st); raise SystemExit(30)
    out=ROOT/'book'/'final'; out.mkdir(parents=True,exist_ok=True); (out/f'{sid}.md').write_text(f"# {sid} {s['title']}\n\n{approved_text}\n",encoding='utf-8')
    s['status']='final'; processed+=1; st['last_completed_section']=sid; st['status']='ready'; st['next_section']=next_pending(m); save(MANIFEST,m); save(STATE,st)
    print('FINAL',sid,'NEXT',st['next_section'])
else:
    (ROOT/'outputs').mkdir(exist_ok=True); save(ROOT/'outputs'/'github_status.json',{'status':'continue','processed':processed,'next_section':st.get('next_section')})
