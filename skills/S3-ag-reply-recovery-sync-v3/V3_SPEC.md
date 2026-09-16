---
tags:
  - social-agency
  - skills
  - reply-recovery
  - v3
date: 2026-03-26
status: draft
---

# S3 Reply Recovery Sync V3 Spec

## 目标重定义

这份文档定义 `S3-ag-reply-recovery-sync-v3` 的 V3 正式规范。

V3 的核心目标不是尽量“聪明抽价”，而是稳定完成三件事：

1. 让单个联系人的回复来龙去脉可读。
2. 让最新有效价格可追溯、可更新、可保守覆盖。
3. 让每次新邮件到来时，系统只更新少数稳定字段，而不是反复重算整表。

## 主表入口与出口

V3 的表格口径固定如下：

- `match / bootstrap` 只参考两个 source master：
  - `Agency/list-master/【S2 Cold】Corestar-1000-KOL.csv`
  - `Agency/list-master/【S2 Cold】Rockbase-580-KOL.csv`
- `writeback` 只写一张 replied master：
  - `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`

补充说明：

- `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL.csv` 保留为历史参考，不再作为 V3 recovery 的正式写入目标。
- 任何新 `thread_id` 只要满足 outreach match 规则，都应尝试先用 `580 / 1000` 做 bootstrap，再落入 `V3` 主表。
- 系统邮件、newsletter、bounce、地址错误类邮件不进入 `manual_review`，而是直接忽略并记为 `ignored`。

## 协作原则

这份文档作为 V2 到 V3 的唯一持续更新方案稿。

- 每次 Steve 明确确认一个字段或规则后，应立即回写到本文件。
- 字段定义优先使用表格表达，至少包含 `字段名` 与 `备注` 两列。
- 主表字段按 `Part 1 / Part 2 / Part 3` 逐步收敛，不一次性定完全部列。
- 未确认项保留为草案，不应伪装成定稿。

## 基础读取规范

- 如果回复内容或附件内容不是英文或简体中文，而是其他语言，例如葡萄牙语、韩语、日语、阿拉伯语等，小语种内容在进入分析包时一律补充中文翻译。
- 原文证据仍然保留，但工作包底稿、分析输入包与后续价格判断优先阅读中文翻译版本。
- 该规则适用于正文、附件 OCR 文本与附件摘录。

## 固定 Workbench 路径

V3 的唯一长期工作目录固定为：

`${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v3/`

历史目录映射：

- `workbench/rockbase-gmail-reply-recovery-v1/` 视为历史 Hub V1
- `workbench/rockbase-gmail-reply-recovery-v2/` 视为历史 Hub V2
- `workbench/rockbase-gmail-reply-recovery-v3/` 视为当前唯一写入的 Hub V3

口头指令协议：

- `Hub`：默认指当前主 Hub；写入时默认指 Hub V3，查历史时默认按 Hub V3 -> Hub V2 -> Hub V1 顺序回查
- `Hub V1`：指 `workbench/rockbase-gmail-reply-recovery-v1/`
- `Hub V2`：指 `workbench/rockbase-gmail-reply-recovery-v2/`
- `Hub V3`：指 `workbench/rockbase-gmail-reply-recovery-v3/`

目录约定：

- `runs/{YYYY-MM-DD}_run-XXX/`
  每一批次的执行产物
- `bodies/`
  正文文件
- `attachments/raw/`
  附件原文件
- `attachments/text/`
  附件 OCR / 文本抽取结果
- `input-packs/`
  单联系人 LLM 输入包
- `output-packs/`
  大模型输出结果
- `audit/`
  完整性检查、异常记录、对比结果

规则：

- 以后涉及这个 skill 的长期产物，应优先写入这个固定目录，不应继续分散在普通 `workbench/{YYYY-MM-DD}/` 下。
- 若需访问历史正文、历史 review table、历史 sync 产物，应先在 Hub V1 / Hub V2 中查找，不应重复迁移旧文件。
- 旧目录名会通过软链接保留，便于历史脚本与旧产物继续访问。
- `workbench/{YYYY-MM-DD}/` 只保留镜像副本、一次性报告或人工 review 稿。

## V3 的三段式视图

### Part 1. 基础信息

这部分放在表最前面，服务人工快速识别联系人。

