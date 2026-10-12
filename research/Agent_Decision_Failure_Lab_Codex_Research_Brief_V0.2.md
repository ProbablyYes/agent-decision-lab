# Agent Decision Failure Lab｜研究背景、实验机制与 Codex 执行协议 V0.2


# 研究起源与科学动机（必须先读）

本项目不是“做五个 Agent Demo”，而是从一系列研究问题出发：**Agent 在不确定的长程任务中，为何会自信地继续错下去？** 我们系统学习过 UQ/Calibration、POMDP/Belief Revision、VoI/Active Diagnosis/Dual Control、Failure Attribution/Recovery、Metacognition/Monitoring/Intervention、RL/Reward Design/OPE/Causal Evaluation。实验不是为验证某个既定算法优越而设计，而是识别 *实际失效链条*：证据存在 → 是否被注意 → 是否改变显式判断 → 是否调整计划 → 是否执行新行动 → 任务是否成功。

最初两个研究问题：
A. 缺少外部信息、隐含需求或环境状态时，Agent 何时需要 ask/retrieve/probe？什么信息最值得获得？
B. 已有 hypothesis 与工具执行结果冲突时，是 hypothesis 错了、execution 错了，还是观测不足？下一步应采取何种行为？

在学习中衍生出五条**独立**研究线和若干子猜想。五线可能在未来形成不同论文，也可能交叉，但不能在实验之前先合并、先确定题目。阶段性输出应该能发现某个猜想被反驳，而不只是展示积极结果。

特别强调：**不要把 Exploration 和 Execution 定义为互斥二选一或固定的阶段转换。** Agent 的实际操作可同时获取信息、检验假设、推进目标、修改环境、修复执行、更新 Belief 或计划。可研究多类型、组合和层级行动，也可以继续、不介入、等待。所谓“正确时机”是基于目标、状态、成本、风险、恢复机会与行动长期价值的比较，而不是预先标注一个神奇切换点。

## 五线产生的具体洞见与可证伪猜想

### P1：假设冲突与诊断性恢复
动机：工具返回失败不等于原来的假设错误。也可能只是命令未执行、生效状态不对、验证工具有问题，或者证据仍不足。在长程任务中，错误归因会引发错误重试、过早推翻假设或持续沿错假设行动。
- P1-H1：在“表面反馈相似、隐藏根因不同”的任务上，现有 Agent 往往选择同一类恢复动作，造成系统性错误。
- P1-H2：允许低成本、能区分竞争解释的诊断动作，将优于一律反思或重试；但在证据已经足够时额外探查可能有害。
- P1-H3：区分 hypothesis error 和 execution error 之后仍可能失败，原因在实际行动能力不足，应单独报告。
- 反证方式：如果 Agent 在盲评下已能稳定区分根因，或 Oracle 归因标签不能改善最终成功率，则当前 P1 设计缺乏改进空间。
- 外推风险：CDW 的人工根因标签易于获得，ALFWorld 未必含类似可观察机制；不可由模拟结果声称自然频率。

### P2：正确反馈为什么没有转化成正确行动
动机：先前的 Agent Checkpoint 思考中，给出正确事实并不总提升任务结果。正确事实可能没有被注意、没有改变显式 Belief、没有改变计划，或者行动仍沿旧路线；也可能行动已合理变化但不具备成功所需能力/预算。这是研究假说，不要伪称已有完整统计验证。
- P2-H1：同一真实事实、相同信息量，在不同的 User/Tool/Memory 载体下，显式采纳和实际行动分布不同。
- P2-H2：信息角色的变化不一定等于信任程度更合理；错误工具反馈可能有害。
- P2-H3：直接告知结论 vs Agent 自己运行工具发现，是另一种效应；必须匹配额外工具历史、观察、费用和状态，不要混为同一实验因子。
- P2-H4：复述正确事实不等于 Belief 真的进入行动策略；要分层测 Reception / Belief Adoption / Plan Change / Action Change / Outcome。
- 反证：若角色随机化在匹配后没有可重复差异，或行为完全由任务能力/预算决定，就不能声称来源效应。

