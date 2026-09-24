from pathlib import Path
import re
p=Path('/app/server.py')
s=p.read_text(encoding='utf-8')

s=s.replace('from docx import Document\n', 'from docx import Document\nfrom docx.oxml.table import CT_Tbl\nfrom docx.oxml.text.paragraph import CT_P\nfrom docx.table import Table\nfrom docx.text.paragraph import Paragraph\n')

m=re.search(r"def extract_docx\(path\):.*?\n\ndef extract_pdf",s,re.S)
assert m
s=s[:m.start()]+'''def _iter_docx_blocks(doc):
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P): yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl): yield Table(child, doc)

def extract_docx(path):
    doc=Document(path); blocks=[]; lines=[]; idx=0; table_no=0
    for block in _iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            t=clean_text(block.text)
            if not t: continue
            idx+=1; lines.append(t); blocks.append({'id':f'b{idx}','text':t,'kind':'paragraph','order':idx,'style':getattr(getattr(block,'style',None),'name',None)})
        else:
            table_no+=1
            for ri,row in enumerate(block.rows,1):
                vals=[clean_text(c.text) for c in row.cells]
                t=' | '.join(v for v in vals if v)
                if not t: continue
                idx+=1; lines.append(t); blocks.append({'id':f'b{idx}','text':t,'kind':'table','order':idx,'table':table_no,'row':ri})
    return '\\n'.join(lines),blocks

def extract_pdf'''+s[m.end():]

m=re.search(r"def extract_pptx\(path\):.*?\n\ndef extract_text",s,re.S)
assert m
s=s[:m.start()]+'''def extract_pptx(path):
    prs=Presentation(path); lines=[]; blocks=[]; idx=0
    for si,slide in enumerate(prs.slides,1):
        for shape_no,shape in enumerate(slide.shapes,1):
            if hasattr(shape,'text'):
                t=clean_text(shape.text)
                if t:
                    idx+=1; lines.append(t); blocks.append({'id':f'slide{si}-b{idx}','text':t,'kind':'slide_text','slide':si,'shape':shape_no,'order':idx})
            if getattr(shape,'shape_type',None)==13:
                idx+=1; blocks.append({'id':f'slide{si}-media{idx}','text':f'[HÌNH ẢNH GỐC TRÊN SLIDE {si}]','kind':'image','slide':si,'shape':shape_no,'order':idx})
        try: notes=clean_text(slide.notes_slide.notes_text_frame.text)
        except Exception: notes=''
        if notes:
            idx+=1; lines.append(notes); blocks.append({'id':f'slide{si}-notes{idx}','text':notes,'kind':'speaker_notes','slide':si,'order':idx})
    return '\\n'.join(lines),blocks

def extract_text'''+s[m.end():]