当前确认字段如下：

| 字段名 | 备注 |
| --- | --- |
| `Source_Tag` | 记录该联系人来自哪个来源表、项目或工作流。 |
| `账号ID` | 联系人的稳定主键，供系统匹配与写回使用。 |
| `频道/作者名称` | 人工阅读时使用的创作者名称。 |
| `平台` | 创作者主要平台，如 YouTube、TikTok、X。 |
| `多平台标记` | 展示位置属于 Part 1，放在 `平台` 后面；填写时机属于 Part 2，由大模型根据当前有效价格涉及的平台语义生成。 |
| `账号链接` | 创作者主页链接，便于人工回跳检查。 |
| `语言` | 创作者或当前沟通链路的主要语言。 |
| `Reply_Contact_Email` | 当前实际参与回复的邮箱地址。 |

当前不放入 Part 1 的字段：

| 字段名 | 备注 |
| --- | --- |
| `Owner` | 更偏运营分配，不属于身份基础信息，后续再决定放置位置。 |
| `Priority` | 更偏运营排序，不属于身份基础信息，后续再决定放置位置。 |

### Part 2. 回复与价格主视图

这部分是给 Steve 看的核心区。重点不是我方发了什么，而是对方怎么回、现在最新价格是什么。

当前草案字段：

| 字段名 | 备注 |
| --- | --- |
| `mail1_reply_block` | 合并 `mail1_reply_at + mail1_reply_body` 的回复块字段。 |
| `mail2_reply_block` | 合并 `mail2_reply_at + mail2_reply_body` 的回复块字段。 |
| `mail3_reply_block` | 合并 `mail3_reply_at + mail3_reply_body` 的回复块字段。 |
| `mail4_reply_block` | 合并 `mail4_reply_at + mail4_reply_body` 的回复块字段。 |
| `mail5_reply_block` | 合并 `mail5_reply_at + mail5_reply_body` 的回复块字段。 |
| `latest_price_raw` | 由大模型提取当前最新有效价格的原始表达，尽量保留对方和价格有关的完整原话。 |
| `latest_price_normalized` | 由大模型输出当前最新有效价格的规范化表达，便于比较与排序。 |
| `latest_price_basis` | 由大模型说明本次判断综合了哪些回复块，以及是否参考了附件内容。 |

说明：

- `mail1_reply_block ~ mail5_reply_block` 用于快速看到针对每一波外联的回复。
- `mail1_reply_block ~ mail5_reply_block` 只允许保留对方的 inbound 回复正文，不允许混入我方 sent 邮件、quoted outbound 内容或其他非回复正文噪音。
- 我方 outbound 正文不再占据主表中心位置，只保留系统级映射关系。
- `多平台标记` 虽然显示位置在 Part 1，但仍然是大模型填写字段，不直接继承主表中的单一 `平台` 列。
- 若当前有效价格涉及多个平台，统一按 `YouTube|TikTok|Instagram` 这种管道分隔格式输出。
- `latest_price_raw` 与 `latest_price_normalized` 是当前主视图中最重要的两列。
- `latest_price_basis` 只保留最低必要说明，不引入过多状态字段。
- `多平台标记 / latest_price_raw / latest_price_normalized / latest_price_basis` 四列都由大模型填写，不由 Python 规则直接决定。
- 实际落表时，`多平台标记` 应排在 `平台` 后面。
- `latest_price_normalized` 允许同时保留“当前有效价 + regular/original 参考价”，但必须明确区分，不允许裸放两个未标记金额。
- `latest_reply_wave / latest_reply_block / latest_reply_attachment_summary / latest_price_source / latest_price_wave / pricing_status / manual_review_reason` 暂时不放入 Part 2 主视图，后续如有必要再决定是否进入 Part 3 或衍生表。

### Part 2 提取原则

V3 不再默认依赖 Python 正则或规则脚本直接决定最新价格。

改为：

1. 先由脚本完成 Gmail 拉取、正文落盘、附件下载、OCR 与文本抽取。
2. 再把 `mail1_reply_block ~ mail5_reply_block` 与附件证据整理成单个联系人的分析输入。
3. 单独运行一次大模型分析 workflow。
4. 由大模型输出 `latest_price_raw / latest_price_normalized / latest_price_basis`。

