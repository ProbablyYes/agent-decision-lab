# Gate 1 模型核验与推荐（待确认）

核验日期：2026-10-12（Asia/Shanghai）。只访问公开资料与无鉴权 Models API；未打开 `.env`，未读取、打印或提交 API Key，未发起推理请求。实际新增 API 花费 ¥0。

## 接口与证据

使用先前项目配置的 OFox Base URL `https://api.ofox.ai/v1`。本轮用户明确确认使用此地址；未用其他进程的 Anthropic 配置替代实验配置。项目此前 model_id=unselected，没有已冻结的实验模型。

实际无鉴权 GET [Models API](https://api.ofox.ai/v1/models) 返回 **159** 个模型。完整原始 JSON 保存在 `research/provider/ofox-models-2026-10-12.json`，SHA-256 绑定在 `configs/gate1.json`。目录可以公开访问，不等于当前账号一定有推理权限。

API 响应里的 pricing 对象没有显式 currency 字段；[OFox 模型目录字段说明](https://ofox.ai/zh/docs/develop/models) 明确价格单位为 **USD/token**。以下以实际返回字符串乘 1,000,000 得到 USD/百万 Token，未根据名称猜价。账户结算币种、兑换系数及控制台对应价格仍待确认。

## 候选比较

| 实际 id | canonical_slug | 输入 USD/M | 输出 USD/M | 缓存读 USD/M | 缓存写 USD/M | context_length | 最大 completion |
|---|---|---:|---:|---:|---:|---:|---:|
| `qwen/qwen-flash` | `qwen-flash` | 0.022 | 0.22 | 0.0043 | 0.027 | 1,000,000 | 32,000 |
| `qwen/qwen-turbo` | `qwen-turbo` | 0.043 | 0.09 | 0.0086 | **未返回，未知** | 128,000 | 16,000 |
| `qwen/qwen3.5-flash` | `qwen3.5-flash-2026-02-23` | 0.10 | 0.40 | 0.01 | 0.125 | 1,000,000 | 64,000 |

三者实际 supported_parameters 均包含 `temperature, top_p, max_tokens, stop, tools, tool_choice, response_format`；qwen3.5-flash 另包含 `reasoning`。最大输出值取实际 top_provider.max_completion_tokens。

**推荐主基座：`qwen/qwen-flash`。** 理由：本实验为短输出、增长输入上下文的多轮工具交互；该模型声明支持 tools/tool_choice，价格低，且四项缓存费率完整。Turbo 输出更便宜，但输入更贵且缓存写价格缺失；qwen3.5-flash 可作后续候选，当前不增加模型实验因子。

“支持工具调用”有目录证据；“实际可靠”仍未验证，必须由获批后的第一条真实轨迹检查。qwen-flash 的 canonical_slug 没有日期，无法保证供应商背后的权重永不变化。冻结的是精确 API ID、参数、提示、schema 和此次目录快照；响应 model 不一致时停止，不自动换模型。

## 汇率及人民币换算

使用 [ECB 参考汇率](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.fi.html)，**汇率日期 2026-10-09**，本轮查询日期 2026-10-12：1 EUR=1.1206 USD，1 EUR=7.4992 CNY，因此交叉换算 **1 USD≈6.6921292165 CNY**。记录在 `research/provider/ecb-fx.json`。ECB XML 直连失败，使用可核实的官网网页数据。此为参考估算，不是 OFox 实际结算汇率；账户若使用固定兑换比例，应重新冻结该比例和来源。

| id | 输入 CNY/M | 输出 CNY/M | 缓存读 CNY/M | 缓存写 CNY/M |
|---|---:|---:|---:|---:|
| qwen/qwen-flash | 0.147227 | 1.472268 | 0.028776 | 0.180687 |
| qwen/qwen-turbo | 0.287762 | 0.602292 | 0.057552 | 未知 |
| qwen/qwen3.5-flash | 0.669213 | 2.676852 | 0.066921 | 0.836516 |

## 3 条与 5 条成本包络

每条最多 8 次 LLM 决策、12 次 primitive 动作；每次最多输入 8192 Token 的保守界、输出 512 Token。超出输入界就暂停，不静默截断。模型实际输入界以序列化请求 UTF-8 字节数+1024 检查；首次调用还须验证供应商计数/隐藏开销，不能把该经验界当作所有 tokenizer 的数学保证。

无缓存参考额 = `条数×8×(8192×输入USD/M + 512×输出USD/M)/1e6×汇率`。

保守预留 = `条数×8×[8192×(输入价+max(输入价,缓存读价,缓存写价)) + 512×输出价]/1e6×汇率×2`，每请求向上取整到微元。这样预留了缓存写入可能附加收费及 2 倍缓冲，不依赖缓存折扣；未知的收费项仍必须核验，公式不替代账户价目。

| id | 3条无缓存参考 CNY | 5条无缓存参考 CNY | 3条保守预留 CNY | 5条保守预留 CNY |
|---|---:|---:|---:|---:|
| qwen/qwen-flash | 0.047037 | 0.078395 | **0.165144** | **0.275240** |
| qwen/qwen-turbo | 0.063977 | 0.106629 | **无法给完整上界** | **无法给完整上界** |
| qwen/qwen3.5-flash | 0.164466 | 0.274110 | 0.657864 | 1.096440 |

在公开 Token 价目、参考汇率和上列费用假设成立时，推荐模型 3/5 条包络均低于首批 ¥8、Gate 1 ¥10。**尚未核实账户结算和缓存写语义，因此现在不能承诺实际账单上界，也不能开始收费实验。** 不启用 web search、远程工具、图像或额外供应商回退；CDW 工具是本地操作。

## 拟冻结设置

配置：`configs/gate1.json`。provider=ofox；model_id=`qwen/qwen-flash`；model_revision=`qwen-flash`（目录标识，非不可变权重版本）；temperature=0；max_tokens=512；Prompt=`v0.2-native-tools-1`；tools=`cdw_action` JSON Schema；world seed=0；单线程；自动重试=0；单条最多 8 次决策/12 次 primitive。Prompt/Schema SHA-256 和完整代码/config 指纹均入审批绑定。

精确模型为**推荐草案**，`model_confirmed=false`。等待研究负责人确认最终模型、账户币种/价目/汇率、缓存统计/计价语义，并批准**第一条**真实轨迹；不会因完成准备而自动开始。
