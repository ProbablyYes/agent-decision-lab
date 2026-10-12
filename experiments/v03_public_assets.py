"""Public GET metadata only. No auth, .env access, model inference or paid endpoint."""
import datetime
import json
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

OUT = Path('research/provider/v03/assets')
OUT.mkdir(parents=True,exist_ok=True)


def get(url):
    req = urllib.request.Request(url,headers={'User-Agent':'ADFL-StageA-public-audit'})
    with urllib.request.urlopen(req,timeout=30) as response:
        return response.read()


def main():
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links=[]
        def handle_starttag(self,tag,attrs):
            if tag=='a':
                self.links += [v for k,v in attrs if k=='href' and v and 'github.com/' in v]
    parser=Links(); parser.feed(get('https://mbjinx.github.io/DoVer_Web/').decode())
    (OUT/'dover_links.json').write_text(json.dumps(parser.links,indent=2),encoding='utf-8')
    index = []
    for repo in ('WangHanLinHenry/EVU','bennidict23/calibration-is-not-control',
                 'bethgelab/delta-belief-rl','alfworld/alfworld'):
        name = repo.replace('/','__')
        try:
            meta = json.loads(get('https://api.github.com/repos/'+repo))
            commit = json.loads(get('https://api.github.com/repos/'+repo+'/commits/'+meta['default_branch']))['sha']
            tree = json.loads(get('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1'))
            (OUT/(name+'.tree.json')).write_text(json.dumps(tree,indent=2),encoding='utf-8')
            paths = [x['path'] for x in tree['tree'] if x['type']=='blob']
            readme = next((p for p in paths if p.lower()=='readme.md'),None)
            if readme:
                (OUT/(name+'.README.md')).write_bytes(get('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+readme))
            if repo == 'alfworld/alfworld':
                for p in ('configs/base_config.yaml','alfworld/agents/environment/alfred_tw_env.py','doc/data.md','setup.py'):
                    if p in paths:
                        (OUT/(name+'__'+p.replace('/','__'))).write_bytes(get('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+p))
            interesting = [p for p in paths if any(k in p.lower() for k in ('trajectory','trajectories','checkpoint','result','split','config','dataset'))]
            row = dict(repo=repo,url='https://github.com/'+repo,commit=commit,default_branch=meta['default_branch'],
                license=(meta.get('license') or {}).get('spdx_id'),files=len(paths),asset_candidate_paths=interesting,
                tree_truncated=tree.get('truncated'),runtime_executed=False)
        except Exception as e:
            row = dict(repo=repo,error=type(e).__name__+': '+str(e),status='UNKNOWN')
        index.append(row)
    (OUT/'index.json').write_text(json.dumps(dict(retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        assets=index),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(index,ensure_ascii=True,indent=2))


if __name__ == '__main__':
    main()