insert_at=s.index('\ndef validate_project(p):')
qfunc='''

_STOPWORDS={'những','chúng','trong','được','không','người','thông','trường','nội','dung','hoạt','động','giáo','viên','học','sinh','một','các','và','hoặc','với','theo','của','cho','này','đó','đây','khi','để','từ'}

def _sentence_candidates(blocks):
    rows=[]
    for b in blocks:
        if b.get('kind')=='image': continue
        for part in re.split(r'(?<=[.!?…])\\s+|\\n+|\\s*\\|\\s*', b.get('text','')):
            t=clean_text(strip_md(part))
            if 18<=len(t)<=220 and not is_heading(t): rows.append((b['id'],t))
    out=[]; seen=set()
    for ref,t in rows:
        k=norm(t)
        if k and k not in seen: seen.add(k); out.append((ref,t))
    return out

def _blank_from_statement(statement):
    words=re.findall(r"[^\\W\\d_]{6,}",statement,flags=re.UNICODE)
    cand=[w for w in words if w.lower() not in _STOPWORDS]
    if not cand: return None
    ans=max(cand,key=len); q=re.sub(rf'\\b{re.escape(ans)}\\b','_____',statement,count=1)
    return (q,ans) if q!=statement else None

def build_question_bank(blocks,classified,limit=10):
    candidates=_sentence_candidates(blocks); bank=[]; used=set(); explicit=[]
    for b in blocks:
        t=clean_text(strip_md(b.get('text',''))); low=t.lower()
        if '?' in t or re.match(r'^(câu\\s*\\d+[.:)]?|hỏi\\b|theo em\\b|hãy\\b)',low): explicit.append(b)
    for ref,t in candidates:
        if len(bank)>=3: break
        if '?' in t: continue
        bank.append({'id':f'q{len(bank)+1:02d}','type':'true_false','level':'Nhận biết','prompt':'Phát biểu sau có đúng theo nội dung giáo án gốc không?','statement':t,'answer':True,'options':['Đúng','Sai'],'source_refs':[ref],'feedback':'Phát biểu này được trích trực tiếp từ nguồn.','auto_score':True}); used.add((ref,t))
    for ref,t in candidates:
        if len([q for q in bank if q['level']=='Thông hiểu'])>=4: break
        if (ref,t) in used or '?' in t: continue
        x=_blank_from_statement(t)
        if not x: continue
        qtxt,ans=x; bank.append({'id':f'q{len(bank)+1:02d}','type':'fill_blank','level':'Thông hiểu','prompt':qtxt,'answer':ans,'source_refs':[ref],'feedback':'Điền đúng từ/cụm từ đã xuất hiện trong giáo án gốc.','auto_score':True}); used.add((ref,t))
    for b in explicit:
        if len(bank)>=limit: break
        t=clean_text(strip_md(b.get('text','')))
        if not t: continue
        bank.append({'id':f'q{len(bank)+1:02d}','type':'open_response','level':'Vận dụng' if any(x in t.lower() for x in ['giải thích','phân tích','đề xuất','vận dụng','liên hệ','nhận xét']) else 'Thông hiểu','prompt':t,'answer':None,'source_refs':[b['id']],'feedback':'Đối chiếu với yêu cầu và nội dung trong giáo án gốc. [CẦN GIÁO VIÊN XÁC NHẬN ĐÁP ÁN]','auto_score':False,'needs_teacher_key':True})
    for ref,t in candidates:
        if len(bank)>=limit: break
        pool=[x for r,x in candidates if r!=ref and x!=t][:12]; opts=[t]+pool[:3]
        if len(opts)<2: continue
        shift=(len(bank)*2)%len(opts); opts=opts[shift:]+opts[:shift]
        bank.append({'id':f'q{len(bank)+1:02d}','type':'mcq','level':'Thông hiểu','prompt':'Phát biểu nào dưới đây được trích đúng từ nội dung nguồn của bài?','options':opts,'answer':t,'source_refs':[ref],'feedback':'Đáp án đúng là phát biểu xuất hiện trong nguồn; phương án còn lại lấy từ phần khác của giáo án.','auto_score':True})
    counts={k:sum(1 for q in bank if q['level']==k) for k in ['Nhận biết','Thông hiểu','Vận dụng']}; warnings=[]
    if counts['Vận dụng']<3: warnings.append('[CẦN GIÁO VIÊN XÁC NHẬN] Nguồn chưa đủ 3 câu vận dụng có đáp án/tiêu chí rõ; hệ thống không tự bịa thêm.')
    if len(bank)<10: warnings.append(f'[CẦN GIÁO VIÊN XÁC NHẬN] Chỉ tạo được {len(bank)}/10 câu bám nguồn.')
    return {'items':bank[:limit],'distribution':counts,'target_distribution':{'Nhận biết':3,'Thông hiểu':4,'Vận dụng':3},'warnings':warnings}
'''
s=s[:insert_at]+qfunc+s[insert_at:]