### P3：干预价值与恢复时机
动机：Monitor 能预测失败并不代表干预有效；提醒、额外证据、重规划、回滚都有成本和损害原本成功任务的风险。风险概率、可恢复性、净干预价值是不同问题。
- P3-H1：相同失败风险、不同恢复机会的状态，其最优动作不同。
- P3-H2：固定提醒、固定回滚可能造成负收益，No Intervention 必须是真实候选。
- P3-H3：等待下一条观察、先进行诊断、局部修复或组合干预，可能优于“立即警告”；无需假定唯一正确干预时间。
- P3-H4：训练时只评估固定后续干预，未必能代表以后继续动态调整的长期价值（与 MemShift 的监督/执行差异有关，属于我们的待检验推断）。
- 反证：若无干预与 Oracle 结果无显著可测差距，不应先开发复杂价值网络。

### P4：多步信息价值与开放元动作空间
动机：单步信息增益可能低估准备性动作、互补信息获取、既推进任务又获得信息的动作；另外过度探索与盲目继续执行都可能低效。
- P4-H1：必须先准备/校准工具才能获得可信信息时，第一步 IG 很低而长期价值高。
- P4-H2：同一动作可以是 probe+execute，不应强制按 Explore/Execute 标签监督。
- P4-H3：一个浅层有限前瞻或学到的 value proxy 是否能在更少 rollout 下接近长程最优？也有可能简单 2-step lookahead 已足够，应保留负结论。
- P4-H4：必要的元动作集合是否可根据环境动态产生，而非完全固定标签？这是第二轮研究候选，不要求 Gate 0 开发无限动作生成器。
- 反证：若单步方法与 Oracle 无差距，则该任务无法测试多步价值机制。

### P5：Plan Reconciliation（独立研究线）
动机：Belief 已经更新、已有计划仍基于旧前提执行。全面重规划会遗失有效工作，完全继续会执行过期动作；正确的策略可能是局部计划依赖修复，也可能是保留旧计划并进行新验证。
- P5-H1：结构化的前提/效果依赖能帮助定位旧计划中哪些节点真正失效。
- P5-H2：选择性修复可能降低重复操作成本，但不一定提高完成率，需要同时报告。
- P5-H3：当证据错误或不可靠时，过快废弃旧计划可能有害。
- P5-H4：计划表示带来的额外 Token/结构成本必须与等预算全量重规划比较。
- 反证：若原 Agent 已自动处理好依赖，或者选择性修复不能优于普通全量重规划（等预算），不能直接宣称机制创新。

## 与既有论文的关系（用来防止重复，不是结果背书）
- ACL 2026 VoI：单步或有限信息获取的决策价值；“询问有成本”不是新颖点。
- ICML 2026 EAPO：学习探索相关价值；“奖励探索”不是新颖点。
- ICML 2026 ΔBelief-RL：通过正确目标概率变化进行中间信用分配；要注意 GT 信息和奖励投机。
- ICML 2025 POPPER：主动证伪与假设验证；普通“发现矛盾就反思”不充分。
- ICLR 2026 DoVer：通过真实干预检验 Agent 失败归因。
- 2026 Intervention Paradox：高 AUROC 并不保证干预收益。
- ICML 2026 OPE + Reward-Shaping Control Variates：少样本长期价值估计有统计限制。
- MemShift（用户学长提供的内部匿名稿，不得外传）：动态参数记忆，用 Checkpoint 反事实 return 监督更新方向；因此“使用 checkpoint 比较未来收益”本身不是新贡献。
以上为研究背景，不能替代最新文献完整复核；正式算法设计之前必须逐项查重、确认 benchmark 可测缺口。

## 科研工作方法
明确四类证据：1) 自然 Agent 轨迹 OBS 表明问题的实际发生率；2) 研究者受控构造 SIM 用于机制检验；3) 从同 Checkpoint 分叉的 CF 检验干预后果；4) Oracle 提供有特权信息的上界，用于检测机会而非充当部署基线。
不要选择性只分析自然失败任务，也要检查基线可能成功的轨迹被干预破坏多少。
研究结果要区分“反馈被复述”“Belief 报告更新”“计划文本更新”“真实工具行动更新”“最终成功”；对同一轨迹的多个连续状态不能当作独立实验任务。


# 执行版实验细则（沿用 V0.1，以下为具体操作约束）

# Agent Decision Failure Lab｜Experimental Protocol V0.1

