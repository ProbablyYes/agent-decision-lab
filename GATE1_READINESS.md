# Gate 1A readiness

日期：2026-10-12。工程与无网验证已完成；**尚未具备收费放行条件**。真实推理调用 0，实际新增花费 ¥0，未打开 `.env` 或读取 API Key。模型与价格详见 `GATE1_MODEL_SELECTION.md`，当前推荐配置仍未获人工确认。

## 当前模型、接口和价格

OFox，`https://api.ofox.ai/v1`，拟固定 `qwen/qwen-flash`。公开 Models API 实际返回输入/输出/缓存读/缓存写为每百万 Token **USD 0.022/0.22/0.0043/0.027**。目录模型标识 qwen-flash 不包含不可变日期。实际账号权限和控制台结算尚未验证。

[Chat Completions 文档](https://ofox.ai/zh/docs/api/openai/chat-completions) 支持 `POST /v1/chat/completions` 和 native tools；实现采用单个 `cdw_action` function tool，模型选择结构化 action，环境执行后通过匹配 tool_call_id 的 tool 消息返回观察，再继续多轮。没有自动文本/JSON fallback，没有自动换模型，没有重试。新增 Prompt 版本明确记录协议载体变化，不新增强制 belief 采集或科学干预。

temperature=0、max_tokens=512、seed=0、8 决策/12 primitive 已在配置和校验中固定。结构化动作先完整验证再执行，超长/嵌套 macro 拒绝，不让部分非法工具动作改变状态。原五线指标与环境未修改。

按 ECB 2026-10-09 参考交叉汇率估算，3 条保守预留 ¥0.165144、5 条 ¥0.275240；这是含缓存附加费用预留和二倍缓冲的目录价估算，不是已核验账单。[OFox 计费说明](https://ofox.ai/zh/docs/develop/observability/pricing) 将输入、输出、缓存输入列为收费项，实际费用需控制台核对。未知费用不是零。

## 持久化预算、审批与恢复

真实入口 `python -m adfl.gate1` 使用唯一项目路径 `.state/gate1.sqlite3`，CLI 不提供任意账本路径。SQLite BEGIN IMMEDIATE + synchronous=FULL；整数微元计费；先持久化预留再发送。预留、计算价和已核验供应商账单分开保存。请求 pending/ambiguous 时所有进程不能发下一请求；进程退出不释放预算。没有账本即停止，不自动建立零余额账本；init-ledger 只能首次创建，覆盖现有文件会失败。

累计本批 cap=¥8，Gate 1=¥10；当前入口只实现 Gate 1，不授予后续阶段。Gate 0 的 ¥90 运行停止线/¥100 硬限测试继续保留。删除账本、复制仓库另建账本或手工修改数据库属于操作员绕过，程序不能防御；必须保留账本及离线备份，其他账户调用不在本项目账本覆盖内。

审批保存 run_id、整个配置/源码/Prompt/Schema 指纹和人工证据。每次发请求都检查审批；改动配置/源码后旧审批失效。当前实际账本未初始化、没有收费审批记录；需确认最终配置后初始化，避免把未确认草案当作批准配置。

恢复逻辑：只有预留、没有持久化响应时视为结果/费用未知，不重发；已有持久化响应时恢复旧环境并只应用该响应；环境状态、消息、决策次数和工具轨迹在同一事务提交，避免应用两次。工具执行后、事务提交前退出也可从已保存响应回放一次。

超时、HTTP 错误、损坏 JSON、模型不符、输出截断、缺失 usage/cache 统计均留存响应/错误。未知成本保留最大预留并暂停。已知计价但格式错误计入分母，终止，不重跑。网络异常保留异常类别，不保存可能包含认证头的异常字符串；供应商原始响应会脱敏，密钥绝不写日志。

费用核验人工导入逐请求实际人民币账单及 Token 统计和来源，不能将计算价直接冒充账单。差异超过约 1% 或 2 微元会保存实际负债并阻断，需调查。缺失统计的崩溃请求仅在操作员确认进程停止、账单核验完成后手工 close-uncertain，作为失败保留，绝不重发。首条完成后所有请求账单核验+人工 review 才允许审批第二条；第二条同样要求独立审查，CLI 不批量跑三条。

## 测试与复现

全部 Gate 0 测试重新运行，**72 passed**（42 项原测试 + 30 项新增测试），无真实网络。新增测试覆盖真实 urllib transport 的 Mock HTTP、授权前不加载凭据、超时/429/重定向/损坏响应、native assistant-tool 消息配对、GT 隔离、模型不符、8 次决策限制、超长 macro、未知缓存用量、跨进程单请求、预算重启、原子事务回滚、响应恢复不重复收费、崩溃人工关闭、账单差异和后续轨迹审批阻断。

发现并修复一处恢复路径错误：崩溃前 usage 尚未保存时，账单核验代码对 NULL 作 JSON 解析；补充测试后允许保留未知 usage，并在明确人工关闭路径处理。最终无失败。

无网命令（当前可执行）：

```powershell
python -m pytest -q
$env:PYTHONPATH = 'src'
python -m adfl.gate1 prepare --dry-run --max-spend-cny 8 --require-approval
```

prepare 当前应输出 ready_for_approval=false、五个待确认项、预算包络；不会构造网络请求，不读取密钥。

以下为**未来获准后**执行命令，本轮没有执行。先记录账户价格/汇率/cache 语义证据，确认并冻结配置的五个 confirmation 状态；不能仅为绕过守卫盲改为 true。确认配置后初始化并逐条审批：

```powershell
python -m adfl.gate1 init-ledger
python -m adfl.gate1 approve --run-id g1-01 --evidence-file approval-first.txt
python -m adfl.gate1 run --run-id g1-01 --require-approval --max-spend-cny 8
python -m adfl.gate1 status
python -m adfl.gate1 reconcile --billing-file bill-request-1.json
# 为首条中的每次请求导入独立实际账单；全部核验后：
python -m adfl.gate1 review --run-id g1-01 --evidence-file review-first.txt
```

approval-first.txt 必须引用研究负责人的明确批准和已审查的模型/价目；不会自动生成。bill-request-1.json 格式见 configs/billing.example.json；未知费用必须留 null 并暂停，不能填 0 代替。只有确实账单为零且有证据时才能填 0。遇崩溃保留原账本，重复 run 只可恢复持久化响应，不会重发；若只有在途预留必须人工对账，参见 close-uncertain 的帮助及代码。

## Gate 1B 顺序和剩余风险

`g1-01`: P1 attribution:H；`g1-02`: P1 attribution:E；`g1-03`: P2 plan:H。seed=0，源 SIM，natural_continue 条件。第三条只是 P2 环境上的基线工具循环，不是 User-vs-Tool 反馈来源比较。五条仅作成本对照，不增加本轮运行授权。

阻断项：最终模型确认；账号账单币种；实际输入/输出/cache 单价；实际结算汇率；缓存写入是否是输入子集或附加收费、缓存用量字段及缺失含义。公开文档没有给出 Qwen 经 OFox 转换后的完整 usage/cache 契约。若这些前置核验仍无法得到，将停止并说明，不能假定缓存缺失代表零；最多在另行明确授权下设计单请求对账验证，不自行降低守卫标准。

其余限制：未证明真实工具调用可靠性；未冻结可验证的供应商权重版本；输入字节数上界是保守工程估计，首请求须核对；供应商计价/路由可能变动，收费前需刷新核验；HTTP 错误是否收费未知，保留预留；本地人工审批控制不防恶意篡改。温度为零不保证文本完全确定。

真实结果将写入 `GATE1_REPORT.md`，包含每步观察、动作、工具返回、错误和实际费用；目前该文件明确标记未执行。Mock 结果不代表机制发生率，三条轨迹不作统计结论。现暂停等待最终模型确认和第一条轨迹批准。