old="checks={'knowledge':bool(scenes),'coverage':not missing,'data':not number_issues,'language':not generic and not duplicates,'multimedia':not empty and all(clean_text(s.get('visual_plan','')) for s in scenes)}"
new="""qbank=p.get('question_bank',{}).get('items',[]); valid_refs=set(block_by); q_issues=[]
    for q in qbank:
        if not q.get('source_refs') or any(r not in valid_refs for r in q.get('source_refs',[])): q_issues.append(q.get('id'))
    checks={'knowledge':bool(scenes),'coverage':not missing,'data':not number_issues,'language':not generic and not duplicates,'multimedia':not empty and all(clean_text(s.get('visual_plan','')) for s in scenes),'assessment_grounding':not q_issues}"""
assert old in s
s=s.replace(old,new)
s=s.replace("'number_issues':number_issues,'quality_score':max(0.0,score)}", "'number_issues':number_issues,'question_grounding_issues':q_issues,'quality_score':max(0.0,score)}")

s=s.replace("p={'id':pid,'filename':file.filename,'source_path':str(dst),'source_text':text,'blocks':blocks,**analysis}\n    validate_project(p); save_project(p)", "p={'id':pid,'filename':file.filename,'source_path':str(dst),'source_text':text,'blocks':blocks,**analysis}\n    p['question_bank']=build_question_bank(blocks,p.get('classified',{}),10)\n    validate_project(p); save_project(p)")
s=s.replace("return {k:p[k] for k in ['id','filename','meta','classified','coverage','scenes','validation']}", "return {k:p[k] for k in ['id','filename','meta','classified','coverage','scenes','question_bank','validation']}")