版本：2026-10-12。性质：第一轮科研机制 Pilot，不是正式 Benchmark/SOTA 结果。研究总目标：确定五类决策失效的真实出现情况、可恢复性、Oracle 上限与强简单基线差距，然后再决定可训练算法。

# 1｜不可改变的约束

独立保留 P1 假设冲突和诊断恢复、P2 正确反馈→实际行动、P3 干预净价值和恢复时机、P4 多步信息价值及开放/组合元动作、P5 Plan Reconciliation（Belief 已更新而旧计划未同步）。共享平台但不默认为一个论文主题。环境为自建 Controlled Diagnostic World（CDW）和 ALFWorld 文本环境。只用冻结 API Agent 和测试用 Mock Agent；不训练 30B，也不把探索/执行硬编码为二元模式。第一轮 API 总支出≤¥100，推荐执行到¥90即停并预留¥10，任何调用前须人工批准并核验模型价目及币种。

# 2｜两类证据，不能混算

A 自然轨迹（OBS）：Agent 无额外干预执行，用于估计真实失败现象出现频率，需保留采样规则与全部分母。B 受控干预（CF）：相同 Checkpoint、任务、环境、剩余预算下改动一种明确的干预因子，用于对比结局；模拟造出的场景标 SIM，知道隐藏真值的理想干预标 ORACLE。ORACLE 是机会空间估计，不是部署算法。不得混淆自建任务与 ALFWorld 官方 Benchmark 分数。

# 3｜CDW 环境接口与设计

实现 reset(task_id, seed)、snapshot()/restore(checkpoint)、step(action)、get_observation()、score(). 隐藏环境状态包括 root_cause、execution_fault、observation_reliability、world_state、plan_DAG、remaining_budget、rng_state；Agent 只看到受限 observations/tool results。工具至少包含 inspect、diagnose、apply_change、verify、undo；可支持 ask、wait 和显式组合动作。动作 kind 不限 Explore/Execute；宏动作展开后逐步计费。至少三个任务族：错误归因、证据冲突与计划依赖、多步互补诊断/准备动作。必须有实际状态转移及可判断的任务完成条件，而不是标签分类小游戏。

# 4｜P1 实验：假设冲突与诊断恢复

目的：执行失败后，Agent 能否区分假设错误(H)、假设正确但执行未生效(E)、目前证据无法区分(U)？控制三类真值，最好让 H/E 的表面失败反馈近似。候选组：自然继续、泛化反思、额外诊断机会、Oracle 错误类型。指标：正确归因、诊断行动的区分价值、无效重试次数、任务成功率、成本。严禁把 Oracle 类型直接泄露到普通组。若 Oracle 提升几乎为零，不能断言缺口可学。

# 5｜P2 实验：反馈进入但行动未变

目的：区分 Reception、Belief Adoption、Action Adaptation、Outcome。以相同正确事实、相似文本长度，随机化 User 消息 vs Tool 消息，并保留无反馈组；结构化 Belief 留待第二阶段独立因子。记录模型的结构化 belief 报告（只是可观测代理，不能当作内部信念真值）、前两次真实工具动作、任务成功与成本。附加少量不可靠证据测试，防止优化成盲从工具消息。

# 6｜P3 实验：净干预价值

目的：高失败风险是否等于值得干预？从自然轨迹中同时保留原本成功与失败的 Checkpoint。比较 No Intervention、Generic Warning、Diagnostic Probe；支持时再加入 Rollback/Repair。主要结果为相对不干预的成功率差、额外成本、误伤率和恢复率。时间点差异先作为观察变量，不在第一轮穷举“最佳时刻”。

# 7｜P4 实验：多步/组合行动的价值

目的：验证单步信息增益是否低估准备动作、互补诊断与同时具有探索/执行价值的工具操作。候选基线：即时进展贪心、一步 Information Gain、二至三步 lookahead；小规模 CDW 可计算有限时域 Oracle。指标：最终回报、任务动作成本、冗余探查、低即时收益但高长期价值动作是否被选中、已知价值下 regret。动作可层级/组合，不限定切换时刻。

# 8｜P5 实验：Plan Reconciliation

目的：提供正确新证据后，旧计划只有部分节点失效，Agent 是继续执行过期动作、全盘重规划，还是选择性修复？CDW 计划用带前置条件与依赖的 DAG，标记 GT 失效节点。对照：Belief-only、Full Replan、Selective Reconciliation、Oracle invalid dependency；另有自然继续对照。指标：失效动作执行率、有效节点保留率、修复成本、完成率。P5 独立出报告，不并入 P2。

