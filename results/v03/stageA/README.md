# Stage A 离线校准结果

日期 2026-10-12；所有 rollout 为 SIM / Scripted Mock / 程序化 Oracle，真实 LLM 样本数为 **0**，新增收费模型费用 **¥0**。

最终全套 pytest：**138 passed**，其中原有 103 项仍通过，新增 35 项参数化测试。`pytest.xml` 为最终结果。`pytest-initial.xml` 保留开发中发现的 4 个 P4 JSON 恢复失败：tuple 观察序列化成 list 后历史不相等。修复为 JSON 原生 observation 后复测通过；这是工程修复，不是算法提升。

`V03_TASK_MANIFEST.jsonl` 共 144 条 seed/机制记录。12 个 World 家族的 design/dev 共 72 个状态通过所有单步分叉和恢复检查；其中 66 个存在成功路径，6 个 P3 irrecoverable 状态在预算内穷举不可达。另对 P4 的 4 个公共概率模型做精确 DP、10 个实际隐藏实现的离线重放测试。holdout 只冻结，不运行 rollout 或用于选择任务。

## 实际保存的证据

| 文件 | 内容与权限 |
|---|---|
| `truth_restore_checks.json` | 每个非 holdout World checkpoint 的恢复、所有单步分叉一致性、穷举最短成功路径；GT 审查用途 |
| `mock_oracle_rollouts.json` | 66 条特权规划器产生的 Scripted Mock 完整动作/反馈/评分；不是部署 Agent 能力 |
| `p2_native_histories.json` | 两 checkpoint × 两可靠性亚组 × C0/C1/C2；原始工具结果、投递事实、合法 call id、相同预算及 C1/C2 长度验证 |
| `p3_mock_pairs.json` | 9 个预选条件的固定响应脚本，保留成功与失败；warning 后的 probe 是脚本设定，不能据此说 warning 会使 LLM 失败 |
| `p3_exact_action_values.json` | 逐 first-action 的特权最佳续接、可达性与净价值 |
| `p4_exact.json` | 显式先验、条件观测概率、四基线的期望回报/成功/动作数/regret/DP 复杂度 |
| `p5_mock_contrasts.json` | A/B/C 的三种校准脚本完整轨迹、有效工作保留和成本；不是三个真实模型条件组 |
| `evaluator_only/checkpoints/` | 完整隐藏状态，严禁作为普通 Agent 上下文 |
| `visible/` | World 的非特权初始输入；文件名含研究标签，因此仅传 JSON 内容，不能把路径给模型 |
| `preservation_audit.json` | 262 个旧结果文件 SHA256 不变、账本全部表逻辑哈希不变，56 笔未知账单仍预留¥0.981665 |
| `cost_estimates.json` | 原价目及整数微元保守估算；非实际账单 |
| `alfworld_reset_probe.json` | BLOCKED_DEPENDENCY，真实 reset 未核实 |
| `tool_schema.json` / `prompt.json` | 独立 V0.3 动作契约与 Prompt，不覆盖 Gate 1 Schema |

## 任务区分能力与限制

P1：H/E 两对相同初始可见反馈需要不同修复；O 可用 audit+verify 而不修改配置；U 两个支持世界同观察、不同正确行动。测试验证证据可分离，不证明 LLM 会选择有价值诊断。seed 置换不是独立任务机制。

P3：recoverable 脚本 continue 失败、repair 成功；fragile-success 自然 wait 成功、rollback 后失败；irrecoverable 三条件均失败且已穷举证明。以上只是已指定脚本的校准，不是条件的平均处理效应。

P4：A/B 两步前瞻=精确最优0.85，C/D=0.90；两步 regret 全为0。IG 在 A/B 为0.45，在 C/D 已最优。没有制造更长链来维持复杂方法优势。

| P5 家族 | 旧尾部首次尝试后特权恢复：成本/成功 | 全部重做：成本/成功 | 精确选择修复：成本/成功 |
|---|---|---|---|
| A 分支变化 | 5 / true | 7 / true | 4 / true |
| B 共享祖先变化 | 7 / true | 7 / true | 6 / true |
| C 假警报（seed0） | 3 / true | 7 / true | 3 / true |

Mock 三策略全部成功，成功指标饱和；目前可区分的是成本和工作保留。真实 LLM 可能自然已经采取最短合法路径，此时必须保留负结果，不能提高难度或改评分掩盖。工具阻止无效依赖执行，因此 obsolete **attempts** 与 actual **execution** 分开，后者为0。B 的最短成功需要6动作，在拟8决策限制内仍有余量。

源码只提供离线生成/核验命令；不存在自动开始 V0.3 收费批次的入口。
