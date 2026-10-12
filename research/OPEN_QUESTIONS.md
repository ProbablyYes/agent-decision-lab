# Open questions and blocked experiment parts

1. P2 原生 Tool 载体需要合法 tool_call_id 和匹配历史。当前离线 feedback helper 的 Tool 消息不能直接发送到供应商；真实角色实验暂停。最低成本检查：同 checkpoint、同事实文本、同历史长度/动作成本，只改变消息角色；可证伪预测：匹配后角色差异消失。批准前需确定供应商消息 schema。
2. P4 regret 需要预定义 reward/cost 权重和有限时域 Oracle；协议未给定数值权重。暂停计算 regret 和最终 scalar return，保留成功、动作次数与准备动作选择。最低成本对照：同 horizon 下即时进展 vs 2-step lookahead vs 穷举上界；预测：校准后诊断提高成功，若无差距则该实例没有机会空间。
3. 当前 plan DAG 是最小 prepare→apply→verify，保留 prepare、使 apply/verify 过期；不足以代表一般复杂 DAG。最低成本检查：从已 prepare checkpoint 对比保留准备与重做准备，若成本无差异或成功已饱和，不扩展算法。正式 P5 需记录旧计划节点及前提，而非根据动作文本推断计划采纳。
4. U 为确定性证据不足，隐藏目标仍可被 scripted policy 猜中；Mock 已知脚本不是可部署推断。自然 U 的可靠性分布与科学任务分层待研究者审查，不能报告自然频率。
5. P3 需同时选原本成功和失败 checkpoint 并配对分叉；当前只有回放和配对评分单测，没有真实恢复率或误伤率数据。先收自然完整轨迹再选择，预注册筛选规则和全部分母。
6. API 供应商模型名/精确版本、计价资料、币种、汇率、usage/cached token 及失败收费格式均未核验；真实 transport、跨进程全局账本和审批记录未接通，Gate 1 仍需先解决这些阻断。不得以估算表当作真实报价。