Part 2 构建注意事项：

- 脚本层必须优先做 inbound-only 清洗。
- 若正文中出现 quoted outbound thread，应在进入 `mailN_reply_block` 前截断。
- 若正文清洗后仍然高度匹配我方标准 outreach 模板，应宁可留空，也不要误写成回复块。
- 不允许把 sent 邮件、quoted mail、自动回复说明页或无关系统噪音直接塞入 `mailN_reply_block`。
- recovery 层识别“这是否属于本轮 outreach thread”时，不能只靠模糊语义，应同时参考：
  - Mail1 初始外联模板
  - `⚙️ Skills/S3-ag-reply-draft-ops/references/reply_templates.md` 中的 `mail2-4` 跟进模板语义
- 若前一封回复给了完整价格、后一封只对其中局部项目进行了修正，则大模型必须做“局部覆盖”而不是整表重置。
- `latest_price_normalized` 应表示综合后的当前有效价格状态，而不是机械复制最后一封回复。
- 若最后一封只是简短修正语句，`latest_price_raw` 可以保留最关键的修正原话，`latest_price_normalized` 则应结合前文完整报价一起输出。
- 若需要同时保留当前有效价与 regular/original 参考价，则当前有效价必须放在前面，参考价必须显式标注为 `[regular/original reference]`，例如 `· YouTube: dedicated $850 [effective] | dedicated $1,000 [regular/original reference]`。

这意味着“抓取”与“理解”是两个独立步骤：

- Step A: Recovery Workflow
- Step B: LLM Pricing Interpretation Workflow

## V3 推荐 Workflow

### Workflow A. Recovery

目标：把数据完整拉回，不负责最终价格判断。

输出内容：

- `mail1_reply_block ~ mail5_reply_block`
- 正文文件
- 附件原文件
- 附件 OCR / 文本抽取结果
- 单联系人聚合输入

附件接线补充：

- 当 `recent_reply_window_preview.csv` 或分段 preview 已经产出后，应允许直接进入附件子流程。
- 附件子流程可通过 `run_attachment_pipeline_from_preview.py` 驱动：
  1. 从 preview 中抽取 `Reply_Thread_ID`
  2. 拉取 full thread 与 attachment inventory
  3. 下载附件到本地
  4. 抽取文本到 `attachments/text`
- 当 preview 规模较大（例如 7d combined preview）时，应优先改用 `run_attachment_pipeline_chunked.py`：
  1. 先按固定 chunk size 拆分 unique `Reply_Thread_ID`
  2. 再逐块执行 `fetch + attachment extraction`
  3. 最后汇总 chunk summary，得到总附件数量与抽取结果
  4. 该模式作为 V3 的默认大批量附件回填工作流
- V3 当前的独立 OCR 方案固定为双 OCR：
  - `macOS Vision OCR`
  - `tesseract`
- 附件 OCR 不再默认只依赖单一引擎；图片与 PDF 页优先走 `Vision + tesseract` 组合判断
- 图片 OCR 类型范围应至少包含：
  - `.png`
  - `.jpg/.jpeg`
  - `.webp`
  - `.heic/.heif`
- `.heic/.heif` 在 OCR 前应先转换为中间 PNG，再进入双 OCR
- 若未来重新接回百度 OCR，应作为第三引擎可选层加入，但不覆盖当前双 OCR 默认口径
- OCR 质检必须保留单独审计层，通过 `audit_ocr_quality_and_price_signals.py` 输出：
  - `ocr_quality_audit.csv`
  - `ocr_price_candidates.csv`
  - `ocr_price_candidates_trusted.csv`
  - `ocr_quality_summary.md/json`
- OCR 审计至少要回答三件事：
  1. 附件文本是 `good / usable / weak / garbled / empty` 中的哪一类
  2. 是否检出了价格表达
  3. 价格是否已被清洗为统一标准格式
- OCR 价格标准化格式固定为：
  - `$1,500`
  - `€3,500`
  - `£250`
- 允许 OCR 先保留 `price_raw`，再把清洗后的结果写入 `price_normalized`
- 如果附件 OCR 只识别出一组金额，但没有明确的平台、形式或套餐标签，模型不得擅自脑补映射为 `TikTok dedicated`、`Instagram story`、`YouTube integration` 等结构。
- 对这类“无标签金额 OCR 证据”，仅允许输出为：
  - `· Bundle Package: $2,000`
  - `· Unmapped Attachment Pricing: $1,450 | $1,950 | $300`
