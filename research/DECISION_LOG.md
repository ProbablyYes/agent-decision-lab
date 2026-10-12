# Decision log

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
