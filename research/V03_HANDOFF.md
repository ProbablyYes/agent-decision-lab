# V0.3 Stage A HANDOFF

Stage A 的五线最小任务与离线验证已完成；本轮 **0 次收费模型请求、新增模型费用¥0**。暂停在模型、设计与费用审查处，尚未执行 Stage B。附件已完整阅读，V0.2 背景、研究地图和 Gate 1/2 记录作为约束，文件身份见 `V03_SOURCE_PROVENANCE.json`。

## 实际完成

- 新增独立 `src/adfl/v03/`：四类归因/证据状态、消息通道投递、三类恢复状态、belief-state 精确有限 POMDP、三个依赖更新家族；保持原 CDW/PilotWorld 语义。
- 严格动作参数、真实前置条件/效果、代际依赖有效性、可恢复 JSON checkpoint、隐藏真值隔离和多个合法计划评分。
- 144 个 manifest 条目，design/dev 72 个 World 状态恢复/分叉检查、66 条特权 Mock 完整轨迹；P4 精确模型和实际实现恢复检查。holdout 仅冻结，没有 rollout/按结果调任务。
- 原 103 项测试和新增 35 项共 **138 passed**；最终结果 `results/v03/stageA/pytest.xml`。开发中 P4 tuple/list 恢复失败保留在 initial XML，修复后通过，未包装成科研进展。
- 262 个旧结果文件哈希一致。只读访问原 SQLite，56 笔 billed=null 请求全部保留，预留 **¥0.981665**；全部账本表逻辑哈希前后一致。没有新审批、cap 变更、结算或预算清零。
- 公开无鉴权 OFox 目录、两个家族近期模型、归一化 Token/cache 价格与2/6/12条费用；外部论文/资产官方来源与 commit 核查，保存 VERIFIED/PAPER-CLAIM/UNKNOWN 区分。
- 独占创建的预注册草案和 SHA256；离线核验命令没有批准/执行模型的能力。

## 最重要的校准发现

P1 H/E 同观察而需要不同修复，O 无需修改配置，U 仍需进一步证据。U 是认识上的信息不足，不能当作互斥物理故障。任务目前可能仍对强模型太容易；尚无强模型结果。

P3 保留自然成功状态，也有程序化不可恢复状态；干预的正、负净价值均可计算。Mock 中 warning 后选择探查是脚本假设，不能推出真实 warning 有害。

P4 四个世界的两步前瞻加终止价值估计均等于精确最优。这是本轮的反预期校准结果：现有简单方法已解决这批任务，不自动发展复杂算法或增加依赖长度来制造差距。

P5 非线性 DAG 的分支/祖先变化确实使部分已完成节点失效，假警报下重做会破坏可复用工作。三种 Mock 校准策略全部成功，成功指标饱和；A/B/C 的最短成本分别4/6/3。真实模型自然规划可能也最优，首批只验证这一点，不预设会失败。Oracle A/B 的节点列表可由普通信息推导，不声称特权信息优势；C 在 audit 前才有隐藏真值优势。

## 交付文件

| 文件 | 用途 |
|---|---|
| `V03_SCIENTIFIC_PROTOCOL.md` | 五线科学假设、任务真值/因子、指标、对照、公平性与反证 |
| `V03_LITERATURE_ASSET_GAPS.md` | 每线3–5篇最近邻，5项重点资源核查及 ALFWorld 阻断 |
| `V03_FRONTIER_MODEL_OPTIONS.md` | 实际模型目录、价格、费用包络与结算待核实项 |
| `V03_TASK_MANIFEST.jsonl` | 家族/split/checkpoint/hash/权限/条件 |
| `V03_PREREGISTRATION.json` + `.sha256` | 待审查的冻结配置，不是收费授权 |
| `../results/v03/stageA/README.md` | 测试与完整校准证据索引 |
| `OPEN_QUESTIONS.md` | 新猜想、反证及协议变更建议，保留旧问题 |

## 可运行命令（PowerShell，仓库根目录）

