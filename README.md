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

APIAgent 固定配置、提示版本与动作接口；没有网络 transport。提供注入传输以无网测试预算、损坏响应和超时。真实 API 需 Gate 1 审批、定价核验以及后续 transport/账单持久化工作。CLI 的 approval 参数不会授予审批或发出请求。`.env` 只用于后续真实 transport；当前没有读取或输出密钥。

每个 run 保存 config.yaml（JSON 是 YAML 1.2 子集）、trajectory.jsonl、events.jsonl、metrics.json、report.md；失败也保留并进入分母。session.json 存储环境与可见消息用于恢复，现阶段没有中断续跑 CLI。ALFWorld 和真实实验臂未运行。
