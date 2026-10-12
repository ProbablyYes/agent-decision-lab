# Decision log

2026-10-12（Gate 2 配对实测结束）：103项测试通过；七分支、两个 checkpoint、37次收费模型请求，无重试。P1 无干预成功5动作、反思失败8动作、Oracle归因成功3动作；反思分支显式知道 A不兼容却把prepare当作修正配置，重做A，决策horizon耗尽而非财务预算不足。P5 四组均成功，Belief-only/整体重规划/选择性修复/Oracle依赖提示工具数4/6/5/6，成功率饱和，未调整任务。账户USD累计used增量0.001090725非逐请求账单；新预留¥0.850926、含历史累计¥0.981665，56笔账单未核验继续保留。Gate 1所有文件哈希不变，账本增量迁移与完整性正常。源任务新语义和人工构造不得当作算法提升；新猜想写入OPEN_QUESTIONS。暂停共同审查，不扩展其他真实研究线。

2026-10-12（g1-01真实执行）：仅1次真实请求，HTTP200，response model=qwen/qwen-flash，usage输入578/输出65/总计643，cache未知。供应商返回tool_calls及finish_reason=stop，冻结适配器要求tool_calls而拒绝；0 primitive，success=false，属于仪器协议兼容性中止，不能当作Agent错误归因。原始失败保留、不重试、不改冻结实现、不执行后两条。实际账单未知，预留¥0.006881；公开价参考估算约¥0.000181非账单。生成首条报告并人工复核，追加实际响应形状回归，最终78项通过；账本备份在.state内不入Git。暂停审查。

2026-10-12（首条评审）：用户原则确认qwen/qwen-flash，先要求核验账户字段；公开控制台跳转登录，无法核实。期间用户进一步明确“大概估价即可”、本地API可用。依最新授权仅g1-01启用估算准入，不要求伪造账户确认；实际收费和缺失cache字段保留未知，预留不释放。其余轨迹在此模式下明确阻断。增加model_access独立确认字段及首条¥1持久化上限，保留8决策/12 primitive、¥8本批/¥10阶段。新增首条报告从账本自动生成，并在对账后更新；77项无网测试通过。公开Models价目在发送前无鉴权再次核验，所选模型元数据未变。没有改变五线指标、动作空间或开发新算法。

2026-10-12：完整读取实际存在的两个 V0.2 文件；用户指定的短文件名不存在，不改名或覆盖源文档。历史 EXPERIMENT_PROTOCOL_V0.1.md 不存在，无法逐文件比较；V0.2 内嵌的 V0.1 操作细则照用，研究背景和实施限制以 V0.2 为准。

2026-10-12：M0–M3 使用标准库共享最小平台，Mock 三类环境覆盖五线，每线 3 个确定性 fixture。禁止真实 API；API adapter 只接收注入的测试 transport。固定 Python 开发依赖版本，无第三方运行依赖。

2026-10-12：预算预留最大输出，未知账单按预留额锁定并停止；不自动重试；同 guard 禁止并发。阶段限额 10/40/70/90，硬上限 100。真实跨进程账单与批准令牌尚未实现，Gate 1 前不得接入网络。

2026-10-12：未收集的 attribution/belief/plan/Oracle 数据输出 null 并报告 unmeasured；不以 scripted 成功替代机制验证。不实施全套研究算法、不改变五线或指标。

2026-10-12（Gate 1A）：依用户追加指令仅准备，不执行 Gate 1B。未打开 .env 或读取凭据；只检查非密钥配置和访问公开 Models API，保存 159 个模型的实际元数据/定价。优先比较 Qwen Flash/Turbo/3.5 Flash，推荐精确 id qwen/qwen-flash，仍 model_confirmed=false。USD/token 单位由供应商文档明确，账户币种和实际结算另待确认。使用 ECB 2026-10-09 参考交叉汇率估算，不冒充供应商结算汇率。

2026-10-12（Gate 1A）：增加 urllib 单次 HTTPS transport、拒绝重定向/自动重试、真实 native function tool schema、审批前不加载凭据。Prompt 从 Gate 0 JSON 文本载体改为 v0.2-native-tools-1，保持动作空间、环境及主要指标，optional belief/plan 不变。此载体版本变化已显式记录；首批三条不是反馈角色比较实验。

2026-10-12（Gate 1A）：SQLite 项目唯一账本，整数微元、事务性审批/预留/响应/状态恢复；保留未知费用、核验实际账单后才能释放预留；跨进程不重置花费，不自动重发未知请求。审批绑定单条轨迹及配置/源码/Prompt/Schema 指纹。预登记顺序以用户最新要求为准：P1 H、P1 E、P2 plan H，各 seed=0、最多8决策/12 primitive，累计本批8元/阶段10元。首条实际审查前阻断后续审批。

