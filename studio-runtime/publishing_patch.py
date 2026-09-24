from pathlib import Path

server = Path('/app/server.py')
s = server.read_text(encoding='utf-8')

s = s.replace("def health(): return {'ok':True,'version':'0.3.2','engine':'semantic-storyboard','storage':'postgres' if _db_ready() else 'local'}",
              "def health(): return {'ok':True,'version':'0.4.0','engine':'semantic-storyboard','storage':'postgres' if _db_ready() else 'local','exports':['elearning','scorm12','mp4']}" )

marker = "@app.post('/api/projects/{pid}/export/elearning')\ndef export_elearning(pid:str):"
if marker not in s:
    raise SystemExit('eLearning export marker not found')

extra = """
@app.get('/api/projects/{pid}/fidelity-report')
def fidelity_report(pid:str):
    p=load_project(pid); val=validate_project(p); save_project(p)
    scene_report=[]
    for scene in p.get('scenes',[]):
        scene_report.append({
            'scene_id':scene.get('id'),
            'title':scene.get('title'),
            'purpose':scene.get('purpose'),
            'source_refs':scene.get('source_refs',[]),
            'locked_facts':scene.get('locked_facts',[]),
            'interaction':scene.get('interaction'),
            'visual_plan':scene.get('visual_plan'),
        })
    return {
        'project_id':p['id'], 'meta':p.get('meta',{}), 'engine_version':p.get('engine_version'),
        'coverage_pct':val.get('coverage_pct'), 'publishable':val.get('publishable'),
        'checks':val.get('checks',{}), 'issues':val.get('issues',{}),
        'coverage':p.get('coverage',[]), 'scenes':scene_report,
    }

def _scorm_manifest(title:str)->str:
    safe=html.escape(title or 'AI E-Learning Studio')
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<manifest identifier="AI_ELEARNING_STUDIO" version="1.0" xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2" xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">',
        '<organizations default="ORG1"><organization identifier="ORG1">',
        f'<title>{safe}</title><item identifier="ITEM1" identifierref="RES1"><title>{safe}</title></item>',
        '</organization></organizations>',
        '<resources><resource identifier="RES1" type="webcontent" adlcp:scormtype="sco" href="index.html">',
        '<file href="index.html"/><file href="project.json"/><file href="fidelity-report.json"/>',
        '</resource></resources></manifest>',
    ]
    return '\\n'.join(lines)

@app.post('/api/projects/{pid}/export/scorm')
def export_scorm(pid:str):
    p=load_project(pid); val=validate_project(p)
    if not val['publishable']: raise HTTPException(409,f"Chưa thể xuất: coverage {val['coverage_pct']}% hoặc còn lỗi chất lượng")
    out=EXPORTS/f'{pid}_SCORM12.zip'
    body=render_elearning_html(p)
    report=fidelity_report(pid)
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('imsmanifest.xml',_scorm_manifest(p['meta']['title']))
        z.writestr('index.html',body)
        z.writestr('project.json',json.dumps({'meta':p['meta'],'scenes':p['scenes'],'questions':p.get('questions',[]),'validation':p['validation']},ensure_ascii=False,indent=2))
        z.writestr('fidelity-report.json',json.dumps(report,ensure_ascii=False,indent=2))
    safe_name=re.sub(r'[^\\w\\-]+','_',p['meta']['title'])
    return FileResponse(out,filename=f'{safe_name}_SCORM12.zip',media_type='application/zip')
"""

s = s.replace(marker, extra + "\n" + marker)
server.write_text(s,encoding='utf-8')

index = Path('/app/static/index.html')
h = index.read_text(encoding='utf-8')
h = h.replace('<button class="tab" data-tab="narration">Lời thuyết minh</button>',
              '<button class="tab" data-tab="narration">Lời thuyết minh</button><button class="tab" data-tab="visuals">Hình ảnh</button>')
h = h.replace('<div class="exports"><button id="exportEL" class="btn secondary">🎓 XUẤT eLEARNING</button><button id="exportVideo" class="btn primary">🎬 XUẤT MP4</button></div>',
              '<div class="exports"><button id="exportEL" class="btn secondary">🎓 XUẤT eLEARNING</button><button id="exportSCORM" class="btn secondary">📦 XUẤT SCORM</button><button id="exportVideo" class="btn primary">🎬 XUẤT MP4</button></div>')
needle = "if(currentTab==='narration'){$('tabContent').innerHTML='<div class=\"scenes\">'+project.scenes.map((s,i)=>`<div class=\"scene\" style=\"grid-template-columns:48px 1fr 140px\"><div class=\"num\">${String(i+1).padStart(2,'0')}</div><div><h3>${escapeHtml(s.title)}</h3><p>${escapeHtml(s.narration||'')}</p></div><span class=\"chip\">${escapeHtml(s.visual_plan||'')}</span></div>`).join('')+'</div>';return}}"
replacement = "if(currentTab==='narration'){$('tabContent').innerHTML='<div class=\"scenes\">'+project.scenes.map((s,i)=>`<div class=\"scene\" style=\"grid-template-columns:48px 1fr 140px\"><div class=\"num\">${String(i+1).padStart(2,'0')}</div><div><h3>${escapeHtml(s.title)}</h3><p>${escapeHtml(s.narration||'')}</p></div><span class=\"chip\">${escapeHtml(s.purpose||'')}</span></div>`).join('')+'</div>';return}if(currentTab==='visuals'){$('tabContent').innerHTML='<div class=\"scenes\">'+project.scenes.map((s,i)=>`<div class=\"scene\" style=\"grid-template-columns:48px 1fr 160px\"><div class=\"num\">${String(i+1).padStart(2,'0')}</div><div><h3>${escapeHtml(s.title)}</h3><p><b>Kế hoạch hình ảnh:</b> ${escapeHtml(s.visual_plan||'Chưa có')}</p><p><b>Nguồn khóa:</b> ${escapeHtml((s.source_refs||[]).join(', ')||'Màn hình điều hướng')}</p></div><span class=\"chip ${s.source_refs?.length?'good':''}\">${escapeHtml((s.flags||[]).join(' • ')||s.purpose||'')}</span></div>`).join('')+'</div>';return}}"
if needle not in h:
    raise SystemExit('render narration marker not found')
h = h.replace(needle,replacement)
h = h.replace("toast(kind==='elearning'?'Đang đóng gói eLearning…':'Đang render MP4 Full HD…');",
              "toast(kind==='elearning'?'Đang đóng gói eLearning…':kind==='scorm'?'Đang đóng gói SCORM 1.2…':'Đang render MP4 Full HD…');")
h = h.replace("a.download=m?decodeURIComponent(m[1]):(kind==='video'?'Video.mp4':'eLearning.zip');",
              "a.download=m?decodeURIComponent(m[1]):(kind==='video'?'Video.mp4':kind==='scorm'?'SCORM12.zip':'eLearning.zip');")
h = h.replace("$('exportEL').onclick=()=>doExport('elearning');$('exportVideo').onclick=()=>doExport('video');",
              "$('exportEL').onclick=()=>doExport('elearning');$('exportSCORM').onclick=()=>doExport('scorm');$('exportVideo').onclick=()=>doExport('video');")
index.write_text(h,encoding='utf-8')
print('Applied publishing/SCORM/visuals patch')
