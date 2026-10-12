"""Optional real OFFLINE ALFWorld reset probe; never calls an LLM.

Requires separately installed alfworld text dependencies and official downloaded
data. Missing dependencies are a recorded blocker, not a simulated successful reset.
"""
import argparse
import importlib.util
import json
from pathlib import Path


def run(config_path, split, seed):
    if importlib.util.find_spec('alfworld') is None:
        return {'status':'BLOCKED_DEPENDENCY','reset_verified':False,
                'reason':'alfworld not installed; Windows Jericho build also failed in dependency dry-run.'}
    import yaml
    from alfworld.agents.environment import get_environment
    config=yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
    config['general']['random_seed']=seed
    wrapper=get_environment('AlfredTWEnv')(config,train_eval=split)
    env=wrapper.init_env(batch_size=1)
    try:
        if hasattr(env,'seed'):
            env.seed(seed)
        obs,info=env.reset()
        return {'status':'RESET_OK','reset_verified':True,'split':split,'seed':seed,
                'observation':obs,'admissible_commands':info.get('admissible_commands'),
                'gamefile':info.get('extra.gamefile'),'llm_calls':0}
    finally:
        env.close()


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True)
    p.add_argument('--split',choices=['train','eval_in_distribution','eval_out_of_distribution'],default='eval_out_of_distribution')
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--output',default='results/v03/stageA/alfworld_reset_probe.json')
    a=p.parse_args()
    try:
        result=run(a.config,a.split,a.seed)
    except Exception as e:
        result={'status':'RESET_FAIL','reset_verified':False,'error':type(e).__name__+': '+str(e),'llm_calls':0}
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))