- 只有当附件文本本身明确给出了平台/形式映射时，才允许写成：
  - `· YouTube: dedicated $500 | integration $350`
  - `· Instagram: reel $250 | story $150`

### Workflow B. LLM Pricing Interpretation

目标：基于完整回复链与附件证据，由大模型判断当前最新有效价格。

输入建议：

- 单个联系人的 `mail1_reply_block ~ mail5_reply_block`
- 附件证据摘要
- 必要时附上正文全文与附件 OCR 全文

输出建议：

| 字段名 | 备注 |
| --- | --- |
| `latest_price_raw` | 大模型判断后的“最新有效价格原始表达”，优先保留最完整、最能代表当前有效报价的一句或一组原始表达。 |
| `latest_price_normalized` | 大模型对当前有效价格做出的规范化表达。格式沿用 V2 中 `Reply_Comprehensive_Pricing` 的结构化思路。 |
| `latest_price_basis` | 大模型简要说明此价格综合了哪些 `mail1_reply_block ~ mail5_reply_block`，以及是否参考附件。 |

### 关于 `latest_price_raw` 的定义

`latest_price_raw` 不应简单等于“最新邮件里的原话”，也不应简单等于“正则命中的一句话”。

V3 建议定义为：

- 由大模型阅读 `Mail1 ~ MailN` 回复与附件证据后，
- 选择“当前最新有效价格”对应的最完整一句原始表达，
- 优先保留真实语气、渠道、形式与价格上下文，
- 而不是机械截取最新邮件中的任意金额句。

换句话说：

- 如果最新邮件只是确认旧价，`latest_price_raw` 可以引用较早那封真正报价格的原话。
- 如果最新邮件正文没有价格、附件里有新价格，`latest_price_raw` 应引用附件证据。
- 如果最新邮件给了更新报价，`latest_price_raw` 应引用最新有效报价那句原话。
- `latest_price_raw` 中的货币符号与数字写法应尽量保留作者原文，不做规范化改写。

### 关于 `latest_price_basis` 的定义

`latest_price_basis` 不写长解释，只写最小必要判断依据。

建议格式：

```text
mail2_reply_block + mail3_reply_block | attachment_used=yes
```

或：

```text
mail4_reply_block only | attachment_used=no
```

### 关于 `latest_price_normalized` 的定义

`latest_price_normalized` 继承 V2 中 `Reply_Comprehensive_Pricing` 的设计目标：

- 只写结构化、可执行的价格表达
- 只在平台 / 形式 / 价格映射清晰时填写
- 不允许输出整套占位模板
- 金额统一规范为 `货币符号 + 千分位数字`
- 建议使用多行分组格式，而不是单行扁平格式
- `Bundle Package` 若存在，固定放在最上方
- 每一行前统一加 `·`

数字规范补充：

- `latest_price_normalized` 中的货币符号应使用标准货币符号，例如 `$`、`€`、`£`。
- `latest_price_normalized` 中的数字统一使用千分位分隔表达。
- 不论原文是美式、欧式还是其他本地写法，进入 `latest_price_normalized` 后都统一改写为标准分隔格式。
- 若同一项同时保留当前有效价与参考价，必须使用显式标签区分：
  - 当前有效价：`[effective]`
  - 历史 regular/original 参考价：`[regular/original reference]`
- 不允许在 `latest_price_normalized` 中出现未标记的第二个金额，否则视为格式不合规。

示例：

```text
1.500€ -> €1,500
12.000 EUR -> €12,000
1500 euro -> €1,500
12000 USD -> $12,000
```

当前确认格式：

```text
· Bundle Package: TikTok + Instagram Cross-post: $2,000
· YouTube: dedicated $500 | integration $350
· YouTube Shorts: dedicated $300
· TikTok: dedicated $800 | integration $500
· Instagram: dedicated $600 | reel $450 | story $200
```

如需同时表达当前有效价与 regular/original 参考价，使用下面的区分格式：

