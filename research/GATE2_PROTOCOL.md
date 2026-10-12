# Gate 2A 最小配对实验预登记 v1

范围：仅 P1 的三个分支、P5 的四个分支，共两个 checkpoint、七条真实轨迹。P2/P3/P4 本轮仅离线仪器校准，不执行收费扩展。保持 Gate 1 CDW 和结果不变；新增 PilotWorld 使用单独任务 ID/version，不能与 Gate 1 成功率作算法提升比较。

所有分支 seed=0、qwen/qwen-flash、temperature=0、max_tokens=512；8 次决策、至多 12 次 primitive（checkpoint 已消耗动作计入）。共享工具 Schema 不变，任务内动作含义在所有同线分支的相同 system 说明中明确。一次请求一个原生工具调用，可含合法 combo；无自动重试、模型切换或补样。顺序由 Random(0) 在发请求前固定。唯一主结果仍为最终正确变更并验证；辅助指标不替代主结果。

## P1

Checkpoint：ambiguous:H 的首次 apply_change(A) 后，剩余 11 次 primitive。失败反馈与 ambiguous:E 完全相同；错误配置与命令未送达不能凭初始反馈区分。diagnose(A) 检查命令回执，diagnose(B) 检查 A 的兼容性；普通 inspect 仅报告服务状态。H/E 真值只在隐藏环境与 Oracle 分支中提供。Mock 覆盖两种真值，真实首批仅 H，不能估计总体 H/E 区分能力。

三个条件：无附加消息；固定普通反思（无新事实、无额外 LLM 调用）；Oracle 归因（直接提供隐藏错误类型，不直接执行恢复）。Oracle 为特权信息上界，不能声称与普通反思匹配信息量。提示长度和附加消息数量不同，记录实际 Token，不把差异归因于纯粹推理能力。显式 H/E 归因未按 Schema 收集时 attribution_correct 保持未测，不从目标选择或任务成功反推。

## P5

Checkpoint：历史 DAG 为 snapshot、credentials → stage:A → apply:A → smoke:A → verify:A。前三步已完成，新外部证据将要求改为 B；snapshot 与 credentials 有效，四个目标相关旧节点失效。checkpoint 剩余 9 次 primitive。

动作映射：prepare 生成共享 snapshot，calibrate 验证共享 credentials，inspect(A/B) 暂存并检查目标配置，apply_change(A/B) 部署，diagnose(A/B) 执行并登记 smoke test，verify 需当前配置已应用且 smoke test 已通过。inspect 同时获取信息并推进任务，工具作用不强制二分。P5 的这些含义不同于 Gate 1，属版本化任务变化，不是 Agent 算法改善。

四个条件共享同一新事实：Belief-only 只提供事实；Full Replan 要求从目标重新构建计划但不强迫抹除有效状态；Selective Repair 要求保留有效部分并修复受影响步骤；Oracle Dependency 另给精确失效/有效节点清单。所有要求都是提示干预，不实施自动计划修复。不能为制造差异强迫 Full Replan 重做已经有效的工作。

成功、primitive 成本、无效 apply 比例、共享已完成节点的实际重做/复用、目标 A 失效步骤执行数分别记录。valid_node_retention 在本最小 DAG 中按两个已完成有效共享节点未被重做的比例操作化，为可观察的执行复用代理，不是模型内部计划保留的直接观测。repair_cost 为 checkpoint 后 primitive 数；checkpoint 历史不再次计费，但前缀消耗与各分支剩余预算相同。保留完整自述计划以供人工审查。

## P2/P3/P4 的离线增强

P2：同正确事实在 User 或 Tool 中出现，采用两臂相同的原生调用 scaffold、匹配 tool_call_id 和相同内容多重集；中性占位消息与事实交换载体。标记为构造历史，不声称是自然工具发现。正式角色实验尚未收费运行。

P3：H/E 同 checkpoint 分别校准自然继续、固定反思、一种实际诊断干预。E 保留自然成功，H 保留自然失败。诊断多消耗一次动作并显露信息，成本与观察差异如实记录，不能把它宣称为纯提示效应。Mock 的策略由评估者预选，仅验证可恢复性与可能误伤，不能测真实干预收益。

P4：complementary 任务须先校准，两个探查各给一位信息，异或关系决定 A/B；单个探查不独立识别目标。dependency 的 inspect 是信息获取和 staging 的双作用动作。未定义 reward/regret 权重，因此不制造 scalar return 或 regret。

## 公平性、预算与停止

同线各条件从完全相同的环境快照、RNG、可见前缀、剩余预算和旧计划恢复；新增干预文本是唯一条件差异。Mock 检查恢复后哈希、脚本成功/失败、节点复用、原生工具回传与中断后不重发。脚本有区别不证明真实模型响应有区别，真实轨迹须另查。

主账本沿用 .state/gate1.sqlite3，增量添加批次表，保留所有 Gate 1 预留。Gate 2 累计 ¥40（包含 Gate 1）、项目总额 ¥100/运行线 ¥90，首批共享 ¥5、每分支 ¥1。新的输入预留上界为 32768 Token，以覆盖更长的 DAG 说明和历史；实际发送的字节上界也检查，未提高输出或决策上限。公开费率与账户账单分开。余额接口只能核对账户累计消费与币种，不能自动释放旧的逐请求未知账单；观察到异常扣款、未知主要 usage、新接口错误时停止后续分支。

七条全部容易成功则报告任务在本模型/预算下成功率饱和；即便工具成本不同，也不能声称提高成功率。不得在看到结果后增加难度、改评分或运行更多样本。本轮结束暂停，新增猜想写入 OPEN_QUESTIONS.md，等待研究决策。
