from pathlib import Path
p=Path('/app/server.py')
s=p.read_text(encoding='utf-8')
old="'publishable':all(checks.values())"
new="'publishable':bool(checks.get('knowledge') and checks.get('coverage') and checks.get('data') and checks.get('assessment_grounding'))"
if old not in s:
    raise SystemExit('publishable expression not found')
s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
print('upgrade-v051-export-gate-ok')
