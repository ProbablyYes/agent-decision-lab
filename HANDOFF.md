# Gate 0 交接：M0–M3 最小实验工具

日期：2026-10-12。状态：暂停，等待研究负责人审查并明确批准 Gate 1。真实 API 调用 0，实际 API 支出 **¥0**。机制 Pilot（不可当作统计显著或 SOTA）。

## 权威协议与范围

已完整阅读仓库实际文件 `Codex_START_HERE_V0.2.md`、`research/Agent_Decision_Failure_Lab_Codex_Research_Brief_V0.2.md`。用户指定的两个短文件名不在仓库，未创建替代协议或改写原文。历史独立 V0.1 文件不存在，版本差异无法逐文件比较，V0.2 内嵌执行细则照用。

五条研究线、主要指标和主要实验分组未修改。共同主结果保留最终成功；ALFWorld 官方分数尚未涉及。Mock 只校准仪器，不证明 Agent 会持续犯错，也不证明干预有效。

## 实际完成

M0：Python 3.11+ 标准库运行项目；固定开发依赖、pytest、配置校验、目录骨架、环境变量密钥隔离。`.env` 已被 Git 忽略，未读取或输出密钥。

M1：CDW attribution、plan、complement 三类任务。H/E/U 分别提供错误假设、执行未生效、证据不足的校准情形；支持 inspect/diagnose/prepare/calibrate/apply_change/verify/undo/wait/组合动作。世界有实际目标变更、准备依赖、校准依赖和最终验证；不是单纯根因标签分类。reset/snapshot/restore 包含 RNG、预算、历史、DAG 与隐藏状态。所有组合 primitive 单独计费。

M2：每线 3 个 fixture，共 15 条完整 SIM 原始轨迹；另存 1 条失败保留示例。各线独立 summary，分母明确。评分契约保留全部辅助指标；已实现成功计数、归因对错、重试计数、P3 同 checkpoint 成功差/额外成本/误伤/恢复、P4 工具成本/准备动作选择、P5 失效行动比例及显式节点保留评分。未测的诊断价值、belief/plan 采纳、Oracle regret 等明确 null/unmeasured，不虚构测量。

M3：冻结 APIAgent 配置与 prompt/schema 指纹、JSON 动作解析、与 CDW 真正循环的注入式 adapter、完整可见消息、自述计划、时延、用量和费用日志。测试传输完成端到端循环。网络 transport 刻意未接通，未安装 ALFWorld。dry-run 不发请求；未选模型或定价时返回估价未知。支持 --dry-run、--max-spend-cny、--require-approval；最后一个参数不会自动授予人工批准。

预算：调用前预留输入上界及最大输出成本；单 guard 最多一个在途请求；未知账单/用量锁定预留并停止；失败不自动重试；10/40/70 的阶段上限、90 的运行停止线、100 的硬上限均保留。settle 超出预留即锁定。真实跨进程全局账本尚未接通，因此不能直接部署收费 transport。

## 验证结果

`python -m pytest -q`：**42 passed in 0.42s**，失败 0。覆盖 15 fixture、三族 JSON 快照回放、隐藏字段不进入公开轨迹、DAG/组合动作/undo 的效果、互补诊断、五线正负评分、10/40/90/100 阻断、预留及未知账单、超时/损坏 JSON/缺失 usage/收费错误、无审批不调用 transport、API 接口的模拟完整循环、配置拒绝测试集调参。

`python -m adfl.runner --output results/gate0`：15 条校准成功，API ¥0。这是脚本使用已知动作的确定性结果，不能称为真实模型成功率。额外 failure_retention 为错误变更后脚本耗尽，失败与异常都留在结果中，未排除。

`python -m adfl.runner --dry-run --max-spend-cny 10 --require-approval`：network_calls=0、approved=false、estimated_cost=null。

每个 run 有 config.yaml、trajectory.jsonl、events.jsonl、metrics.json、report.md。hidden/initial.json、final.json、session.json 是评估者文件，不传入 Agent。session 保存环境、消息、指纹与预算；环境回放已验证，完整进程中断续跑 CLI 尚未提供。events 保留响应与异常，正常 Mock 无异常时为空。公开日志只记录可见状态，隐藏世界状态保存在独立目录。

## 尚未实现及实验设计问题

详见 research/OPEN_QUESTIONS.md。未执行真实五线实验臂，所有 scientific comparison arms 明确标记 missing；没有自然 OBS、实际 CF 或 Oracle 效果数据。P2 原生 Tool 角色消息历史须匹配，离线 helper 不可直接发给供应商。P4 奖励权重/Oracle 未定义，因此不算 regret。P5 最小线性 DAG 仅校准部分节点失效，不代表一般复杂计划。U 脚本猜中目标不是推断能力。P3 需同时保留原成功/失败 checkpoint。以上相关科学比较暂停，不擅自补充协议参数。