start=s.index('def render_elearning_html(p):')
end=s.index("\n@app.get('/api/projects/{pid}/fidelity-report')",start)
renderer=r"""def render_elearning_html(p):
    scenes=json.dumps(p['scenes'],ensure_ascii=False).replace('</','<\\/')
    questions=json.dumps(p.get('question_bank',{}),ensure_ascii=False).replace('</','<\\/')
    title=html.escape(p['meta']['title'])
    return f'''<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
body{{margin:0;font-family:Arial;background:#eef2f7;color:#172033}}.wrap{{max-width:1100px;margin:auto;padding:24px}}.stage{{min-height:590px;background:linear-gradient(135deg,#13203f,#30456f);border-radius:22px;color:white;padding:5%;display:flex;flex-direction:column;justify-content:center;box-shadow:0 18px 50px #0002}}h1{{font-size:40px;margin:0 0 14px}}p{{font-size:18px;line-height:1.45}}.meta{{opacity:.8}}.interaction,.quiz{{margin-top:12px;padding:14px;border:1px solid #ffffff33;background:#ffffff14;border-radius:14px}}.feedback{{display:none;margin-top:10px;padding:12px;background:#eafaf4;color:#155f49;border-radius:10px}}.controls{{display:flex;justify-content:space-between;gap:10px;margin-top:18px}}button{{padding:12px 18px;border:0;border-radius:12px;font-weight:700;cursor:pointer}}.primary{{background:#6d4aff;color:white}}.bar{{height:8px;background:#d8deea;border-radius:99px;overflow:hidden;margin:14px 0}}#fill{{height:100%;background:#6d4aff}}.option{{display:block;padding:9px 11px;margin:7px 0;background:#fff;color:#172033;border-radius:10px}}input[type=text],textarea{{width:100%;padding:11px;border-radius:10px;border:1px solid #ccd3df}}.result{{background:white;border:1px solid #dce2ec;border-radius:16px;padding:18px;margin-top:14px}}.good{{color:#15805f}}.warn{{color:#a36b00}}
</style></head><body><div class="wrap"><div class="bar"><div id="fill"></div></div><div class="stage"><div class="meta" id="meta"></div><h1 id="title"></h1><p id="desc"></p><div class="interaction" id="sceneInteraction"><b id="inter"></b><p id="prompt"></p><button onclick="toggleFeedback()">Xem phản hồi</button><div class="feedback" id="feedback"></div></div><div class="quiz" id="quizBox" style="display:none"></div></div><div class="controls"><button onclick="prev()">← Quay lại</button><button id="nextBtn" class="primary" onclick="next()">Tiếp tục →</button></div><div id="result" class="result" style="display:none"></div></div><script>
const scenes={scenes},qb={questions};let i=0,qIndex=-1,answers={{}},completedOpen={{}};
function findAPI(win){{let tries=0;while(win&&tries<12){{if(win.API)return win.API;win=win.parent;tries++}}return null}}const API=findAPI(window);try{{API&&API.LMSInitialize('')}}catch(e){{}}
function scormSet(k,v){{try{{API&&API.LMSSetValue(k,String(v));API&&API.LMSCommit('')}}catch(e){{}}}}
function esc(s){{return String(s??'').replace(/[&<>\"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}}[c]))}}
function showScene(){{const s=scenes[i];qIndex=-1;quizBox.style.display='none';sceneInteraction.style.display='block';title.textContent=s.title;desc.textContent=s.desc||'';inter.textContent=s.interaction||'';prompt.textContent=s.interaction_prompt||'';feedback.textContent=s.feedback||'Không có phản hồi riêng.';feedback.style.display='none';meta.textContent=(i+1)+' / '+scenes.length+' · '+(s.phase||s.type||'');fill.style.width=((i+1)/(scenes.length+qb.items.length)*100)+'%';nextBtn.textContent=i===scenes.length-1?(qb.items.length?'Làm đánh giá →':'Hoàn thành'):'Tiếp tục →'}}
function toggleFeedback(){{feedback.style.display=feedback.style.display==='block'?'none':'block'}}
function renderQuestion(){{const q=qb.items[qIndex];sceneInteraction.style.display='none';quizBox.style.display='block';title.textContent='Đánh giá cuối bài';desc.textContent='Câu '+(qIndex+1)+' / '+qb.items.length+' · '+q.level;meta.textContent='ĐÁNH GIÁ';let h='<b>'+esc(q.prompt)+'</b>';if(q.statement)h+='<p>'+esc(q.statement)+'</p>';if(q.type==='true_false'||q.type==='mcq'){{h+=(q.options||[]).map(o=>'<label class="option"><input type="radio" name="q" value="'+esc(o)+'"> '+esc(o)+'</label>').join('')}}else if(q.type==='fill_blank'){{h+='<p><input id="textAns" type="text" placeholder="Nhập câu trả lời"></p>'}}else{{h+='<p><textarea id="textAns" rows="4" placeholder="Nhập câu trả lời của em"></textarea></p>'}}h+='<button class="primary" onclick="checkAnswer()">Kiểm tra</button><div id="qfb" class="feedback"></div>';quizBox.innerHTML=h;fill.style.width=((scenes.length+qIndex+1)/(scenes.length+qb.items.length)*100)+'%';nextBtn.textContent=qIndex===qb.items.length-1?'Xem kết quả':'Câu tiếp theo →'}}
function normv(x){{return String(x??'').trim().toLowerCase()}}
function checkAnswer(){{const q=qb.items[qIndex],fb=document.getElementById('qfb');let val='';const radio=document.querySelector('input[name=q]:checked');if(radio)val=radio.value;else if(document.getElementById('textAns'))val=document.getElementById('textAns').value;if(q.auto_score){{let ok=false;if(q.type==='true_false')ok=(val==='Đúng')===Boolean(q.answer);else ok=normv(val)===normv(q.answer);answers[q.id]=ok;fb.innerHTML=(ok?'<b>✓ Chính xác.</b> ':'<b>Chưa đúng.</b> ')+esc(q.feedback||'');if(!ok)fb.innerHTML+='<br><small>Gợi ý: xem lại nguồn '+esc((q.source_refs||[]).join(', '))+'. Em có thể sửa và thử lại.</small>'}}else{{completedOpen[q.id]=Boolean(val.trim());fb.innerHTML=esc(q.feedback||'')+'<br><b>Phần này không tự chấm vì nguồn không có đáp án khóa.</b>'}}fb.style.display='block';updateScore()}}
function updateScore(){{const auto=qb.items.filter(q=>q.auto_score),correct=auto.filter(q=>answers[q.id]===true).length,attempted=auto.filter(q=>q.id in answers).length,pct=auto.length?Math.round(correct/auto.length*100):0;scormSet('cmi.core.score.raw',pct);scormSet('cmi.core.score.min',0);scormSet('cmi.core.score.max',100);return{{auto,correct,attempted,pct}}}}
function finish(){{const r=updateScore(),open=qb.items.filter(q=>!q.auto_score),doneOpen=open.filter(q=>completedOpen[q.id]).length;result.style.display='block';result.innerHTML='<h3>Kết quả tự kiểm</h3><p><b>'+r.correct+'/'+r.auto.length+'</b> câu tự chấm đúng · <b>'+r.pct+'%</b></p><p>'+doneOpen+'/'+open.length+' câu mở đã làm.</p>'+(qb.warnings||[]).map(x=>'<p class="warn">'+esc(x)+'</p>').join('');scormSet('cmi.core.lesson_status','completed');scormSet('cmi.core.lesson_location','finished');try{{API&&API.LMSFinish('')}}catch(e){{}}}}
function next(){{if(qIndex>=0){{if(qIndex<qb.items.length-1){{qIndex++;renderQuestion()}}else finish();return}}if(i<scenes.length-1){{i++;showScene()}}else if(qb.items.length){{qIndex=0;renderQuestion()}}else finish()}}
function prev(){{if(qIndex>0){{qIndex--;renderQuestion();return}}if(qIndex===0){{qIndex=-1;i=scenes.length-1;showScene();return}}if(i>0){{i--;showScene()}}}}
window.addEventListener('beforeunload',()=>{{try{{API&&API.LMSCommit('')}}catch(e){{}}}});showScene();
</script></body></html>'''
"""
s=s[:start]+renderer+s[end:]