```text
· YouTube: dedicated $850 [effective] | dedicated $1,000 [regular/original reference]
· Instagram: reel $425 [effective] | reel $500 [regular/original reference]
```

V3 延续这种结构化表达，但改为由大模型阅读完整回复链后生成，而不是由 Python 规则硬抽。

### Part 3. 系统字段

这部分放在最后，服务脚本更新与追溯，不干扰人工读表。

V3 应尽量沿用旧 `【S3 ReplyOps】Corestar-Replied-KOL.csv` 的字段语义与字段名传统，避免重构时破坏旧 skill；但正式写入目标应是 `【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`。

V3 当前正式保留并优先使用以下核心字段：

| 字段名 | 备注 |
| --- | --- |
| `账号ID` | Person 层主键。系统更新最终应尽量落到这个联系人行。 |
| `Reply_Contact_Email` | 当前回复邮箱。抓取回 Gmail 后，常作为第一层联系人匹配线索。 |
| `Reply_Thread_ID` | 当前活跃 Gmail thread 主键。后续同 thread 的新邮件优先直接命中此行。 |
| `Reply_Last_Message_ID` | 当前该行记录的最新 inbound message id。用于确认本行最后一次有效更新落点。 |
| `Outbound_Message_IDs` | 我方已发送 outbound 的 message id 映射。用于判断对方回复的是哪一波。 |
| `Latest_Inbound_Message_ID` | 本次最新抓取到的 inbound message id。用于增量去重和更新判断。 |
| `Latest_Inbound_InReplyTo` | 最新 inbound 的 `In-Reply-To`。用来和 `Outbound_Message_IDs` 对齐，判断波次。 |
| `Reply_Stage` | 当前回复阶段，供系统做状态推进。 |
| `Reply_Stream` | 区分 `Outreach / Workstream / Ignored`。 |
| `Pipeline_Stage` | 运营层阶段字段，系统在安全条件下可刷新。 |
| `Reply_Count` | 当前 thread 内有效回复轮次数量。用于主表排序与处理优先级控制。 |
| `Capture_Run_ID` | 本次抓取批次 id。用于追溯本轮 recovery。 |
| `Capture_At` | 本次抓取时间。 |
| `Reply_Body_File` | 最新 inbound 正文落盘路径。 |

如果附件链路继续保留，建议在 V3 中新增：

| 字段名 | 备注 |
| --- | --- |
| `Reply_Attachment_Files` | 最新 inbound 对应的附件清单路径或聚合路径。 |
| `Reply_Attachment_Text_Files` | 最新 inbound 对应的附件抽取文本路径或聚合路径。 |

以下字段不再保留在 V3 主表，而是下沉到 workbench 历史快照中：

