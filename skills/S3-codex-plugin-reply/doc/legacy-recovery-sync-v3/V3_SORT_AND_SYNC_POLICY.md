---
tags:
  - social-agency
  - skills
  - reply-recovery
  - v3
date: 2026-03-26
status: draft
---

# V3 Sort And Sync Policy

## 目标

定义 V3 主表的排序方式，以及持续抓取后如何稳定定位 person、thread 与增量更新。

## 表格口径

- `match / bootstrap` 只参考：
  - `Agency/list-master/【S2 Cold】Corestar-1000-KOL.csv`
  - `Agency/list-master/【S2 Cold】Rockbase-580-KOL.csv`
- `writeback` 只写入：
  - `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`

## Sync 锚点

| 字段名 | 用途 |
| --- | --- |
| `账号ID` | Person 层主键。最终更新落点。 |
| `Reply_Contact_Email` | 联系人邮箱匹配线索。 |
| `Reply_Thread_ID` | 当前活跃 Gmail thread 主键。 |
| `Latest_Inbound_Message_ID` | 最新 inbound message 去重锚点。 |
| `Latest_Inbound_InReplyTo` | 当前 inbound 回复对象。 |
| `Outbound_Message_IDs` | 我方各波次 outbound message id 映射。 |
| `Reply_Last_At` | 当前行最后一次有效回复时间。 |
| `Reply_Count` | 当前 thread 内有效回复轮次数量，用于排序。 |

## 主表精简口径

V3 主表的 Part 3 只保留核心系统字段：

- `Sort_Bucket`
- `Reply_Count`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`
- `Reply_Last_Subject`
- `Reply_Last_At`
- `Outbound_Message_IDs`
- `Latest_Inbound_Message_ID`
- `Latest_Inbound_InReplyTo`
- `Reply_Stage`
- `Reply_Stream`
- `Pipeline_Stage`
- `Capture_Run_ID`
- `Capture_At`
- `Reply_Body_File`

以下历史字段不再保留在主表，而是下沉到 workbench 快照：

- `Reply_Status`
- `Reply_Needs_Manual_Review`
- `Manual_Review_Reason`
- `Manual_Review_Focus`
- `Owner`
- `Priority`
- `Final_Outcome`
- `Ops_Notes`
- `Reply_Analysis`

## 持续抓取更新顺序

1. 优先用 `Reply_Thread_ID` 命中已有行。
2. 若 thread 未命中，再尝试 `Reply_Contact_Email`。
3. 若仍未命中，再回退 source 表 bootstrap 到 `账号ID`。
4. 命中后用 `Latest_Inbound_Message_ID` 去重。
5. 用 `Latest_Inbound_InReplyTo + Outbound_Message_IDs` 判断波次归属。

## MailN 扩展原则

- 主视图允许继续增加 `mail4_reply_block`、`mail5_reply_block`、`mail6_reply_block`
- 底层系统字段不需要无限复制
- 波次归属本质依赖 `Outbound_Message_IDs` 与 `Latest_Inbound_InReplyTo`

## 推荐排序字段

V3 主表推荐按以下顺序排序：

1. 正常行优先，`备注` 不为空且无 mail 的问题行沉底
2. `section` 行固定整表最后
3. `Reply_Count` 升序
4. `Reply_Last_At` 降序
5. `频道/作者名称`

## Sort_Bucket 规则

建议脚本先生成一个排序辅助列：

| Sort_Bucket | 含义 |
| --- | --- |
| `1_replied_clear_price` | 已回复，且当前价格明确 |
| `2_replied_need_review` | 已回复，但价格或平台仍需人工判断 |
| `3_waiting` | 已发出但仍在等待回复 |
| `4_closed` | 已完成或停止跟进 |

## 排序目标

- 正常、有 mail 内容的线程先排前面
- 在 replied 主线里，先处理回复轮次少的线程
- 同等复杂度下，优先最新回复
- `备注` 已标记且无 mail 的问题行沉底
- `section` 行永远排在整表最后

## Reply_Count 规则

| 字段名 | 规则 |
| --- | --- |
| `Reply_Count` | 统计当前 thread 已进入主线的有效回复轮次，默认按从少到多排序。 |

说明：

- 默认不采用 `Reply_Count` 从多到少。
- 原因：短线程更容易快速读清、价格判断更稳、token 成本更低。
- 只有在专项清理复杂历史线程时，才临时切换为从多到少。