# 9｜样本数、预算分阶段闸门

Gate 0（¥0）：每条线 3–5 个确定性 fixture，使用 Mock/ScriptedPolicy 检查 GT 隔离、状态回放、工具效果、评分及日志。Gate 1（累计≤¥10）：每线 1–2 个 API 场景，每个至多两分支，验证指令格式及真实账单。Gate 2（累计≤¥40）：CDW 上每线最多 12 个任务（预设分层，若有三类各4个）；起始只跑 baseline + 信息量最高的一个对照，补测前需核算成本。Gate 3（累计≤¥70）：ALFWorld 先跑 10 条自然轨迹，实际观察到可用信号且预算允许再扩到 20–30 条；只在有效重放 Checkpoint 分叉。Gate 4（累计≤¥90）：剩余预算集中复测 1–2 条有迹象的研究线，事先确定新任务和分组。¥100 为不可突破上限，≥¥90 暂停实测；所有阶段需负责人明确批准，不自动进入下一关。若每次调用单价未知、token 用量不可读或无法控制并发，暂停调用。样本是 Pilot 工程建议，不宣称统计显著。

# 10｜预算与估计误差

每次 API 请求记录模型精确版本、input/output/cached tokens、官方计价版本、人民币汇率时间、实际/预估成本、失败重试成本；每次发送前预留最大输出 token 可能成本。不要在供应商延迟结算时同时并发大量请求。若账单不可对齐，先用单线程一请求验证。比较成本时同时给出 tokens、调用次数、工具次数。

# 11｜实验公平性与统计

固定模型、prompt 模板版本、工具接口、任务与剩余预算；分支从相同环境快照恢复并验证一致性。对照条件顺序随机化；seed 相同不能保证 LLM 的后续文本完全一样。随机化/配对以 task 或 checkpoint 为单位，不把同一 task 的多个种子或多分支当成独立任务计数。预先指定主要指标（最终成功/原 Benchmark 官方得分）和辅助指标；展示每组 n、成功次数、差值、分母、负结果。小样本只描述趋势，不宣称显著；条件充分时计算配对置信区间。任何 Checkpoint 筛选条件和重放排除数量均须报告。

# 12｜文件与日志契约

仓库：AGENTS.md、README.md、research/RESEARCH_MAP.md、research/DECISION_LOG.md、research/OPEN_QUESTIONS.md、research/EXPERIMENT_PROTOCOL_V0.1.md、src/adfl/{world,agents,interventions,evaluation,budget}、experiments/{p1,p2,p3,p4,p5}、configs、tests、results。每个 run 下存 config.yaml、trajectory.jsonl、events.jsonl、metrics.json、report.md；记录 task_id/template_family、来源 OBS/SIM/CF/ORACLE、split、条件、checkpoint hash、GT 隐藏路径、模型、prompt hash、seed、每步状态/行动/工具结果、tokens/cost、完成判据、被排除的样本及原因。API 密钥只能走 .env，不入版本库。

# 13｜自动化测试与停止条件

运行 pytest（无 API）：状态恢复重放；hidden GT 无泄漏；计划 DAG 依赖 GT；所有五线评分器；模拟支出达到¥10/40/90/100时正确告警与阻断；超时、重试、损坏 JSON、缺失实验臂均保留日志；报告不默默删除失败案例。任一重大错误即停止实验。若 Oracle 没优势、强基线已接近上界、失败机制出现频率很低、环境不可靠、单价不可核对、发现泄漏或预算逼近上限，也停止该阶段并回报。

# 14｜Codex 实施顺序

M0 初始化仓库、测试/日志/预算骨架；M1 CDW 三种任务族、snapshot/restore 与 Mock Agent；M2 P1–P5 的评分函数与示例 run；M3 冻结 API 接口和 dry-run；完成 Gate 0 后暂停，交 HANDOFF.md 人工审查，再批准 Gate 1；随后受控 Pilot、ALFWorld 官方安装与真实自然执行、必要时定向复测。Codex 不得自行“优化指标、调整分组、搜索测试集、扩大 API 预算”。

# 15｜第一次交付验收

