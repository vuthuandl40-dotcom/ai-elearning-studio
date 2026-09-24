from pathlib import Path

p = Path('/app/server.py')
s = p.read_text(encoding='utf-8')

old = '''def project_path(pid:str)->Path: return DATA/f'{pid}.json'
def load_project(pid:str)->dict[str,Any]:
    p=project_path(pid)
    if not p.exists(): raise HTTPException(404,'Không tìm thấy dự án')
    return json.loads(p.read_text(encoding='utf-8'))
def save_project(obj:dict[str,Any])->None:
    project_path(obj['id']).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
'''

new = '''DB_URL=os.getenv('DATABASE_URL','').strip()
try:
    import psycopg
except Exception:
    psycopg=None

def project_path(pid:str)->Path: return DATA/f'{pid}.json'

def _db_ready():
    return bool(DB_URL and psycopg)

def _ensure_db():
    if not _db_ready(): return
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE IF NOT EXISTS studio_runtime_projects (id TEXT PRIMARY KEY, payload JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())')
        conn.commit()

def load_project(pid:str)->dict[str,Any]:
    if _db_ready():
        _ensure_db()
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT payload FROM studio_runtime_projects WHERE id=%s',(pid,))
                row=cur.fetchone()
                if row:
                    payload=row[0]
                    return payload if isinstance(payload,dict) else json.loads(payload)
    fp=project_path(pid)
    if not fp.exists(): raise HTTPException(404,'Không tìm thấy dự án')
    return json.loads(fp.read_text(encoding='utf-8'))

def save_project(obj:dict[str,Any])->None:
    project_path(obj['id']).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    if _db_ready():
        _ensure_db()
        payload=json.dumps(obj,ensure_ascii=False)
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO studio_runtime_projects(id,payload,updated_at) VALUES (%s,%s::jsonb,NOW()) ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload, updated_at=NOW()', (obj['id'],payload))
            conn.commit()
'''

if old not in s:
    raise SystemExit('storage block target not found')
s=s.replace(old,new)

old_list = '''def list_projects():
    items=[]
    for f in sorted(DATA.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
        try:
            p=json.loads(f.read_text(encoding='utf-8')); items.append({'id':p['id'],'filename':p.get('filename',''),'meta':p.get('meta',{}),'validation':p.get('validation',{})})
        except Exception: pass
    return items[:50]
'''
new_list = '''def list_projects():
    items=[]
    if _db_ready():
        _ensure_db()
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT payload FROM studio_runtime_projects ORDER BY updated_at DESC LIMIT 50')
                for (payload,) in cur.fetchall():
                    p=payload if isinstance(payload,dict) else json.loads(payload)
                    items.append({'id':p['id'],'filename':p.get('filename',''),'meta':p.get('meta',{}),'validation':p.get('validation',{})})
        return items
    for f in sorted(DATA.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
        try:
            p=json.loads(f.read_text(encoding='utf-8')); items.append({'id':p['id'],'filename':p.get('filename',''),'meta':p.get('meta',{}),'validation':p.get('validation',{})})
        except Exception: pass
    return items[:50]
'''
if old_list not in s:
    raise SystemExit('list_projects target not found')
s=s.replace(old_list,new_list)

old_del = '''    project_path(pid).unlink(missing_ok=True)
    for f in EXPORTS.glob(f'{pid}_*'): f.unlink(missing_ok=True)
    return {'ok':True}
'''
new_del = '''    project_path(pid).unlink(missing_ok=True)
    if _db_ready():
        _ensure_db()
        with psycopg.connect(DB_URL) as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM studio_runtime_projects WHERE id=%s',(pid,))
            conn.commit()
    for f in EXPORTS.glob(f'{pid}_*'): f.unlink(missing_ok=True)
    return {'ok':True}
'''
if old_del not in s:
    raise SystemExit('delete target not found')
s=s.replace(old_del,new_del)

s=s.replace("def health(): return {'ok':True,'version':'0.3.0','engine':'semantic-storyboard'}",
            "def health(): return {'ok':True,'version':'0.3.2','engine':'semantic-storyboard','storage':'postgres' if _db_ready() else 'local'}")

p.write_text(s,encoding='utf-8')
print('Applied PostgreSQL persistence patch')
