# Agent Decision Failure Lab

V0.2 科研机制 Pilot；P1–P5 独立，Mock 仅验证实验仪器。权威文件为 `Codex_START_HERE_V0.2.md` 和 `research/Agent_Decision_Failure_Lab_Codex_Research_Brief_V0.2.md`。

Python 3.11+，运行时仅使用标准库。开发依赖固定在 requirements-dev.txt。

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
$env:PYTHONPATH = 'src'
python -m adfl.runner --output results/gate0
python -m adfl.runner --dry-run --max-spend-cny 10 --require-approval
```

运行目录必须不存在，防止覆盖原始记录。每线 H/E/U 三个共享 fixture；名称是校准分层，不代表每线都研究 H/E/U。所有工具会改变环境或提供受限观察，任务成功须正确变更后验证。组合动作逐步扣费。

原始日志位于 results/gate0；hidden/ 下快照只供评估者，不能传给 Agent。trajectory 仅含可见观察、消息、动作及自述。工具结果目前作为 user 内容返回，所有组须一致；P2 真正的原生 tool 角色实验尚未接入。角色反馈 helper 只是离线构造器。

Gate 0 APIAgent 固定配置、提示版本与动作接口，保留注入传输以无网测试预算、损坏响应和超时。Gate 1A 已增加真实 OFox transport 和独立持久化入口 `python -m adfl.gate1`，详见 GATE1_READINESS.md。默认配置的模型/账户价目/汇率/cache 语义未确认，不能发请求。`--require-approval` 参数不授予审批；批准必须绑定冻结指纹和单条 run。仅获批收费 send 时 transport 才会加载本地凭据；Gate 1A 没有读取密钥。

每个 run 保存 config.yaml（JSON 是 YAML 1.2 子集）、trajectory.jsonl、events.jsonl、metrics.json、report.md；失败也保留并进入分母。Gate 0 session.json 存储环境与可见消息。Gate 1 以 SQLite 为真值源恢复，JSONL 是可重新导出的审计产物；不重发中断请求。ALFWorld 和真实实验臂未运行。

Gate 1A 无网检查：

```powershell
$env:PYTHONPATH = 'src'
python -m adfl.gate1 prepare --dry-run --max-spend-cny 8 --require-approval
```

主基座推荐及候选实际价格见 GATE1_MODEL_SELECTION.md。只有研究负责人确认模型、核验收费资料并批准第一条后才可执行；首条后再次暂停审查，不批量运行。