必须有：Git commit/id；项目目录树；pytest 通过数量及失败输出；每线至少 3 个不调用 API 的 fixture；Mock 示例完整原始轨迹；GT 隔离说明；¥0 API 实耗；预算守卫测试；未实现项清单；交接报告 HANDOFF.md。研究负责人审查协议前禁止发出真实 API 请求。


# 实现与沟通规范（Codex 必须遵守）

## A. 实施阶段和第一个真实 LLM 时间点
**不是整个第一阶段都用 Mock Agent。** Mock 仅校准实验仪器，研究对象必须是真实冻结 LLM Agent；但在基本环境错误未消除之前，真实 LLM 数据无效。
1. M0 最小项目骨架：Python 3.11+，依赖锁定，pytest，配置校验，预算日志，API adapter 接口；提供运行命令和 gitignore。
2. M1 最小 CDW：至少覆盖 P1 的 H/E/U 三类可执行工具场景、P2/P5 的部分计划依赖场景、P4 的两步互补工具场景；实现 reset/snapshot/restore + hidden GT 隔离。
3. M2 Mock 校准（约 3–5 fixtures/研究线）：必须证明工具有实际状态变化、评分器判定正确、恢复一致、秘密 GT 无泄漏。**不要为了做满所有 Demo 无期限推迟真实 LLM**，可先实现足够覆盖五条线的共享最小版本。
4. M3 API Agent 接口：与 CDW `step()` 真正循环交互，LLM 返回可解析动作；保留完整消息角色、工具调用与结果、计划快照、时延、token。先实现 dry-run 估价/限额功能。
5. **Gate 1：暂停、由研究负责人审批，然后立即用真实冻结 LLM API 运行首批 3–5 条端到端轨迹**，至少覆盖 P1、P2/P5、P4；先检查实际行为，再为 P1–P5 扩充分支。禁止将 mock 任务分布代表真实 benchmark。
6. Gate 2/3/4 再按预算、实际失败机制和 benchmark 兼容性逐级放行。API 调用不自动开始；负责人明确批准 Gate 1 才可扣费。

## B. 真实模型实验的公正性
- 固定 `model_provider/model_id/model_revision`（若供应商提供）、temperature、max_tokens、提示模板版本、工具 schema、动作预算与定价资料。使用单一冻结模型做主要实验，额外模型仅作后续泛化验证。
- 真实 API 不代表可以随意多次调用直到出现“喜欢的”结果。记录所有失败、超时、重试，必要时保留原始请求/响应的脱敏哈希。
- 所有组必须从同一 checkpoint 及同一可见上下文恢复。P2 User-vs-Tool message 角色对照必须保证提示文本事实一致，不要让 Tool 组偷偷获得额外真实观测。
- 可将内部 belief 报告设计成可选的结构化自述，但它是 *代理测量*，不是内部神经 belief 的直接观测。若采集该报告改变了行动决策，它本身就是新干预，须独立对照。

## C. 前置预算守卫
- 在任何 API 调用前让负责人提供模型名、官方定价和货币换算来源；若未知，先暂停。
- 总上限 ¥100；执行期在累计 ¥90 暂停，至少留 ¥10 对账缓冲。Gate 1/2/3 累计上限分别 ¥10/¥40/¥70。
- 每个请求计算保守的 input 和 max_output 上界，先检查剩余预算。若不能保证并行账单控制，禁用并行请求。
- API 失败、重试同样计费。提供 `--dry-run`、`--max-spend-cny` 和 `--require-approval`。
- 通过配置显式禁止测试集调参和自动高成本重试。

## D. 强制结果物
每次实验至少输出 `config.yaml`、`trajectory.jsonl`、`metrics.json`、`events.jsonl`、`report.md`，完整列出采样分母、所有条件、跳过/失败任务、实际 API 费用与未运行的对照。
每次阶段结束输出 `HANDOFF.md`，用自然语言解释：实际执行了什么；发生了什么；什么尚未观察到；发现了哪些与预期相反的行为；有什么新猜想；哪些变化需要研究者批准。
Codex 可以主动提出新机制/实验，但必须写入 `OPEN_QUESTIONS.md`，包含可证伪预测和最低成本的对照；不能擅自改变主要协议。
真实报告必须写明“机制 Pilot（不可当作统计显著或 SOTA）”，原始 OBS 与合成 SIM 的性能分别报告。