| 字段名 | 处理方式 |
| --- | --- |
| `Reply_Status` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Reply_Needs_Manual_Review` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Manual_Review_Reason` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Manual_Review_Focus` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Owner` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Priority` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Final_Outcome` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Ops_Notes` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |
| `Reply_Analysis` | 从主表移除，保留在 `part3_legacy_snapshot_before_trim.csv` |

### Part 3 的定位逻辑

系统不是只靠一个字段找人，而是按下面的层级定位：

1. 先用 `Reply_Thread_ID` 找已有行。
2. 如果 thread 未命中，再尝试用 `Reply_Contact_Email` 找联系人行。
3. 如果仍未命中，再回退到上游 source 表做 bootstrap，把结果落回 `账号ID`。
4. 命中后，再用 `Latest_Inbound_Message_ID` 做去重，避免重复写入同一封邮件。

换句话说：

- `账号ID` 负责“这个人是谁”
- `Reply_Thread_ID` 负责“这条 Gmail 对话是谁的当前主线程”
- `Latest_Inbound_Message_ID` 负责“这封最新回复有没有处理过”
- `Latest_Inbound_InReplyTo + Outbound_Message_IDs` 负责“这封回复属于 Mail 几”

### Part 3 的波次判断逻辑

当前脚本的核心做法是：

- 从 Gmail thread 中提取我方 outbound message id
- 压成 `Outbound_Message_IDs`
- 再读取对方最新 inbound 的 `In-Reply-To`
- 用 `Latest_Inbound_InReplyTo == Outbound_Message_IDs[mailN]` 判断其属于 `mailN`

这也是为什么 V3 虽然主视图会支持 `mail1_reply_block ~ mail5_reply_block`，但系统字段仍必须保留 `Outbound_Message_IDs`。

补充规则：

- `Outbound_Message_IDs` 不应只记录前三波，而应支持动态 `mailN`，例如：

```text
mail1:xxx|mail2:yyy|mail3:zzz|mail4:aaa|mail5:bbb
```

- 只要最新 inbound 的 `In-Reply-To` 命中其中任意一波 outbound id，就应优先判定为本轮 outreach，而不是误归入日常 workstream。

### Part 3 的增量更新逻辑

由于 Gmail 会持续新增邮件，V3 必须支持反复抓取、持续更新。

当前稳定链路应是：

1. 用 checkpoint 缩小抓取窗口。
2. 抓回 thread 后按 `message_id` 去重。
3. 命中已有 `Reply_Thread_ID` 的联系人行后，只更新该 thread 的新 inbound。
4. 把最新结果写入：
   - `Latest_Inbound_Message_ID`
   - `Latest_Inbound_InReplyTo`
   - `Reply_Last_Message_ID`
   - `Reply_Last_At`
   - `Reply_Last_Subject`
   - `Reply_Body_File`
   - `Capture_Run_ID`
   - `Capture_At`

### Part 3 的扩展规则

如果后续出现 `mail4 / mail5 / mail6 ...`，主视图部分可以继续追加：

- `mail4_reply_block`
- `mail5_reply_block`
- `mail6_reply_block`

但底层系统字段不需要按同样方式无限复制。

底层只需要持续维护：

- `Outbound_Message_IDs`
- `Latest_Inbound_InReplyTo`

因为波次本质上是靠 `In-Reply-To` 与 outbound message id 映射判断出来的，而不是靠固定三列硬编码。

### Part 3 设计原则

- 优先保留现有字段名，方便在原 skill 上升级。
- Person 的最终稳定落点仍应是 `账号ID`。
- Thread 的最终稳定落点应是 `Reply_Thread_ID`。
- 单封新邮件的增量去重锚点应是 `Latest_Inbound_Message_ID`。
- 波次判断锚点应是 `Latest_Inbound_InReplyTo + Outbound_Message_IDs`。
- Part 3 是系统层，不追求好看，只追求稳定可更新。
- V3 主表只保留“当前更新必须依赖”的系统字段。
- 历史状态、人工 review、运营备注类字段不再占据主表，而是沉入 workbench 快照。

### 主线排序规则

当 reply thread 进入 V3 主线后，默认排序应服务于“先吃掉简单且最新的线程”，而不是先啃最长线程。

当前确认排序如下：

| 排序优先级 | 字段 | 顺序 | 备注 |
| --- | --- | --- | --- |
| 1 | `问题行标记` | 正常行在前 | `备注` 不为空且无 mail 的问题行应沉底 |
| 2 | `Section 行标记` | section 最后 | `--- M1 ---` 等分隔行固定沉到整表最后 |
| 3 | `Reply_Count` | 从少到多 | 先处理短线程，降低理解成本与 token 消耗 |
| 4 | `Reply_Last_At` | 从新到旧 | 同等复杂度下优先处理最新回复 |
| 5 | `频道/作者名称` | A-Z / 常规升序 | 作为稳定兜底排序键 |

补充说明：

- 默认不采用 `Reply_Count` 从多到少，因为长线程更复杂、上下文更重、价格修正链更容易失真。
- 只有在“历史复杂线程专项清理”场景下，才临时改用 `Reply_Count` 从多到少。
- `mail1_reply_block ~ mail5_reply_block` 全空、且 `备注` 已标记为问题的行，应沉到底部但位于 section 行之前。

## V3 的数据分层

主表不应该同时承担“真相源”和“明细仓库”两种职责。

建议保留三层：

1. `message_timeline`
2. `pricing_evidence`
3. `contact_rollup`

### message_timeline

一行一封邮件，保存回复链路真相。

建议最小字段：

- `contact_id`
- `thread_id`
- `message_id`
- `in_reply_to`
- `direction`
- `wave`
- `sent_at`
- `from_email`
- `subject`
- `body_text`
- `body_summary`
- `attachment_count`
- `attachment_flag`

### pricing_evidence

一行一条价格证据，正文和附件都进入这一层，不直接覆盖主表。

建议最小字段：

- `contact_id`
- `message_id`
- `wave`
- `evidence_source`
- `attachment_name`
- `evidence_text_raw`
- `evidence_text_clean`
- `price_raw`
- `price_normalized`
- `currency`
- `pricing_type`
- `platform`
- `confidence`
- `needs_review`

### contact_rollup

一行一个联系人，只保留最新可执行状态。

建议最小字段：

- `contact_id`
- `creator_name`
- `reply_contact_email`
- `latest_inbound_at`
- `latest_reply_wave`
- `latest_price_wave`
- `latest_price_source`
- `latest_price_normalized`
- `latest_price_excerpt`
- `pricing_status`
- `manual_review_reason`

## V3 最新价格更新原则

V3 不再采用“见到金额就直接覆盖”的简单规则。

建议改成三步：

1. 先提取价格证据。
2. 再将完整回复链交给大模型理解。
3. 最后才决定是否更新 `latest_price_*`。

覆盖规则建议：

- 最新 inbound 有明确新价格，且大模型判断证据清晰：允许覆盖。
- 最新 inbound 只是确认旧价格：保留原有效价格，并记录确认关系。
- 正文无价格、附件有明确价格：附件可接管。
- 最新邮件价格模糊或平台不清：不覆盖旧价格，转人工审核。

## 当前进度快照

截至 2026-03-27，V3 已完成以下进度：

1. 主表已切换到 V3 可视结构，Part 1 / Part 2 / Part 3 的主列顺序已经落地。
2. `mail1_reply_block ~ mail5_reply_block` 已进入主表，且已加入 inbound-only 清洗规则。
3. 已从 Hub V1 / Hub V2 回查并补齐一轮 reply body，优先修复 `mail2_without_mail1` 与本地正文缺失问题。
4. 已完成空白 `mail1_reply_block` 的分类，区分 `section_row / empty_body_file / auto_reply / no_body_reference / outbound_filtered_or_unverified`。
5. 已完成第一轮与第二轮 Part 2 LLM 样本测试，并验证“前文完整报价 + 后文局部修正”的合并判断链路可行。
6. 当前大模型输出的四个核心字段为：
   - `多平台标记`
   - `latest_price_raw`
   - `latest_price_normalized`
   - `latest_price_basis`

## 下一阶段执行口径

下一阶段不直接在旧样本上反复打补丁，而是先做“全量抓取最新资料 -> 再统一清洗 -> 再统一升级”。

执行顺序固定为：

1. 先从 Gmail / Hub / 历史正文与附件来源中，把目前最新的 thread、body、attachment 资料尽量完整抓回。
2. 再统一做 inbound-only 清洗、quoted outbound 截断、小语种翻中、正文与附件补齐。
3. 再统一构建新的 `mail1_reply_block ~ mail5_reply_block`。
4. 最后再批量运行大模型填写：
   - `多平台标记`
   - `latest_price_raw`
   - `latest_price_normalized`
   - `latest_price_basis`

也就是说，V3 接下来的主轴是：

- 先把最新资料抓全
- 再把数据清干净
- 再做价格理解与升级写回

## 附件模块的角色

附件分析模块必须保留，但职责应收敛：

- 下载附件
- OCR / 文本抽取
- 输出附件证据片段
- 标记是否含价格线索

附件模块不直接决定最终价格，只向 `pricing_evidence` 层供给证据。

## 为什么这是更稳的 V3

因为它把三件事拆开了：

- 对话来龙去脉：看 `message_timeline`
- 价格证据来源：看 `pricing_evidence`
- 当前执行决策：看 `contact_rollup`

这样即使自动抽价效果一般，也不会污染全表；最差情况只是最新价格进入人工审核，而不会丢掉上下文和证据链。

## 下一步建议

进入实现前，先继续确定三件事：

1. `mail1_reply_body / mail2_reply_body / mail3_reply_body` 是否够用，还是要支持动态更多波次。
2. `latest_price_*` 是否只保留一个主价格，还是保留 `dedicated / integration / bundle` 三类。
3. V Two 是先做“衍生视图升级”，还是直接重构底层 `timeline + evidence + rollup`。
