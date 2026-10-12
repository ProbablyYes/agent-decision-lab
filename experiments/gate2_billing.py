"""Read-only documented account check. Never emit credentials or account IDs."""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from adfl.agents.transport import local_key, NoRedirect


def check(label):
    destination=Path('results/gate2/billing'); destination.mkdir(parents=True,exist_ok=True)
    path=destination/(label+'.json')
    if path.exists():
        raise RuntimeError('billing evidence exists; do not overwrite')
    result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
        'endpoint':'https://api.ofox.ai/v1/user/balance',
        'documentation':'https://ofox.ai/docs/api/openapi/balance'}
    try:
        request=urllib.request.Request(result['endpoint'],headers={'Authorization':'Bearer '+local_key(),'Accept':'application/json'})
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=30) as response:
            body=json.loads(response.read()); result['status']=response.status
        result['account']={k:body.get(k) for k in ('is_active','balance','used','total','currency')}
    except Exception as exc:
        result.update(status=None,error=type(exc).__name__)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    check(sys.argv[1])
