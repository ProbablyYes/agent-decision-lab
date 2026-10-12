# Codex：从这里开始（V0.2）

你是 Agent Decision Failure Lab 的工程实现者，科研问题与实验对照已由研究负责人事先确立。**先完整阅读 `research/RESEARCH_BRIEF_V0.2.md`**，包括五条线的起源、实验机制、对照、成本和停止条件。`research/EXPERIMENT_PROTOCOL_V0.1.md` 是历史版本，若不同以 V0.2 为准，并记录版本差异。

第一轮目标不是证明算法有效，而是以真实 LLM Agent 在可重置世界里确认失效机制和干预作用，同时在 ALFWorld 上确认自然出现率；保持 P1–P5 独立。

现在执行 M0–M3 的**最小可运行版本**：项目骨架、最小 CDW、Mock 校准、冻结 API Agent 接口、日志与预算安全阀。不要调用真实 API；不要一次性实现大而全的五套算法，不要训练 LLM，也不要主动进入 ALFWorld 高成本运行。

Gate 0 通过后，**立即暂停交付**：HANDOFF.md + 目录树 + pytest 结果 + 3–5 条真实 API 运行的拟定方案与保守成本测算（实际花费应为 ¥0）。研究负责人明确批准 Gate 1 后，才开始真实 LLM API，先用 3–5 条端到端真实轨迹检查行为，再调整后续 Pilot，而不是一直用 Mock。

如果觉得实验逻辑有漏洞，写入 `research/OPEN_QUESTIONS.md` 并停止相关部分，不要静默“修正科学问题”。禁止泄漏隐藏 GT、混淆自然/合成/Oracle、在测试集调参。所有变更写入 DECISION_LOG.md。