s=s.replace("'number_issues':val.get('number_issues',[])},'coverage'", "'number_issues':val.get('number_issues',[]),'question_grounding_issues':val.get('question_grounding_issues',[])},'question_bank':p.get('question_bank',{}),'coverage'")
s=s.replace("{'meta':p['meta'],'scenes':p['scenes'],'validation':p['validation']}", "{'meta':p['meta'],'scenes':p['scenes'],'question_bank':p.get('question_bank',{}),'validation':p['validation']}")

needle="""            fp=work/f'frame_{i:03d}.png'; img.save(fp); frames.append(fp)
        concat=work/'concat.txt'
"""
assert needle in s
replacement="""            fp=work/f'frame_{i:03d}.png'; img.save(fp); frames.append((fp,3.0))
        for qi,q in enumerate(p.get('question_bank',{}).get('items',[])[:10],1):
            img=Image.new('RGB',(1920,1080),(18,30,56)); d=ImageDraw.Draw(img); d.rounded_rectangle((85,75,1835,1000),radius=34,fill=(34,51,88))
            d.text((135,115),f'ĐÁNH GIÁ · Câu {qi:02d}',font=sf,fill=(190,205,230)); y=205
            prompt=q.get('prompt','')+((' '+q.get('statement','')) if q.get('statement') else '')
            for line in wrap_text(d,prompt,tf,1580)[:6]: d.text((150,y),line,font=tf,fill='white'); y+=70
            d.text((150,875),'5 giây suy nghĩ',font=bf,fill=(220,225,245)); qfp=work/f'quiz_{qi:02d}_q.png'; img.save(qfp); frames.append((qfp,5.0))
            img2=img.copy(); d2=ImageDraw.Draw(img2); d2.rounded_rectangle((135,760,1785,960),radius=22,fill=(24,114,86))
            if q.get('auto_score'):
                ans='Đáp án: '+('Đúng' if q.get('type')=='true_false' and q.get('answer') else str(q.get('answer') or ''))
            else: ans='Đáp án/tiêu chí: CẦN GIÁO VIÊN XÁC NHẬN'
            yy=790
            for line in wrap_text(d2,ans+' — '+q.get('feedback',''),bf,1540)[:4]: d2.text((175,yy),line,font=bf,fill='white'); yy+=42
            afp=work/f'quiz_{qi:02d}_a.png'; img2.save(afp); frames.append((afp,3.0))
        concat=work/'concat.txt'
"""
s=s.replace(needle,replacement)
s=s.replace("for fp in frames: f.write(f\"file '{fp.as_posix()}'\\nduration 3.0\\n\")\n            f.write(f\"file '{frames[-1].as_posix()}'\\n\")", "for fp,dur in frames: f.write(f\"file '{fp.as_posix()}'\\nduration {dur}\\n\")\n            f.write(f\"file '{frames[-1][0].as_posix()}'\\n\")")

