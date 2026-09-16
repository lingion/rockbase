# S3 ReplyOps（入口）

这是 S3 回复运营的唯一直接入口：处理报价恢复、谈判跟进、回复草稿与状态同步。`S3-ag-reply-draft-ops` 和 `S3-ag-reply-recovery-sync-v3` 是内部能力层，不建议单独作为起点。

需要 Gmail 时先用自己的 OAuth token；回写任何主表前必须 dry-run 并确认字段映射。

## V2 安装与离线验收

- 离线队列生成只需 Python 3.11+。
- Gmail 能力：`python -m pip install -e '.[gmail]'`
- 模型生成：`python -m pip install -e '.[llm]'`
- 代表性离线验收：`python -m pytest -q tests/test_s3_queue_smoke.py`

该验收只用虚构 CSV 在临时目录生成队列，不访问 Gmail、Feishu、真实邮箱或生产主表。
