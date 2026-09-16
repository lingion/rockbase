# Workbench Template

## 目的

本文件定义 `ag-gmail-reply-ops` 项目在 workbench 中的推荐目录结构。

原则：

- skill 内放标准方法
- workbench 内放当前项目执行文件
- 所有 batch 使用稳定命名

## 状态说明

旧结构：

```text
workbench/{date}/{project-slug}/
```

适合一次性项目批次，但不再推荐作为长期 reply recovery 主入口。

升级后默认主入口：

```text
workbench/reply-recovery-hub/
```

## 推荐目录

```text
workbench/reply-recovery-hub/
├── 00-state/
├── 01-runs/
├── 02-review-ready/
├── 03-master-sync/
├── 04-bodies/
├── 05-attachments/
└── 06-ledgers/
```

## `00-state/`

只放长期状态：

- checkpoint
- capture config

## `01-runs/`

只放每次运行的 run 目录，例如：

- `2026-03-19_run-001/`
- `2026-03-19_run-002/`

run 内可继续放：

- thread ids
- full fetch csv
- recent preview
- run audit
- run summary

## `02-review-ready/`

只放给用户看、给用户决策的文件，例如：

- 正式审核表
- 精修报价表
- reply-ready table

## `03-master-sync/`

只放 master 写入相关文件：

- preview
- audit
- summary

## `04-bodies/`

长期放正文文件，按 `message_id.txt` 存。

## `05-attachments/`

按层分：

- `raw/`
- `text/`
- `ocr/`

## `06-ledgers/`

长期放：

- `reply_message_ledger.csv`
- `reply_thread_ledger.csv`
- `attachment_ledger.csv`

## 命名建议

推荐：

- `{date}_run-001_full_messages.csv`
- `{date}_run-001_review_table.csv`
- `{date}_run-001_attachment_extraction_report.csv`

避免：

- `final.csv`
- `new.csv`
- `最新版.csv`