需补齐真实 transport 的供应商 schema、全局持久化预算账本、崩溃恢复对账、人工审批记录绑定模型/价格/阶段、usage 与缓存计价核验，方可扣费。目前 guard 不能防止多个独立进程各自建立账本，这也是不交付联网 transport 的原因。

没有观察到真实 Agent 的反预期行为，也没有提出有数据支持的新科学结论。最重要的仪器发现是：脚本完成任务与辅助机制测量是不同层次，未收集 belief/plan 时不得用任务成功补齐这些指标。

## Gate 1 首批真实 API 执行方案（未执行）

人工批准后先冻结单一 model_provider/model_id/model_revision、temperature=0、max_tokens=512、prompt 与工具 schema；核验官方/供应商实际价格、币种、汇率来源时间、输入/输出/缓存计费和失败费用。先实现上列阻断项，再单线程逐请求执行；没有自动重试。每条最多 8 次模型决策、12 个 primitive 工具动作，超过即记失败/截断，禁止补跑到满意。

建议先 **5 条、无分叉**：P1 attribution:H、P1 attribution:E、P2 plan:H、P5 plan:E、P4 complement:H，seed=0，split=pilot，来源 SIM。P2/P5 分开报告，不以同一成功数字合并；初批只检验真实行为和账单，角色对照、计划修复对照尚不运行。前三条也可作为 3 条保守起步，审查后再执行余下 2 条。真实冻结 LLM 在 CDW 上运行依然是 SIM，不能称 ALFWorld 自然频率。

首请求后立即核对返回 usage 和供应商账单；对不齐即停。随后检查动作是否合法、是否无效重试、是否使用诊断、是否保留准备、是否能验证成功。全部失败/超时保留；不得挑选成功样本。初批若无明显实验空间或接口不可靠，不扩样本。每线 1–2 场景、最多两分支是 Gate 1 上界；首批 5 条只覆盖优先接口，P3 真实干预比较待 checkpoint 可用后另行审查，不能宣称五线 Gate 1 均已完成。

## 保守成本包络（不是供应商报价）

未核验模型价目，因此**不能给出有效真实报价**，也不会调用 API 获取报价。设输入单价 a、输出单价 b（均为人民币/百万 token），5 条×8 请求×每次输入上界 8192、输出 512：上限为 `0.327680*a + 0.020480*b` 元。真实调用前按序列化 UTF-8 字节长度+1024 开销检查输入界，超过 8192 就暂停而不静默截断。

仅作预算准入示例：若核验后 a≤¥10、b≤¥30，则上述请求总预留≤**¥3.8912**；再留一倍对账/估计缓冲，预算包络 **¥7.7824**。这不是宣称供应商有该价格；实际价格高于上限应减少首批条数/动作上限并重新报审。3 条同样条件的基础包络≤¥2.33472，加倍≤¥4.66944。

Gate 1 累计绝不超过 ¥10；建议初批实际操作上限设 ¥8，余 ¥2 等待账单。总阶段累计上限仍为 10/40/70/90；全项目硬上限 ¥100。未知单价、用量不可读、并发账单不可控时停止。预算不得自动转入下一 Gate。

## 目录树与提交

```text
AGENTS.md / README.md / HANDOFF.md
Codex_START_HERE_V0.2.md
pyproject.toml / requirements-dev.txt / .gitignore
configs/gate0.json
research/
  Agent_Decision_Failure_Lab_Codex_Research_Brief_V0.2.md
  RESEARCH_MAP.md / DECISION_LOG.md / OPEN_QUESTIONS.md
src/adfl/
  config.py / runner.py
  world/cdw.py
  agents/interface.py
  budget/guard.py
  interventions/__init__.py
  evaluation/__init__.py
experiments/p1..p5/README.md
tests/test_instruments.py / test_scoring.py
results/gate0/
  p1..p5/{H,E,U}/[五类标准结果文件 + hidden/]
  p1..p5/summary.json
  failure_retention/[标准结果文件 + hidden/]
```

Git commit/id 记录在 `results/GATE0_COMMIT.txt`；该记录指向包含实现、测试和本报告的交付提交。暂停等待 Gate 1 审查，不会后台继续实验。

## Gate 1A 后续交接（2026-10-12）

上述为 Gate 0 的历史验收记录。Gate 1A 新增真实 transport、持久化预算/审批/恢复和 Mock 网络测试；当前状况以 GATE1_READINESS.md、GATE1_MODEL_SELECTION.md 为准。最终72项无网测试通过。推荐 qwen/qwen-flash 待确认，实际账户计价/缓存语义仍阻断收费；没有读取密钥、没有推理调用、实际新增花费¥0。GATE1_REPORT.md 现标记未执行。按最新用户要求暂停，等最终模型确认及第一条轨迹批准。
