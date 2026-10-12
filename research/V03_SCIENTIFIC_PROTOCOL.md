# V0.3 Stage A 科学协议与任务审查

日期：2026-10-12。范围：零收费模型调用的仪器校准、任务构造、预注册。附件的 Stage B 是待审查方案，不是本轮执行授权。保留 V0.2 的五条独立研究线和主要结果指标：最终任务成功；成本、过程指标与自述分开。旧 CDW、PilotWorld 和 Gate 0–2 结果不变。

## 研究对象与证据边界

Gate 1 的三条成功轨迹说明接口和多轮工具执行已跑通，不能估计公开 Benchmark 的失效率。Gate 2 P1 反思分支失败存在证据语义和动作参数混淆，P5 四组成功且自然继续最省动作，不能当作新算法的证据。V0.3 的任务变化是新的 SIM 仪器；没有对旧结果重新评分或声称复现。

本轮实现位于 `src/adfl/v03/`，复用已有 MockAgent 和持久化账本的计价模块，遵循 CDW 的 snapshot/restore/step/score 接口。另建严格、版本化动作 Schema，避免更改原 Gate 1 transport 的冻结动作集。原 API transport、审批与日志基础保留，V0.3 收费执行器尚未接入；没有新增自动收费入口。

所有环境完整状态、评分真值和程序化 Oracle 输出只能进入 `evaluator_only`、校准报告和研究审查。普通 Agent 的输入只由 `design.context()`、`role_contexts()` 或 `intervention()` 产生，不能传入 checkpoint、manifest、任务文件名、family 标签或评分器输出。P1 的 target、delivery、sensor validity 不在普通观察里。P5 的既往执行 stamp 是任务本身的可见证据；当前 required revision 和 live validity 由工具/推理核实，不直接泄漏。Oracle 条件显式标注特权。

每次 primitive 成本为 1，辅助净效用为 `task_success - 0.05 × primitive_calls`。0.05 是冻结的人工任务效用单位，不是 API 人民币价格；不可将其解释成真实经济损失。工具失败也计成本。多个合法行动顺序都可成功，评分不与参考序列比较。未测量的归因报告、事实接收、自述正确率为 null。

## P1：错误原因与证据不足

| 家族 | 隐藏状态 | 特定证据 | 可行修复 |
|---|---|---|---|
| H | prior 已送达，但 prior 不兼容 | receipt=delivered；compatibility=incompatible | 选择另一配置，再 verify |
| E | prior 兼容，但 prior 未送达 | receipt=absent；compatibility=compatible | 重发原配置，再 verify |
| O | prior 已执行，监控反馈过期 | 有送达收据；独立 monitor audit 发现 stale | 核验监控，再 verify，无需修改配置 |
| U | 可见证据相同的 H/E 支持世界 | 需要 receipt/compatibility 等进一步证据 | 行动必须依赖新的证据 |

H/E 的 seed 0/1 分别构成两对完全相同的可见初始上下文；这些是标签置换变体，不声称独立机制。U 的 seed 0/2 可见上下文相同而正确目标不同。U 是**认识上的不可识别性**，不是与 H/E/O 互斥的第四种物理故障；Oracle 的 U 标签本身也不给正确目标。

receipt、compatibility、audit_monitor 各自只回答一项证据，成本各为 1。没有一键返回完整根因和下一步行动。verify 依据隐藏实际状态及独立观测有效性，不采用自述。receipt 指向 checkpoint 前的 prior，后续 apply 不会改写这份既往收据。

条件：no-intervention、generic-reflection、真实工具 diagnostic-evidence、oracle-failure-class。诊断条件从相同处理前 checkpoint 调用真实 receipt，并扣除 primitive 预算；不把免费 Oracle 当作普通方法。首批收费建议仅冻结一个 H/E 无干预对，其他条件不自动执行。

主要：task_success、工具成本/净效用。次要：诊断选择、wrong_target_modifications、first_relevant_action_correct；S0/S1/S2 需要对可见证据逐步审计，不能仅凭最终成功或某次额外探查自动判定。归因自述当前未独立采样，保持 null。

反证：强模型合理区分 H/E/O；固定反思同样有效；Oracle 不改善结果；成功饱和。出现这些情况就报告，没有提高难度制造失败的自动流程。

## P2：相同内容、不同消息通道

两个 seed checkpoint × C0/C1/C2；另有正确来源和 reliability=0.8 来源亚组。先在一个克隆上真实执行 compatibility，一次工具调用、同一 call id、同一处理后状态及剩余预算，保存原始结果。实验投递层将事实送入 user 或原生 tool-result；C0 将事实遮蔽。没有给 C2 多调用工具，也没有伪造不存在的 tool call。

C1 与 C2 交换**完全相同的 fact 字符串和 neutral 字符串**在 user/tool 两个位置，其他角色布局、tool_call_id、prefix 成本相同，序列化字节长度相同。实际 tokenizer/角色开销仍要在获批运行后记录，不能事先声称模型输入 token 绝对相等。C0 信息量较少是定义中的处理差异。

