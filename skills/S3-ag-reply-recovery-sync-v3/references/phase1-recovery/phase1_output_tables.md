# Phase 1 Output Tables

## 目标

本文件定义 Phase 1 结束后几张核心表应该长什么样，以及哪些字段允许回写 master。

完整字段释义请同时查看：

- `../shared/replied_master_field_dictionary.md`

## 1. 最小主表结构

Phase 1 的目标不是堆字段，而是保留一张能判断“这是谁、回到哪一封、这次抓取是哪次、下一步做什么”的最小表。

建议最小字段只保留这些：

- `账号ID`
- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Outbound_Message_IDs`
- `Latest_Inbound_Message_ID`
- `Latest_Inbound_InReplyTo`
- `Latest_Body_File`
- `Capture_Run_ID`
- `Capture_At`
- `Reply_Stream`
- `Reply_Stage`
- `Reply_Analysis`

## 2. 这几个合并字段怎么写

### `Outbound_Message_IDs`

把已发送的 outbound message id 压成一列，统一格式：

```text
mail1:<id>|mail2:<id>|mail3:<id>
```

这样后续只要看 `Latest_Inbound_InReplyTo`，就能判断对方回的是哪一波。

### `Reply_Stage`

只保留一个阶段字段，不再拆成多个状态列。

建议值：

- `mail1_waiting_reply`
- `mail1_replied_waiting_mail2`
- `mail2_waiting_reply`
- `mail2_replied`
- `closed`
- `manual_review`

### `Reply_Analysis`

把原来分散的分析列合并成一列，用短格式保存：

```text
category=<...> | summary=<...> | next=<...>
```

示例：

```text
category=quoted | summary=shared revised rate | next=prepare_mail2
```

## 3. 价格相关字段怎么写

Phase 1 当前有效价格层保留两列，另加一列人工摘要位：

- `Reply_Main_Dedicated_Rate`
- `Reply_Comprehensive_Pricing`
- `Reply_Pricing_Excerpt`
- 以及波次历史层：
  - `Mail1_Pricing_Excerpt`
  - `Mail2_Pricing_Excerpt`
  - `Mail3_Pricing_Excerpt`

规则：

- `Reply_Pricing_Excerpt`
  - 默认保留给人工整理摘要
  - recovery 机器分析不要默认写这里
- `Reply_Comprehensive_Pricing`
  - 只写结构化、可映射的平台 / 形式 / 价格
  - 没有价格，不填
  - 有价格但平台 / 形式对应不上，不填
  - 不允许输出整套占位模板，如 `dedicated - | integration -`
  - 金额统一规范为 `货币符号 + 千分位数字`，例如 `€1,500`、`$12,000`
- `Reply_Main_Dedicated_Rate`
  - 只放主平台主报价
  - 必须是明确 dedicated / review / standalone video 价
  - 平台不明时不填
- `Mail1_Pricing_Excerpt / Mail2_Pricing_Excerpt / Mail3_Pricing_Excerpt`
  - 写机器重新分析后的波次证据块
  - 允许保留 package、bundle、usage、add-on、cross-post、平台覆盖等上下文
  - 需要同时参考正文与附件，不做“只摘一个价格”的过度压缩

推荐结构：

```text
Bundle Package: TikTok + Instagram Cross-post: $2,000
YouTube: dedicated $500 | integration $350
YouTube Shorts: dedicated $800
TikTok: dedicated $1000
Instagram: dedicated $1200 | story $300
```

欧式金额示例统一改写：

```text
1.500€ -> €1,500
12.000 EUR -> €12,000
```

不要这样写：

```text
(Bundle Package): -
(YouTube): dedicated - | integration -
(YouTube Shorts): dedicated - | integration -
```

## 4. 写回原则

- master 更新前必须先备份
- 只能脚本写入
- 不并行写同一份 CSV
- full master 命中不到的行，只留在 audit，不乱补

## 5. `Reply_Stream` 规则

`Reply_Stream` 只允许这三个值：

- `Outreach`
- `Workstream`
- `Manual_Review`

含义：

- `Outreach`：回复的是标准 `Mail1 / Mail2 / Mail3`
- `Workstream`：回复的是日常交接/执行推进邮件
- `Manual_Review`：当前无法稳定判断

对于 recent audit：

- 只有 `Outreach` 可以纳入 replied 主表
- `Workstream` 不纳入当前 reply pipeline
