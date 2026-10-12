"""Small unauthenticated source checks, independent of model inference."""
import json
import urllib.request
from pathlib import Path


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ADFL-public-audit'}),timeout=30) as r:
        return r.read()


out=Path('research/provider/v03/assets')
try:
    repo='microsoft/ACV'
    commit=json.loads(get('https://api.github.com/repos/'+repo+'/commits/main'))['sha']
    tree=json.loads(get('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1'))
    files=[x for x in tree['tree'] if x['path'].startswith('misc/DoVer/') and x['type']=='blob']
    result=dict(url='https://github.com/microsoft/ACV/tree/main/misc/DoVer',commit=commit,
                files=files,tree_truncated=tree.get('truncated'),runtime_executed=False)
    for p in ('misc/DoVer/README.md','misc/DoVer/AG2/DoVer/dover_readme.md'):
        if any(row['path']==p for row in files):
            name='DoVer.README.md' if p=='misc/DoVer/README.md' else 'DoVer.AG2.README.md'
            (out/name).write_bytes(get('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+p))
except Exception as e:
    result=dict(status='UNKNOWN',error=type(e).__name__+': '+str(e))
(out/'dover_asset_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'dover_files':len(result.get('files',[])),'status':result.get('status','TREE_VERIFIED')}))