```powershell
$env:PYTHONPATH = 'src'
python -m pytest -q
python -m adfl.v03.stage_a
python -m adfl.v03.review
python experiments/v03_alfworld_smoke.py --config research/provider/v03/assets/alfworld__alfworld__configs__base_config.yaml --split eval_out_of_distribution --seed 0
```

前两项均离线。`stage_a` 可重建相同任务，不修改旧结果或账本；冻结核验会检查 manifest、源码、Prompt/Schema 和具名 checkpoint。当前 `review` 必须显示 `paid_execution_authorized=false` 及阻断项，不能将其输出理解为允许收费。

本轮另执行 `python experiments/v03_public_assets.py`、`python experiments/v03_resource_checks.py` 查询公开资源；这些命令含公开 GET，没有 key/推理调用。初次冻结用 `python -m adfl.v03.review --freeze`，文件存在时拒绝覆盖。后续更改需新版本审批，不能删除原注册后静默重建。

ALFWorld 依赖 dry-run：

```powershell
python -m pip install --dry-run --ignore-installed --disable-pip-version-check --index-url https://pypi.org/simple --retries 0 --report .state/v03-alfworld-install.json alfworld
```

实际 exit1：Jericho3.3.1 构建 requirements 时 WinError2；失败没有生成完整安装 report。当前 smoke 输出 BLOCKED_DEPENDENCY。未完成官方 text reset 或数据下载，建议独立 Linux/WSL 环境继续；本轮没有 ALFWorld OBS 分母。

## 下一阶段的具体待批方案

建议主模型 **`google/gemini-3.8-flash`**，不同家族候选 **`anthropic/claude-sonnet-5.5`**。OFox 旧 Gemini3.5/3.7 未弃用标记与 Google 自动路由文档冲突，已避免推荐这些旧 ID。型号存在和原厂 Agent 定位可核实，但目录不是账户权限实测，也不是不可变权重证明。

冻结四个 dev seed=10 实验：P1 H/no-intervention、P1 E/no-intervention；P5 B/选择性提示、同 B/belief-only。P1 两个 checkpoint 的可见上下文一致，P5 两组为同 checkpoint。temperature=0；max_tokens=512；每条8决策/12 primitive；输入上界4096；新 Prompt/Schema 哈希见注册。先第一条并人工审查，其他轨迹不会自动执行。第二家族及 P2/P3/P4 真实实验均不在此首批清单。

Gemini 四条无缓存参考约¥2.14，保守预留 **¥6.907584**，建议独立批次cap¥8、单条cap¥2；加旧预留累计¥7.889249，继承 Gate2¥40、项目¥100/警戒¥90。Sonnet 相同四条保守约¥12.72，超出本批建议；若选 Sonnet，建议先仅P1两条，预留¥6.359344，不自动加额。

## 尚未完成/收费阻断

1. **账户实际价目、缓存/TTL/存储收费、reasoning 输出计数、实际结算 FX、逐请求账单仍待核验。** 历史余额为USD，只是保存时证据，不是新查询的当前余额。所有未知费用保留占额。
2. OFox 对 Gemini low thinking 和 Sonnet between_tools 的映射尚不清楚。512输出是否足够强模型完成思考与原生工具动作亦待审查；未看到结果前可以修订预算和新版本注册，不能结果后调整制造失败。
3. V0.3 新 Schema 尚未绑定收费 transport/审批 runner；没有提供虚构的真实运行命令。旧 transport/账本继续保留，获批 Stage B 工程接入须先通过 Mock 网络和费用中断验证，并绑定最终 code commit 与新指纹。本轮注册记录基线 commit 与全部相关文件哈希，不冒称未提交改动已有最终 commit。
4. P5 处理提示长度不同仍可能解释行为差异。相同预算上限不等于相同实际 Token 消耗；若行为不同，需要另审长度对照。Mock 不证明前沿模型存在缺口。
5. ALFWorld 真实 reset 阻断；外部论文训练/全部原始轨迹没有复现，资源状态详见资产报告。

新增 SiliconFlow 只是供应商备选，本轮没有使用、保存新密钥或切换 provider。等待研究负责人审查模型和预注册后再明确批准具名小批次；Stage A 完成不触发收费执行。