2026-10-12（Gate 1A）：无网测试发现并修复 crash-reservation 的 NULL usage 账单解析路径；原 Gate 0 测试和新增 transport/跨进程/恢复/未知费用测试合计72项最终通过。GATE1_REPORT.md 明确尚未执行，不填造真实结果。停止等待最终模型确认及第一条批准。


## 2026-10-12 Gate 1 native-tool compatibility and scoped continuation
User explicitly authorized g1-01b, g1-02, g1-03 with unchanged model/prompt/schema/limits. Accept stop only with one complete valid native cdw_action; retain compatibility anomaly. Original g1-01 remains immutable. Unknown bills stay reserved; named continuation may proceed past terminal unreconciled runs without marking bills reviewed or releasing liabilities. 86 offline tests passed, including the saved actual g1-01 response and matching next-request Tool Message. Each new run cap CNY1; batch cap CNY8 remains stricter than Gate 1 CNY10. No new research algorithms.

Three authorized runs completed: six decisions/primitives each, all task-success; 18 new requests, no retries or model fallback. Original g1-01 file hashes unchanged. Reopened ledger integrity ok, total 19 unreconciled requests and CNY0.130739 reserved exposure; actual bills unknown. E trajectory explicitly misdescribed execution-failure evidence, then succeeded; no causal/statistical claims. Paused for review.


## Gate 2A paired pilot v1, 2026-10-12
User authorized minimal P1/P5 contrasts only after Mock verification. Versioned PilotWorld adds ambiguous H/E failure and partial DAG invalidation without modifying Gate 1 CDW/tasks/results. Exact arms, random order, fairness limits and metrics pre-registered in research/GATE2_PROTOCOL.md. 103 offline tests pass; Mock native loops, checkpoint forks, P2 legal matched carriers, P3 natural successes, P4 complementary probes and dual-effect staging calibrated. Scripted success differences are not Agent scientific evidence. USD account lifetime consumption checked via documented read-only balance endpoint, not attributed to project. Gate 1 unknown CNY0.130739 remains reserved. Additive same-ledger pilot authorization: cumulative CNY40, batch CNY5, per branch CNY1; no retries, no later arms.

## V0.3 Stage A（2026-10-12）

用户仅授权Stage A，不授权附件中的Stage B收费调用。完整阅读V0.3任务书并结合V0.2、研究地图和Gate1/2记录；五线独立、最终成功指标不变。新增src/adfl/v03独立版本和新Schema，不修改旧CDW/PilotWorld/transport语义或旧实验结果。任务覆盖P1 H/E/O/U、P2匹配合法消息通道、P3自然成功/可恢复/预算内不可恢复、P4显式有限POMDP和belief-state精确DP、P5部分完成非线性DAG和代际依赖。144条manifest，holdout只冻结不rollout；72个design/dev世界校验和66条特权Mock成功路径均为仪器证据。最终138项pytest通过（原103项+新增35项），保留开发中4项P4 JSON tuple/list恢复失败的initial XML；修复不作算法提升。

P4带终止叶值的两步基线在四世界均达最优，暂停复杂方法扩展。P5三种Mock校准脚本全部成功，明确成功饱和与成本差，不据此推断强模型失败。过期依赖被工具拒绝，记录attempt与execution区别。Oracle A/B可由普通信息推导，C未audit时才有真特权。新猜想和反证追加OPEN_QUESTIONS。

匿名公开GET核实OFox159模型，推荐google/gemini-3.8-flash与跨家族anthropic/claude-sonnet-5.5；旧Gemini3.5/3.7自动路由风险有官方证据。拟四条dev seed10实验保守预留6.907584元，单独批次建议8元，账户实际费率/cache/reasoning/FX仍阻断；不将估算当账单。只读原SQLite，全56笔未知账单保留0.981665元；全部表逻辑哈希不变，262个旧结果哈希不变。没有收费推理、模型回退、新审批或预算释放。

核查官方论文和代码树/commit，DoVer实际代码已定位microsoft/ACV/misc/DoVer；外部运行能力保持未核实。ALFWorld官方配置/split/reset接口已读，Windows Jericho依赖dry-run失败，smoke明确BLOCKED_DEPENDENCY，无OBS自然轨迹。SiliconFlow仅列备选，未保存或使用新增密钥。生成V03全部指定文档和待审查注册/hash，暂停等研究审查；后续Schema接入收费runner须另行绑定最终commit并通过Mock网络/预算检查。
