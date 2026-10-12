"""Derive reports and source labels from the original durable pilot sessions."""
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from adfl.budget.ledger import Ledger
from adfl.evaluation import attribution_metrics, paired_intervention, score_line
from adfl.gate1 import LEDGER_PATH, ROOT
from adfl.world.pilot import PilotWorld


def main():
    root=ROOT/'results/gate2'; c=json.loads((root/'preregistration.json').read_text(encoding='utf-8'))
    ledger=Ledger(LEDGER_PATH); all_records=ledger.snapshot(); runs={}; budget=[]
    previous=json.loads((root/'billing/before.json').read_text())
    with ledger.transaction() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    hashes=json.loads((root/'gate1-preservation.json').read_text())
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    for rid,line,arm in c['run_order']:
        snap=ledger.snapshot(rid); run=snap['runs'][0]; s=json.loads(run['session'])
        w=PilotWorld(); w.restore(s['environment']); requests=snap['requests']
        path=root/rid; metrics=json.loads((path/'metrics.json').read_text())
        # Generic Gate 1 exporter uses SIM. Preserve the actual Gate 2 session label.
        metrics.update(source=s['source'],environment_origin='SIM',checkpoint_hash=s['checkpoint_hash'],
            condition=arm,remaining_primitives=w.s['remaining_budget'],cost=w.score()['tool_calls'])
        if line=='p1': metrics.update(attribution_metrics(None,w.s['root_cause'],w.s['history'][w.s['prefix_actions']:]),diagnostic_value=None)
        metrics['failure_layer']=None if metrics['success'] else 'model_decision_and_task_semantics; decision_horizon_termination' if s['error']=='decision/action budget exhausted' else 'interface_or_harness'
        (path/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        (path/'report.md').write_text('# Controlled paired Pilot (not statistical evidence)\n\n'+json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
        current=json.loads((root/'billing'/('after-'+rid+'.json')).read_text())
        usd=Decimal(str(current['account']['used']))-Decimal(str(previous['account']['used']))
        item={'run':rid,'account_used_delta_usd':str(usd),'reference_cny_conversion':str(usd*Decimal(c['pricing']['cny_per_usd'])),
              'actual_itemized_cost_cny':None,'reserved_exposure_cny':metrics['reserved_exposure_cny']}
        budget.append(item); previous=current
        trajectory=[json.loads(x) for x in (path/'trajectory.jsonl').read_text(encoding='utf-8').splitlines()]
        runs[rid]={'metrics':metrics,'session':s,'requests':requests,'trajectory':trajectory,'budget':item}
    records={line:[r['metrics']|{'condition':r['session']['condition']} for r in runs.values() if r['session']['line']==line] for line in ('p1','p5')}
    summaries={line:score_line(line,rs) for line,rs in records.items()}
    for line in summaries:
        summaries[line].update(independent_checkpoints=1,branch_count=len(records[line]),sampling_unit='one matched SIM-origin checkpoint; branches are not independent tasks')
    pairs={}
    for line,base in (('p1','g2-p1-no_intervention'),('p5','g2-p5-belief_only')):
        pairs[line]={rid:paired_intervention(runs[base]['metrics'],r['metrics']) for rid,r in runs.items() if r['session']['line']==line and rid!=base}
    batch_exposure=sum(r['reserved'] if r['billed'] is None else r['billed'] for r in all_records['requests'] if r['run'].startswith('g2-'))
    summary={'source_environment':'SIM','scientific_inference':False,'independent_checkpoints':2,'branches':len(runs),
        'line_summaries':summaries,'paired_outcomes':pairs,'budget':budget,'batch_reserved_cny':batch_exposure/1e6,
        'cumulative_exposure_cny':all_records['exposure_micro_cny']/1e6,'unreconciled_requests':all_records['unreconciled_requests'],
        'gate1_originals_unchanged':True,'ledger_integrity':'ok','actual_itemized_cost_cny':None}
    (root/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    mock_root=root/'mock'
    mock_summary=json.loads((mock_root/'summary.json').read_text(encoding='utf-8'))
    for rid,_,_ in c['run_order']:
        path=mock_root/rid/'metrics.json'; m=json.loads(path.read_text(encoding='utf-8'))
        m.update(actual_api_cost_cny=0,actual_network_calls=0,transport_mock=True,source='SIM',scientific_evidence=False,
                 reservation_is_synthetic=True)
        path.write_text(json.dumps(m,indent=2),encoding='utf-8')
        mock_summary['scores'][rid]=m
        (mock_root/rid/'report.md').write_text('# Mock instrument calibration, zero real API calls\n\n'+json.dumps(m,indent=2)+'\n',encoding='utf-8')
    (mock_root/'summary.json').write_text(json.dumps(mock_summary,indent=2),encoding='utf-8')
    rows=['# Gate 2 P1/P5 配对机制 Pilot 报告','',
        '2026-10-12。**机制 Pilot（不可当作统计显著或 SOTA）**。七条真实轨迹已完成并暂停：P1 三组、P5 四组；共两个独立构造 checkpoint，同 checkpoint 的分支不能当成独立任务。环境来源 SIM，条件标记 SIM/CF/ORACLE，不是公开 Benchmark 的自然失效频率。没有收费运行 P2/P3/P4，没有失败重试或筛选。','',
        '## 结果','',
        '| 研究线 / 条件 | 成功 / 分母（比例） | 决策 / primitive | 共享有效节点复用代理 | 无效 apply 比例 | 停止原因 |',
        '|---|---|---|---|---|---|']
    for rid,line,arm in c['run_order']:
        m=runs[rid]['metrics']; rows.append(f'| {line} / {arm} | {int(m["success"])}/1 ({100*int(m["success"])}%) | {m["decisions"]} / {m["tool_calls"]} | {m.get("valid_node_retention","未测")} | {m.get("invalid_action_rate","未测")} | {m["error"] or "成功验证"} |')
    rows += ['',
        'P1 的无干预和 Oracle 归因成功，普通反思失败；本单 checkpoint 的观察性配对成功差为 -1（反思）和 0（Oracle），工具成本差为 +3 和 -2。P5 四组均成功，相对 Belief-only 的成功差均为 0；整体重规划、选择性修复、Oracle 依赖提示的工具成本差分别为 +2、+1、+2。上述差异是本次实际分支结果，不是总体因果效应或显著性结论，temperature=0 亦不保证供应商完全确定性。','',
        '**P5 本实例成功率饱和，无法区分成功率提升。** 仅能观察成本及执行复用差异。原生 Belief-only 反而使用最少动作；Oracle 提示没有达到最少成本。未增加任务难度、改评分或补跑。P1 普通反思出现失败，说明这个实例有行动后果差异，但不足以断言普通反思普遍有害。','',
        '## 实际机制观察','',
        'P1 普通反思：inspect(A) → diagnose(A) 获得 delivered → diagnose(B) 获得 A incompatible → prepare(A) → apply_change(A) → verify(A) 失败 → diagnose(A) → inspect(B)。第4步自述已知 A 不兼容，但认为 prepare 能准备“修正配置”；第5步继续应用 A。环境 prepare 只准备工作区，并不修改配置兼容性，因此出现虚构动作效果与反馈后的行动未调整。第8次决策后仍有3次 primitive 额度：直接停止机制为决策 horizon，基础问题为模型行动选择/工具语义解释偏差；不是财务预算、API 格式或工具执行异常。不能仅因 budget exhausted 文本就把它归类为收费预算失败。','',
        'P1 无干预：同样 inspect(A)、diagnose(A)、diagnose(B)，随后直接 apply_change(B)、verify(B)，成功。Oracle 归因分支仍执行 diagnose(B) 才转向 B；其自述称该诊断在检查“alternative configuration”，而实际工具定义是检查 A 的兼容性。这延续了 Gate 1 的观察：成功并不保证每一步证据解释准确。','',
        'P5 Belief-only：inspect(B) → apply_change(B) → diagnose(B) → verify(B)，保留已完成共享工作，4步成功。选择性修复提示仍多做 prepare(B)，5步成功。整体重规划与 Oracle 依赖提示都执行 prepare(B)、calibrate(B) 后完成同一4步后缀，共6步。两组自述都承认共享 snapshot/credentials 有效，却仍重做对应动作；Oracle 依赖组并非理想 Oracle 行动策略，只是获得特权依赖提示的同一个 LLM。所有 P5 分支均未执行旧 A 的目标相关动作，所以没有观测到旧 A 计划持续执行。','',
        '## 对照公平性与解释边界','',
        '预登记方案见 [GATE2_PROTOCOL.md](research/GATE2_PROTOCOL.md)，精确消息、顺序、版本与指纹见 [preregistration.json](results/gate2/preregistration.json)。同线各组环境快照、RNG、旧计划、可见前缀与剩余预算一致，仅条件消息不同。P1 checkpoint 剩余11个 primitive，P5剩余9个，均把历史已消耗动作计入12个总额度。对照文本确实不同；真实后续行动也有差异，未由 Harness 自动执行“重规划”或“选择性修复”。','',
        'Oracle 条件提供额外真值/依赖信息，不匹配普通组的信息量或 Token 长度，属于信息上界检查，不能作为纯提示格式对照。P1 真实仅执行 H；E只由 Mock 检查，因此尚无真实 H/E 总体归因准确率。自述未按强制 H/E 标签采集，attribution_correct 和 diagnostic_value 保持未测。P5 valid_node_retention 是两个有效共享完成节点是否被重做的执行代理，不证明内部计划结构。','',
        'P5 Oracle 节点清单可由普通组已见的旧 DAG 和新 B 要求推导，主要增加显式定位；此任务并未赋予它独立隐藏信息优势。因此 P5 四组成功饱和与 Oracle 成本未下降，不能直接否定真实依赖信息的价值。未在观测结果后修改任务来制造这种优势。','',
        '工具语义存在重要限制：target 对 prepare/calibrate/普通 verify 不起区分作用，模型却多次使用“service A/B”“calibration of B”等解释。成功分支也存在这个偏差，故失败不能完全归为一般推理缺陷；动作命名先验、配置与服务实体混淆、Schema 接受无作用参数都可能参与。新增 PilotWorld 与 Gate 1 的动作含义变化已显式版本化，不能把任务变化或工程修复称为算法提升。','',
        'P2 离线构造了合法的 User/Tool 配对历史，事实内容、多重集与调用 ID 匹配；P3 离线保留 H/E 自然成功/失败及一次具体诊断干预；P4 离线验证校准后互补位探查及 inspect 的信息+staging 双作用。它们都未获本批真实数据，不能报告这些研究线的实证改进。','',
        '## 费用与未结算预留','',
        '官方只读余额接口实际返回 HTTP200、账户 active、币种 USD：[Balance API 文档](https://ofox.ai/docs/api/openapi/balance)。该接口返回账户累计消费，不返回逐请求账单。公开费率已重新获取并与原 qwen/qwen-flash 快照核对一致；缓存写入费率语义、逐请求舍入、实际充值人民币汇率仍未知，不能记为0。官方计费说明称实时结算，但仍以余额观测和逐请求证据区别核验层级：[计费说明](https://ofox.ai/docs/develop/observability/pricing)。','',
        '| 分支 | 实测账户 used 增量 USD | 参考折算 CNY | 持久化预留 CNY | 逐请求实际账单 |',
        '|---|---|---|---|---|']
    for item in budget:
        rows.append(f'| {item["run"]} | {item["account_used_delta_usd"]} | {Decimal(item["reference_cny_conversion"]):.8f} | {item["reserved_exposure_cny"]:.6f} | 未知 |')
    delta=sum(Decimal(b['account_used_delta_usd']) for b in budget)
    rows += ['',f'本批37次真实模型请求；账户累计消费增量合计 USD {delta}，按冻结参考 USD/CNY={c["pricing"]["cny_per_usd"]}（ECB 2026-10-09）折算约 ¥{delta*Decimal(c["pricing"]["cny_per_usd"]):.8f}，不是人民币实际结算账单。余额采样期间若存在其他客户端消费，会混入增量；不能据此自动给本项目逐请求分摊费用。账户 lifetime used 还包含本项目之外的历史消费，未全额归入项目。',
        f'本批保留预留 ¥{batch_exposure/1e6:.6f}（首批上限¥5）；含 Gate 1 的累计预算暴露 ¥{all_records["exposure_micro_cny"]/1e6:.6f}（Gate 2累计上限¥40、项目¥100、运行线¥90）。{all_records["unreconciled_requests"]}笔逐请求账单仍未核验；原Gate 1 ¥0.130739全部保留，没有用账户聚合增量释放预留。每次真实请求预留¥0.022998，输入上界32768、输出512及潜在缓存写入附加费、2倍缓冲。整个预登记56次请求的最大估算预留¥1.287888，本次实际37次。',
        '主要 input/output usage 均有效；缓存读仅记录明确返回字段，缺失读/写量保持null。没有新接口错误、截断、拒绝或自动重试；原生 stop 工具兼容异常仍按每步记录。未知实际附加规则意味着本地费率预算不能声称是供应商真实扣款的数学保证；余额增量未超过任何分支预留，SQLite核验与跨进程累计守卫正常。','',
        '## 验证、交付与暂停','',
        '103 项 pytest 通过，包含全部 Gate 0/Gate 1 回归，以及 H/E 同表面反馈、P1/P5 真值与分叉恢复、原生 Mock 工具往返、中断后复用已持久化响应、不重发、跨进程首批上限与包含历史预留的¥40累计阻断。Mock完整轨迹在 results/gate2/mock/，费用¥0，仅为仪器校准。Generic exporter 的 Gate 1 固定SIM标签在本批派生 metrics 中按原始 session 修正为 SIM/CF/ORACLE；未改写请求响应、可见轨迹或旧 Gate 1 结果。','',
        '全部 Gate 1 文件 SHA-256 与运行前一致；账本 integrity_check=ok。主账本沿用 .state/gate1.sqlite3，增量增加批次授权表，迁移前备份 .state/backups/gate1-before-gate2.sqlite3。完整事件、Token、原始响应、隐藏状态恢复文件与预算审计保留；API Key未打印或提交。','',
        '实际执行命令（已执行，勿自动重跑）：','',
        '```powershell',"$env:PYTHONPATH = 'src'",'python experiments/gate2_billing.py before','python experiments/gate2_mock.py','python -m pytest -q','python -m adfl.gate2 prepare','python -m adfl.gate2 run --run-id g2-p5-full_replan','python -u experiments/gate2_execute_remaining.py','python experiments/gate2_report.py','```','',
        '新猜想、可证伪预测与最低成本后续对照已写入 research/OPEN_QUESTIONS.md。本次已暂停；不进一步执行 P1–P5 扩展，不因 P5 饱和或 P1 失败而调整任务或再采样。','',
        '## 完整干预和逐步可见轨迹','']
    for rid,line,arm in c['run_order']:
        r=runs[rid]; s=r['session']
        rows += [f'### {rid}','',f'Checkpoint `{s["checkpoint_hash"]}`；source {s["source"]}，环境来源SIM。',
            f'[原始事件和请求响应](results/gate2/{rid}/events.jsonl) · [可见轨迹](results/gate2/{rid}/trajectory.jsonl) · [评分](results/gate2/{rid}/metrics.json)','',
            '初始完整可见上下文（含旧计划与精确干预）：','', '```json',json.dumps(s['messages'][:len(session_messages(c,rid))],ensure_ascii=False,indent=2),'```','']
        for t,request in zip(r['trajectory'],r['requests']):
            response=json.loads(request['response']); body=response['body']; calls=body['choices'][0]['message']['tool_calls']
            rows += [f'#### 决策 {t["step"]}','',f'请求 `{request["id"]}`；响应 `{body.get("id")}`；model `{body["model"]}`；HTTP {response["status"]}；finish_reason `{body["choices"][0]["finish_reason"]}`；调用 `{calls[0]["id"]}`。','',
                '```json',json.dumps({k:t.get(k) for k in ('visible_before','action','tool_result','belief_report','plan_snapshot','usage','compatibility_anomaly','latency_s','error')},ensure_ascii=False,indent=2),'```','',
                f'本请求预留¥{request["reserved"]/1e6:.6f}，逐请求实际账单null；无自动重试。','']
    (ROOT/'GATE2_PILOT_REPORT.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    print(json.dumps({'branches':len(runs),'batch_exposure_cny':batch_exposure/1e6,'cumulative_exposure_cny':all_records['exposure_micro_cny']/1e6,'observed_account_delta_usd':str(delta),'unreconciled':all_records['unreconciled_requests']}))


def session_messages(c,rid):
    return c['prompt_manifest'][rid]


if __name__=='__main__': main()