不可靠亚组采用冻结的 `seed % 5 == 0` 投递翻转，其余事实正确；source reliability=0.8 对应均匀 residue 分布下的生成规则。当前两个手选校准 checkpoint 不构成 80% 正确率样本。保留 raw tool truth 与投递后事实，不能将处理层噪声误归为模型或原始工具错误。主来源效应与错误证据抗干扰效应分层分析。

fact_reception/自述若另开测量分支，不把该分支问答偷偷放回行动上下文；当前 null。主要仍为最终成功，记录 first-relevant-action、工具成本。C3 structured-belief 留待后续协议，不伪称已执行。

## P3：恢复价值而非失败风险

| 家族 | 有限世界约束 | 预先指定三个条件 |
|---|---|---|
| recoverable | stage=1，需要两次 advance 和 verify；窗口允许两次推进 | continue / generic-warning / selective-repair |
| fragile-success | wait 可自然完成；rollback 可逆，但移除进度并消耗窗口 | continue / rollback / wait-one-observation |
| irrecoverable-within-budget | stage=1，剩余 1 primitive；所有合法动作穷举均不能完成 | continue / diagnostic-probe / selective-repair |

三类初始风险描述相近，不能只选 baseline 失败。干预实现是真实 prefix 动作或明确不同的提示：rollback/probe/advance/wait 实际改变环境、扣费并返回原生工具结果；warning 只改变提示。Scripted rollout 是固定策略的仪器检查，不是反思方法的效果估计。

`shortest_success` 对有限合法动作空间穷举，生成每个 first action 的最佳续接及净效用；无可行完成时允许停止，已消耗动作仍有负成本。该 Oracle 是特权程序化上界，不是风险标签。baseline 自然成功遭破坏、baseline 失败被恢复应按相同 checkpoint 单独计数；不混算两个条件总体成功率来推因果。

## P4：精确 belief-state 价值

四个公共有限概率模型，隐藏状态 `(x,y,calibrated,first_probe,progress,time)`；A/C/D 为两个等概率根状态，B 为四个等概率 bit 对。目标 B 为 XOR；其他为 x。转移及条件观测概率明确为 0/1；这是确定性条件反馈的 POMDP 特例，不声称已经覆盖随机失灵工具。

- A：calibrate 不改变目标熵，但使 measure 可靠。
- B：probe1 显示 x，不改变 XOR 目标的边缘熵；使 probe2 可显示 y。
- C：dual 同时推进 progress 并给 x，prepare 和 measure 是分开的替代路线。
- D：第一次 wait 获得定时正确观测；time≥2 后提交目标已错过窗口。

每个动作成本 1/20，正确终止且满足任务前提得 1，否则 0；horizon=4。belief 使用 Fraction 归一化，DP 输入为**后验分布**，不是一次实现的隐藏目标。BeliefSession 将实际 hidden 留在 evaluator-only 快照，普通观察只有 posterior/history；JSON 恢复和逐步重放已测试。

基线为 immediate-progress/reward greedy、one-step target information gain、receding two-step lookahead、exact finite-horizon DP。两步基线在截断处使用最佳立即终止价值；不是故意给零叶值削弱基线。IG 相同时优先实际推进 progress，避免只靠字母排序制造 dual 行动差距。即时基线等值时使用公布的动作顺序，结论要承认 tie-break 依赖。

| 世界 | 即时 greedy 净回报 | 一步 IG | 两步前瞻 | 精确 DP |
|---|---:|---:|---:|---:|
| A | 0.45 | 0.45 | 0.85 | 0.85 |
| B | 0.45 | 0.45 | 0.85 | 0.85 |
| C | 0.40 | 0.90 | 0.90 | 0.90 |
| D | 0.45 | 0.90 | 0.90 | 0.90 |

这些是数学仪器值，非 LLM 结果。四个世界两步基线全部达到 Oracle；当前任务**不支持**“必须开发更复杂 P4 方法”的主张。更长依赖或近似训练方法需新研究决策，不自动扩展。逐策略的成功概率、期望动作成本、regret、memoization 规模另见 p4_exact.json。

## P5：更新与计划有效性

共同的非线性拓扑为 snapshot→left、snapshot+credentials→right、left+right→merge、merge+credentials→publish，最后 verify。checkpoint 已完成 snapshot/credentials/left/right，继承计划为 merge/publish/verify。三个家族是不同更新机制，不把共同 DAG 的 seed 置换视作独立图任务：A 改分支 left 的要求；B 改共享祖先 snapshot 的要求；C 给出 0.8 可靠的非权威 snapshot 更新报告。