s=s.replace("'version':'0.4.0'", "'version':'0.5.0'")
s=s.replace("'exports':['elearning','scorm12','mp4']", "'exports':['elearning','scorm12','mp4'],'features':['ordered-source','grounded-assessment','scorm-score','video-question-countdown']")

p.write_text(s,encoding='utf-8')
print('patched v0.5')

ui=Path('/app/static/index.html')
h=ui.read_text(encoding='utf-8')
old="""if(currentTab==='questions'){const qs=(project.classified.questions||[]);$('tabContent').innerHTML=qs.length?'<div class=\"scenes\">'+qs.map((q,i)=>`<div class=\"scene\" style=\"grid-template-columns:48px 1fr 110px\"><div class=\"num\">${String(i+1).padStart(2,'0')}</div><div><h3>Câu hỏi nguồn</h3><p>${escapeHtml(q.text)}</p></div><span class=\"chip good\">Giữ nguyên</span></div>`).join('')+'</div>':'<div class=\"empty\">Không phát hiện câu hỏi riêng trong nguồn.</div>';return}"""
new="""if(currentTab==='questions'){const qb=project.question_bank||{items:[],warnings:[],distribution:{}};const qs=qb.items||[];let head=`<div class=\"callout\" style=\"margin:0 0 12px\"><b>Ngân hàng đánh giá bám nguồn:</b> ${qs.length}/10 câu · Nhận biết ${qb.distribution?.['Nhận biết']||0} · Thông hiểu ${qb.distribution?.['Thông hiểu']||0} · Vận dụng ${qb.distribution?.['Vận dụng']||0}</div>`+(qb.warnings||[]).map(w=>`<div class=\"callout\" style=\"background:#fff8e8;border-color:#f0d99b;color:#8a6500;margin:0 0 8px\">${escapeHtml(w)}</div>`).join('');$('tabContent').innerHTML=head+(qs.length?'<div class=\"scenes\">'+qs.map((q,i)=>`<div class=\"scene\" style=\"grid-template-columns:48px 1fr 130px 140px\"><div class=\"num\">${String(i+1).padStart(2,'0')}</div><div><h3>${escapeHtml(q.type==='open_response'?'Câu mở':q.type==='fill_blank'?'Điền khuyết':q.type==='true_false'?'Đúng / Sai':'Trắc nghiệm')}</h3><p style=\"white-space:normal\">${escapeHtml(q.prompt||'')}${q.statement?' — '+escapeHtml(q.statement):''}</p></div><span class=\"chip\">${escapeHtml(q.level||'')}</span><span class=\"chip ${q.auto_score?'good':''}\">${q.auto_score?'Tự chấm':'GV xác nhận'} · ${escapeHtml((q.source_refs||[]).join(', '))}</span></div>`).join('')+'</div>':'<div class=\"empty\">Nguồn chưa đủ dữ liệu để tạo câu hỏi bám nguồn.</div>');return}"""
if old not in h:
    raise SystemExit('questions renderer target missing')
h=h.replace(old,new)
ui.write_text(h,encoding='utf-8')
print('upgrade-v05-ok')
