# V0.3 模型、费用与待审查事项

核查日期 2026-10-12。本轮匿名 GET `https://api.ofox.ai/v1/models` 得到 159 个模型，原始响应保存于 `provider/v03/models.json`。没有读取本地 API Key，也没有发起推理请求。目录存在和 tools 声明不等于账户实测权限、transport 正确性或实际收费已核实。[OFox 字段及单位说明](https://ofox.ai/docs/develop/models)规定公开价格为 USD/token；换算如下。

| 候选精确 OFox ID | 家族/近期证据 | 输入 USD/M | 输出 USD/M | cache read USD/M | cache write USD/M | OFox context / max output |
|---|---|---:|---:|---:|---|---|
| `google/gemini-3.8-flash` | Google，目录日期 2026-09-02 | 1.50 | 7.50 | 0.15 | generic=0.083；1h=1.00 | 1,000,000 / 65,536 |
| `anthropic/claude-sonnet-5.5` | Anthropic，目录日期 2026-09-28 | 2.00 | 10.00 | 0.20 | 5m=2.50；1h=4.00 | 1,000,000 / 128,000 |

两者 actual supported_parameters 均为 `temperature, top_p, max_tokens, stop, tools, tool_choice, response_format, reasoning`。Google 目录端点为 `/v1/chat/completions`；Sonnet 另有 `/v1/responses`。拟用 Base URL=`https://api.ofox.ai/v1` 的 Chat Completions；不启用搜索、音视频、远端付费工具和路由回退。工具为本地 CDW primitive。

优先推荐 Gemini 3.8 Flash 作首批主模型：原厂明确面向长程工程和自主 Agent，并声明 function calling、structured outputs、low/medium/high thinking；不是根据 Flash 名称推断其属于弱模型。它仍是 Flash 层级，不能声称代表所有旗舰模型或全部前沿能力。[Google 官方模型页](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)。Sonnet 5.5 为跨家族确认候选；厂商近期发布资料可核实其存在和 Agent 定位，不能用厂商宣传替代本实验结果。[Anthropic 发布页](https://www.anthropic.com/claude-sonnet-5-5)。Qwen Flash 留作历史开发对照。

查到重要版本冲突：OFox 仍把 Gemini 3.5/3.7 标记 `is_deprecated=false`，但 Google 2026-10-08 说明 3.5/3.7 请求自动转向 3.6/3.8。因此不推荐旧 ID 作为冻结基座，也不会在请求异常后自动换成新 ID。[Google 官方变更记录](https://ai.google.dev/gemini-api/docs/changelog)。canonical_slug 的稳定字符串不等于不可变权重；两候选均无可核实的不可变权重 revision。获批后必须记录响应 model；仅凭相同响应字符串也不能证明后端权重固定。

## 费用包络

参考 FX 沿用保存的 [ECB 参考汇率网页](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.fi.html)：日期 2026-10-09，EUR/USD=1.1206、EUR/CNY=7.4992，故 USD/CNY=6.692129216491165；来源快照为 `provider/ecb-fx.json`。这是人民币估算，不是账户实际充值或结算兑换规则。

所有估算按每条最多 8 决策，每请求最多 4096 输入、512 输出。无缓存参考额为 `n×8×(4096×input+512×output)/10^6×FX`。复用原 RateCard 的保守预留：`n×8×[4096×(input+max(input,read,write各TTL))+512×output]/10^6×FX×2`，每请求向上取整到微元；不依赖 cache 折扣，允许输入与缓存附加收费。原始、归一化价目和计算结果见 `results/v03/stageA/cost_estimates.json`。

| 模型 | 条数 | 无缓存参考 ¥ | 保守预留 ¥ |
|---|---:|---:|---:|
| Gemini 3.8 Flash | 2 | 1.069027 | 3.453792 |
| Gemini 3.8 Flash | 4（拟首批） | 2.138055 | **6.907584** |
| Gemini 3.8 Flash | 6 | 3.207082 | 10.361376 |
| Gemini 3.8 Flash | 12 | 6.414165 | 20.722752 |
| Sonnet 5.5 | 2 | 1.425370 | **6.359344** |
| Sonnet 5.5 | 4 | 2.850740 | 12.718688 |
| Sonnet 5.5 | 6 | 4.276110 | 19.078032 |
| Sonnet 5.5 | 12 | 8.552220 | 38.156064 |

Gemini 四条在这些假设下可放入单独¥8批次，单条预留¥1.726896，建议单条cap¥2；加旧未知预留¥0.981665后累计包络¥7.889249，低于 Gate2 ¥40。Sonnet 四条无法放入¥8，不能因为无缓存参考价较低而直接批准；若选它作主模型，应先缩为 P1 H/E 两条或重新审查设计，不自动追加额度。6/12 条表格是容量估计，不是执行清单。

**这些数值不是实际账单或已证明的绝对上限。** 公开 cache_write 字段的 TTL/存储语义、hidden thinking 是否全部计入 max_tokens/completion、账户实际优惠或附加费尚未知。未知项不得按零处理，也不能仅凭 2 倍缓冲宣称全部收费风险已覆盖。

## 账户与审批阻断项

只读审计原 `.state/gate1.sqlite3`，保留全部 56 笔 billed=null 的请求，累计预留¥0.981665，未新增批准、未结算、未改 cap。上次保存的账户余额响应为 2026-10-12 03:16:27 UTC，currency=USD、balance=34.05354207；这是历史记录，不冒充当前余额。Gate2 aggregate used 增量 USD0.001090725 只作辅助证据，没有分摊为逐请求账单或释放预留。

收费前需要审查：

1. 两个候选的账户实际 Token/缓存价、币种、折扣/附加费及兑换规则。公开模型目录只作估算。
2. generic cache_write 与 write_1h 是否分别是写入 token、存储时间收费或互斥档位；缓存统计字段缺失含义、cache read/write 与普通输入的关系。缺失为 unknown/null。
3. Gemini low thinking 的 OFox `reasoning` wire mapping、hidden thinking 的输出上限和收费。Google 不支持 minimal，不能随意猜参数。Sonnet 5.5 原厂要求以 between_tools 替代旧 thinking-off，OFox 映射同样未实测核实。
4. 512 输出上限是否足够保留模型思考与完整动作；如果更改上限，要在看到模型结果前重算费用并冻结新审批。不能因被截断而修改条件追求成功。
5. 4096 输入界必须覆盖 system、工具 Schema、完整历史及供应商封装；字节数+余量只是保守估计，不是所有 tokenizer 的严格证明。超界暂停、保留 BUDGET_TRUNCATION，禁止静默截断历史。
6. 新 Schema 的原生工具适配/无网网络 Mock、未知收费中断与新审批绑定仍需在获批 Stage B 工程接入时验证。现有旧 transport 不会被悄悄换成 V0.3 Schema。

新增 SiliconFlow 供应商是用户提出的备选；本轮没有使用或写入其密钥，没有核验其账户权限、模型目录和费率，也没有自动切换供应商。若后续选用，应建立独立供应商价目和同一项目账本绑定，经审查后再执行。

当前结论：模型候选与公开估价已准备；**未批准、未调用**。建议审查上述明确字段和 `V03_PREREGISTRATION.json` 后决定四条 Gemini 或两条 Sonnet 的小批次。