每个执行 stamp 记录本节点 requirement revision 和输入节点的 generation。有效性递归核对当前要求、输入有效性和 generation。重做祖先即使 revision 没变，也会使依赖旧 generation 的已完成后代失效。credentials 在 B 中仍有效；A 中 snapshot/credentials/right 都可保留。C 的 seed%5=0 是假警报，先 audit 可以避免丢弃旧工作；其他 residue 发生真实变化。没有把种子选择率当成自然概率。

execute_node(node) 会在前置条件有效时使用当前要求执行该节点；不隐式重做其子孙，也不接受无作用的 target。此任务研究**哪些节点需要协调**，不研究节点内部选择错误配置。工具会在无效前置条件时拒绝执行：因此 `obsolete_action_attempts` 可非零，`obsolete_action_execution` 在此受保护世界中为零，不能把被拒绝的尝试谎称实际执行了过期结果。

full-replan 是重新评估计划的提示，不强制重做所有已完成节点；selective 提示要求核对依赖，不提供隐藏 invalid 集合。A/B 的 invalid 集合可由权威新事实、DAG 和 stamp 推导，所谓 dependency-oracle 在这些家族**不是额外特权信息优势**；C 未 audit 时 evaluator 的 live validity 才具有特权信息。标签要按条件诚实区分。

程序化最优、全部重做、先尝试旧尾部再用特权规划器恢复三种 Mock 脚本用来检查工具后果和成本计数，不能当作真实 belief-only/full-replan/selective 三种算法结果。多个拓扑排序验证通过。首批只拟比较 B 的 belief-only 和 selective 提示；若行为一致或成功饱和，应报告，无权自动加难。

指标：task_success、净工具成本；valid_work_retention 使用更新后仍有效的既往完成节点作分母；unnecessary_reexecution 在执行前检查真值；stale attempt 与 actual execution 分开；plan_consistency 按节点有效性，不按参考路径。

## 分割、冻结与后续小批次

design seeds=[0,1,2]；dev=[10,11,12]；holdout=[1000,1001,1002]。144 个 manifest 条目包括 seed 变体，不是 144 个独立机制。holdout 仅生成、冻结 checkpoint，不 rollout/评分/据此选择难度；所有机制最优性校准在 design/dev 和公共 P4 概率模型上。

下阶段预选 dev seed=10：P1 H/E 各一次 no-intervention；P5 B 同 checkpoint 的 belief-only/selective 各一次。先拟用 Gemini 3.8 Flash；另一个家族需另行批准，不自动加样本。相同模型/参数/Schema、8 决策、12 primitive、4096 输入上界、512 输出上限。P5 处理提示长度不同是已知混杂；token 预算上限相同，真实消耗计入成本。若要声称内容而非长度带来优势，需另审长度对照，不把本次小样本直接当论文因果证明。

预注册 JSON+SHA256 绑定源码、模型目录、Prompt、Schema、manifest 和具名 checkpoint。文件默认独占创建，不覆盖已冻结注册。任何后续 transport 接入、更改 reasoning 参数、最终 code commit 都需形成带变更理由的新审批绑定，保留 Stage A 版本。

状态保留 SUCCESS / AGENT_TASK_FAIL / HARNESS_FAIL / BUDGET_TRUNCATION / UNIDENTIFIABLE。没有静默排除；无法区分原因就 UNIDENTIFIABLE。首条 review 后才继续，无重试、模型替换或成功样本筛选。缺费率、cache/思考 token 语义、实际结算汇率仍阻断收费。既有 56 笔未知账单全额保留；本批建议≤¥8，继承 Gate2≤¥40、项目≤¥100、警戒¥90，限制同时检查。

## 各线 Evidence Card（Stage A）

| 线 | OBS 支持率/分母 | 已有 SIM/CF 与本轮校准 | 强模型缺口 | 决策及最便宜反证 |
|---|---|---|---|---|
| P1 | UNKNOWN / 0 | 旧 Gate2 反思失败；新 H/E/O/U 真值可区分 | UNKNOWN | CONTINUE：先冻结 H/E 自然对，正确处理就是负结果 |
| P2 | UNKNOWN / 0 | 两 checkpoint 通道内容和状态对齐 | UNKNOWN | HOLD 收费：先审投递层语义，再批准一对 C1/C2 |
| P3 | UNKNOWN / 0 | 有自然成功、有恢复、有穷举不可恢复和干预危害 | UNKNOWN | HOLD 收费：三类均保留，不只研究失败 |
| P4 | UNKNOWN / 0 | 两步=精确最优；简单 IG 在 C/D 也最优 | 未测试；不需要先测 LLM 证明 DP | HOLD 复杂算法：当前精确任务已被简单基线解决 |
| P5 | UNKNOWN / 0 | 旧四组成功；新 A/B/C 有真实代际依赖和成本差 | UNKNOWN | CONTINUE：B 的同 checkpoint 对照；若一致则记录饱和 |

ALFWorld 仍为外部 OBS 接入项，真实 reset 尚未通过，不能把 CDW 的校准分母转成公开 Benchmark 统计。
