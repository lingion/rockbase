# Scripts

这里放 `S3-codex-plugin-reply` 的正式脚本。

当前还没有把 plugin-first workflow 完整脚本化，所以先保留目录与职责边界。

当前明确边界：

- 脚本负责 `capture / packaging / writeback / audit`
- LLM 负责 `relevance / ownership / need_reply / WF routing / draft judgment`

硬规则：

- 不再把“重判断”优先沉淀成旧式前置筛选脚本
- 不再允许脚本用 preview 先把真实候选池缩窄
- 后续脚本优先做证据层和执行层，而不是判断主脑

后续优先沉淀的脚本应包括：

1. `build_plugin_reply_queue.py`
   - 从 inbox / unresolved threads 构建 raw dispatcher 队列
   - 只做 light routing 字段准备，不做最终业务判断
2. `prepare_plugin_reply_jobs.py`
   - 把待起草对象转成 manifest
3. `write_plugin_reply_drafts.py`
   - 调用 Gmail OAuth 链路写 reply drafts
4. `sync_plugin_reply_to_master.py`
   - 把 ownership、need-reply、阶段、价格、附件状态、下一步动作写回 S3 master
5. `export_plugin_reply_evidence_pack.py`
   - 输出完整 thread evidence package，供 LLM judgment 使用

不再优先把下面能力做成脚本主脑：

- `classify_plugin_reply_candidates.py` 这种最终分类器
- `auto route into WF-1 / WF-2` 这种最终业务路由器

这些默认由 LLM 做。

当前推荐最小队列产物：

- `queue_draft_ready.csv`
- `queue_missed_reply.csv`
- `queue_ocr_first.csv`
- `queue_contact_update.csv`
- `queue_manual_review.csv`

在这些脚本正式落地前，当前逻辑仍然主要由：

- Gmail 插件
- 本地已有 reply draft 脚本
- 结构化 review / manifest / audit 文件

共同完成。
