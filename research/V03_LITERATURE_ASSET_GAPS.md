# V0.3 最近工作与可执行资产核查

核查日期：2026-10-12。以下为针对机制问题的小范围核查，不声称系统综述或已证实的新颖性。论文结论属于 PAPER-CLAIM；代码树存在属于 VERIFIED；本地复现实验通过是另一个层次，本轮未复现外部训练/收费评测。仓库 commit、文件树和 README 快照位于 `provider/v03/assets/`，不将公开 README 中的运行示例视作执行授权。

## 每条研究线的最近邻与待验证差距

| 线 | 已核查的 3–5 篇最近邻 | 已有贡献与本项目边界 |
|---|---|---|
| P1 | [EVU / Seeing Isn't Believing (2026-04)](https://arxiv.org/abs/2604.17252)；[DoVer (v3 2026-01)](https://arxiv.org/abs/2512.06749)；[Reflexion (2023)](https://arxiv.org/abs/2303.11366)；[Uncertainty-Aware Clarification (2026-06)](https://arxiv.org/abs/2606.03135) | belief inertia、干预验证、语言反馈和主动澄清都已有工作。待检验的是匹配反馈下 H/E/O 的行动价值及证据不足，不能把主动诊断本身命名为新发现。先证明新工具真值可识别，再看强模型是否仍有错配。 |
| P2 | [EVU](https://arxiv.org/abs/2604.17252)；[Observable Belief Revision / α-Law (2026)](https://arxiv.org/abs/2603.19262)；[ReAct (2022/ICLR2023)](https://arxiv.org/abs/2210.03629)；[Action Boundary Blindness (ACL2026)](https://aclanthology.org/2026.acl-long.1711/) | 更新、交互反馈和行动边界均非新概念。需要区分相同事实的 user/tool 投递效果、事实接收与真实行动，以及不可靠证据下的顺从。可见概率/自述不是内部 belief 的直接测量；角色处理不能偷偷增加信息。 |
| P3 | [Calibration Is Not Control (2026-06)](https://arxiv.org/abs/2606.21399)；[Accurate Failure Prediction… / Intervention Paradox (2026-02)](https://arxiv.org/abs/2602.03338)；[DoVer](https://arxiv.org/abs/2512.06749)；[Reflexion](https://arxiv.org/abs/2303.11366) | 风险预测不等于干预收益、恢复与破坏的权衡已有明确研究。本项目只能验证有限状态中的可恢复性、具体动作反事实价值和强模型的剩余决策缺口，不能将该权衡重新包装。 |
| P4 | [Intrinsic Credit Assignment / ΔBelief-RL (2026-02)](https://arxiv.org/abs/2602.12342)；[InfoPO (v2 2026-06)](https://arxiv.org/abs/2603.00656)；[EAPO / Surprising Success, Repeated Failure (2026-09)](https://arxiv.org/abs/2609.33781)；[Uncertainty-Aware Clarification](https://arxiv.org/abs/2606.03135) | belief-change、信息增益、探索信用分配都已有方法；EAPO 当前核实版本是 reasoning token 信用分配，不等同于多步工具 VoI。需要先问简单前瞻能否解决互补动作。本轮四个有限世界的两步前瞻已等于精确最优，暂没有开发复杂方法的依据。 |
| P5 | [PlanFence / Fresh Memory, Stale Plans (v2 2026-09)](https://arxiv.org/abs/2609.03340)；[ReAct](https://arxiv.org/abs/2210.03629)；[EVU](https://arxiv.org/abs/2604.17252)；[Action Boundary Blindness](https://aclanthology.org/2026.acl-long.1711/) | 计划与依赖版本过期、刷新/重规划、行动范围均已有研究。新检查应落在有效工作保留、局部代际失效及非权威证据下的修复成本；PlanFence 的分布式 owner-head 协议不能直接视为本地 DAG 提示的同一个算法。 |

以上来源支持问题定位，不支持“前沿模型已存在本项目的目标缺口”这一尚未运行的结论。没有搬用论文百分比作为我们的结果。

## 资产核查分层

| 工作 | VERIFIED：实际访问的资产 | PAPER-CLAIM / README 声明 | UNKNOWN / 未执行 |
|---|---|---|---|
| EVU | [官方仓库](https://github.com/WangHanLinHenry/EVU)，commit `9c9781c953c63262d3ba1d36a11e7661177beabe`；完整未截断树，1253 个文件；环境/训练/评测代码，以及 `data/alfworld/new_final_alfworld_sft_data.json`、ScienceWorld index、VirtualHome 数据路径 | README 描述 SFT→RL→inference，明确大 checkpoints、生成轨迹与原工作区日志不随发布提供 | 本轮未下载/解析全部 SFT 数据；不能把它等同于全量原始评测轨迹。GitHub license 元数据为空，具体各组件许可须复核；未训练或复现效果。 |
| Calibration Is Not Control | [官方仓库](https://github.com/bennidict23/calibration-is-not-control)，commit `9e3825b7eea89ee9dc88f1ccd11f277f8e10beb3`；11 个文件；存在 `collect_alfworld_branches.py`、`evaluate_controllers.py`、`src/oversight_branching/`，MIT 元数据 | 论文/README 描述同 prefix 分叉、动作条件控制器，提供 ALFWorld 数据采集命令 | 树中未见完整采集分支轨迹包；未运行代码，不能声称论文 300-task heldout 数据已公开且可直接复现。 |
| ΔBelief-RL | [官方仓库](https://github.com/bethgelab/delta-belief-rl)，commit `f173b54a559b50db35a45daec0463f571d092981`；183 文件；环境、训练/评测脚本、split 文本及 Parquet 文件路径/大小，MIT 元数据 | README 描述 token 概率 belief 变化奖励和多任务评测；有名为 `ALL_TRAJECTORIES.parquet` 的单步 SFT 数据文件 | 文件存在不等于全量多轮评测日志开放；未加载 Parquet schema、未取得所有训练权重。GPU/CUDA 训练未执行；不能声称效果可在当前 Windows 环境直接复现。 |
| DoVer | [论文项目网站](https://mbjinx.github.io/DoVer_Web/) 的 Code 链接实际指向 [microsoft/ACV/misc/DoVer](https://github.com/microsoft/ACV/tree/main/misc/DoVer)，commit `994ac15db6fff8a5131bbf5a26e84e352e676796`；1853 个文件，大量为 vendored frameworks；有 intervention/replay 脚本、AG2 checkpoint system、`Who&When/Hand-Crafted/*.json` 任务资产 | README 说明 Magentic-One replay、分析和干预流程，需要 AutoGen/AGDebugger、Node、部分 Azure 配置；声明 logs 布局 | 不再将其误记为“代码仅待发布”。任务级代码路径已核实，但未执行并验证 checkpoint 恢复；未核实完整论文原始 logs/GAIA/AssistantBench 数据开放性及各组件许可。 |
| PlanFence | [论文 v2 全文](https://arxiv.org/html/2609.03340v2) 可访问，描述 exact input links、dependency frontier、owner-head validation、一次 replan 后 block | 文中报告 SBus validator、handoff/live workflows 和协议评测 | 本次在论文公开链接中未定位可核实的任务级代码/完整轨迹下载；标 UNKNOWN，不能推断不存在或已可复现。需作者资产链接再核验，不重建分布式系统。 |

仓库树是公开资产存在性的证据，不是运行成功证明。`index.json` 和 `dover_asset_audit.json` 保留 commit、path、size 与 tree_truncated 字段；没有从第三方摘要猜资源开放情况。

## 书目信息纠正与开放项

- “Intervention Paradox” 对应已核实 arXiv `2602.03338`，正式页面标题为 Accurate Failure Prediction in Agents Does Not Imply Effective Failure Prevention；不依赖匿名转载 PDF。
- V0.2 的 EAPO 缩写/会议信息不足以唯一识别论文。此次核实的是 `2609.33781`、2026-09-27、Entropic Advantage Policy Optimization；不能自动声称它就是此前所指的 ICML2026 工作。仍需负责人确认旧书目。
- EVU 的 README/论文关于 venue 的写法略不同；本轮只依赖可核实论文 ID 与代码，不将待核实 venue 当新颖性依据。Calibration 仓库的 NeurIPS 标签同样不替代独立会议录核验。
- Alpha-law 的 observable update 分析不等同于工具 Agent 的因果控制策略；Action Boundary 的替代有效路径误判风险与本项目不按参考序列评分直接相关。

## ALFWorld 接入审查

[官方仓库](https://github.com/alfworld/alfworld)，commit `aaba6870f86c5be6a08a491f32a50b906227bc3e`；README、`configs/base_config.yaml`、`alfred_tw_env.py` 和 setup 文件已保存。本轮没有混入 EVU 的修改版 ALFWorld 作为官方接口。

官方配置映射：train→`json_2.1.1/train`；eval_in_distribution→`valid_seen`；eval_out_of_distribution→`valid_unseen`。公开 OBS 应预先固定 split、完整 gamefile 清单、任务采样顺序/seed，保留所有尝试和官方 done/score；不能仅采集失败再估计自然失败率。CDW holdout 与 ALFWorld 官方 split 是不同概念。

官方 text 接口为 `get_environment('AlfredTWEnv')(config, train_eval=split).init_env(batch_size=1)`，`obs,info=env.reset()`，`env.step([command])`。只向 Agent 交付文本和允许的公开命令信息，专家轨迹/隐藏任务真值不进普通上下文。ALFWorld 的自然轨迹 checkpoint 需按官方 seed+gamefile+prefix 重放并核实环境状态，不直接套用 CDW JSON 快照能力。

安装核查实际结果：本机 Python3.12/Windows，`alfworld` 未安装。默认清华镜像 SSL 失败；改用官方 PyPI 的依赖 dry-run 可读取 `alfworld==0.4.2`、`textworld==1.7.0`，但 Jericho3.3.1 构建 requirements 时 WinError2，未完成安装、数据下载或真实 reset。没有修改项目运行依赖或冒充 Mock reset 成功。

已提供 `experiments/v03_alfworld_smoke.py`：无模型调用的真实 reset 探针，当前输出 `BLOCKED_DEPENDENCY`。下一步建议独立 Linux/WSL 环境固定 Python 与官方 commit，安装 text 依赖、`alfworld-download` 下载官方数据，再运行该探针核验 seed/gamefile。当前没有执行 OBS 自然轨迹，也不把此未完成项隐去。
