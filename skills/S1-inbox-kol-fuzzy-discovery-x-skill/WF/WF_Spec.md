---
description: "[Legacy Redirect] WF_Spec 已降级 | 正式入口请改用 WF_Int。"
---

# WF_Spec

`WF_Spec` 已不再作为本 skill 的正式启动入口。

从现在开始：

- `WF_Int.md` 是正式入口
- `QUERY_LIBRARY.md` 是所有 query 方法论与关键词矩阵的主文档

新的正式流程是：

```text
自然语言需求
-> WF_Int 提问与澄清
-> 更新 QUERY_LIBRARY
-> 生成当天 spec
-> 生成 Implementation Plan / Todo List
-> 用户确认
-> 执行
```

## 当前职责分工

### `WF_Int.md`

负责：

- 启动式 intake workflow
- 向用户提问并补齐关键参数
- 驱动 library -> spec -> plan -> todo -> 执行

### `QUERY_LIBRARY.md`

负责：

- query 方法论
- AI 核心词 / 扩展层逻辑
- topic query matrix
- 历史 query 档案

### `specs/*.json`

负责：

- 承接当日已确认的结构化执行参数
- 供代码层 `task_spec.py` / pipeline 执行

## 兼容说明

如需查看旧的 spec 思路，请直接参考：

- `WF_Int.md`
- `specs/_template.x_kol_task.json`
- `src/x_kol_discovery/task_spec.py`

正式新任务不应再从 `WF_Spec` 直接起步。

