---
tags: [agency, master, field-standard, sop, csv]
date: 2026-03-11
status: active
version: v1.0
---

# Master 字段标准化规范

## 0. 文档用途

本文件用于固定 `Master` 主表的字段口径，避免不同 Agent、不同项目、不同时间段对同一字段采用不同写法。

适用对象：

- `【Master】Rockbase20260307-PartMerge.csv`
- 后续同类 Master 主表

核心原则：

1. 原始信息优先保留，不随意覆盖。
2. 标准化只处理“文本口径混乱”字段。
3. 数字字段当前阶段一律不改。
4. 结构化新增字段不得替代原始字段。

---

## 1. 当前统一范围

本阶段只统一以下字段：

| 字段 | 是否统一 | 统一方式 | 备注 |
| --- | --- | --- | --- |
| 平台 | 是 | 固定官方平台名 | 允许标准化 |
| 语言 | 是 | 统一为中文标准名 | 允许标准化 |
| 国家 | 是 | 统一为中文标准名 | 允许标准化 |
| 粉丝数 | 否 | 保持原样 | 当前阶段禁止改动 |
| 原价 | 否 | 保持原样 | 当前阶段禁止改动 |
| rate（USD$)报价 | 否 | 保持原样 | 当前阶段禁止改动 |

---

## 2. 字段处理原则总表

| 字段类型 | 处理原则 | 是否允许覆盖原值 | 说明 |
| --- | --- | --- | --- |
| 原始文本字段 | 尽量保留 | 否 | 作为历史信息与追溯依据 |
| 标准化文本字段 | 允许统一口径 | 是，需按规范执行 | 仅限平台/语言/国家 |
| 数字字段 | 暂不处理 | 否 | 包括粉丝数、原价、rate |
| 结构化衍生字段 | 新增列承载 | 不覆盖原始列 | 如 dedicated/integrated/bundle 报价 |
| 备注/说明字段 | 保留原文优先 | 否 | 尤其适用于报价说明 |

---

## 3. 平台字段规范

### 3.1 标准写法

| 标准值 | 使用说明 |
| --- | --- |
| YouTube | 统一写法，禁止写 `Youtube` |
| TikTok | 统一写法，禁止写 `Tiktok` |
| Instagram | 统一写法，禁止写 `IG`、`INS` |
| X | 统一写法 |
| 多平台 | 用于同一行明确包含多个平台 |

### 3.2 映射规则

| 原始写法 | 标准值 |
| --- | --- |
| Youtube | YouTube |
| YouTube | YouTube |
| Tiktok | TikTok |
| TikTok | TikTok |
| IG | Instagram |
| INS | Instagram |
| Instagram Reels | Instagram |
| INS/TT | 多平台 |
| TikTok,Instagram | 多平台 |
| YouTube+X | 多平台 |

### 3.3 执行备注

| 场景 | 处理方式 |
| --- | --- |
| 同一达人一行内同时包含多个平台 | 写 `多平台` |
| 需要保留具体平台组合信息 | 放入 `备注` 或后续新增平台说明列 |
| 不确定平台 | 暂不猜测，保留原值后人工确认 |

---

## 4. 语言字段规范

### 4.1 标准写法

| 标准值 | 使用说明 |
| --- | --- |
| 英语 | 英文内容统一归此类 |
| 中文 | 简体中文 |
| 中文-繁体 | 繁体中文内容 |
| 西班牙语 | 标准中文写法 |
| 葡萄牙语 | 标准中文写法 |
| 法语 | 标准中文写法 |
| 德语 | 标准中文写法 |
| 阿拉伯语 | 统一替代 `阿语` |
| 日语 | 标准中文写法 |
| 韩语 | 标准中文写法 |
| 印地语 | 标准中文写法 |
| 多语言 | 明显多语混合 |
| 未标记 | 空值或无法判断 |

### 4.2 映射规则

| 原始写法 | 标准值 |
| --- | --- |
| English | 英语 |
| EN | 英语 |
| 英语 | 英语 |
| 阿语 | 阿拉伯语 |
| 阿拉伯语 | 阿拉伯语 |
| Hindi | 印地语 |
| 印度语 | 印地语 |
| Japanese | 日语 |
| Korean | 韩语 |
| 空值 | 未标记 |

### 4.3 执行备注

| 场景 | 处理方式 |
| --- | --- |
| 一行内明确出现两种及以上语言 | 写 `多语言` |
| 只是受众多语言，不代表内容多语言 | 仍以创作者内容主语言为准 |
| 看不出来语言 | 写 `未标记`，不要猜 |

---

## 5. 国家字段规范

### 5.1 标准写法

| 标准值 | 使用说明 |
| --- | --- |
| 美国 | 标准中文国名 |
| 英国 | 标准中文国名 |
| 加拿大 | 标准中文国名 |
| 澳大利亚 | 标准中文国名 |
| 印度 | 标准中文国名 |
| 巴基斯坦 | 标准中文国名 |
| 阿联酋 | 标准中文国名 |
| 沙特阿拉伯 | 标准中文国名 |
| 日本 | 标准中文国名 |
| 韩国 | 标准中文国名 |
| 法国 | 标准中文国名 |
| 德国 | 标准中文国名 |
| 巴西 | 标准中文国名 |
| 菲律宾 | 标准中文国名 |
| 尼日利亚 | 标准中文国名 |
| 多国/混合 | 用于国家字段本身不是单一国家时 |
| 未标记 | 空值或无法判断 |

### 5.2 映射规则

| 原始写法 | 标准值 |
| --- | --- |
| US | 美国 |
| USA | 美国 |
| United States | 美国 |
| 美国 | 美国 |
| UK | 英国 |
| United Kingdom | 英国 |
| 英国 | 英国 |
| CA | 加拿大 |
| Canada | 加拿大 |
| 加拿大 | 加拿大 |
| South Korea | 韩国 |
| Korea | 韩国 |
| Brazil | 巴西 |
| Japan | 日本 |
| France | 法国 |
| Germany | 德国 |
| Philippines | 菲律宾 |
| Nigeria | 尼日利亚 |
| CA&US | 多国/混合 |
| UK/EU | 多国/混合 |
| 空值 | 未标记 |

### 5.3 执行备注

| 场景 | 处理方式 |
| --- | --- |
| 字段值是市场组合而不是单一国家 | 写 `多国/混合` |
| 国家与受众市场不同 | 国家只记录博主归属，不记录市场判断 |
| 市场判断需求 | 通过 `tag_market` 处理，不写进国家列 |

---

## 6. 数字字段处理政策

当前阶段以下字段一律不改：

| 字段 | 处理政策 | 原因 |
| --- | --- | --- |
| 粉丝数 | 保持原样 | 当前业务依赖原始写法 |
| 原价 | 保持原样 | 保留原始商务语境 |
| rate（USD$)报价 | 保持原样 | 保留原始报价文本结构 |

执行规则：

1. 不做 `K/M/W` 到整数的转换。
2. 不统一千分位。
3. 不拆数值。
4. 不覆盖任何原始报价文本。

---

## 7. 报价字段结构化建议

当前阶段：**建议方案已确定，但暂不强制实施。**

如后续需要结构化报价，新增以下字段，不覆盖原始报价列：

| 字段 | 用途 | 是否覆盖原值 |
| --- | --- | --- |
| 报价_dedicated_usd | 存 dedicated 报价主值 | 否 |
| 报价_integrated_usd | 存 integrated 报价主值 | 否 |
| 报价_bundle_usd | 存 bundle / package / 多平台组合报价 | 否 |
| 报价说明 | 保留原始报价文本或补充说明 | 否 |

### 报价说明字段原则

| 原则 | 说明 |
| --- | --- |
| 原文优先 | 优先保留原始报价原文 |
| 不做摘要替代 | 不建议用机器摘要覆盖原文 |
| 允许补充解释 | 必要时可补充简短人工说明 |
| 不替代原始 rate 列 | `报价说明` 只是补充层 |

---

## 8. 推荐列位策略

如果未来新增标准化列或结构化列，建议按以下顺序管理：

| 区域 | 建议内容 |
| --- | --- |
| 原始基础区 | 平台、语言、国家、粉丝数、报价、简介、受众等原始字段 |
| 标签分析区 | `tag_topics`、`tag_scenarios`、`tag_audience` 等 |
| 结构化商务区 | dedicated/integrated/bundle 报价等新增结构列 |
| 执行区 | 联系方式、联系方式备注、备注、review_status 等 |

当前你已经明确的管理原则是：

| 字段 | 位置原则 |
| --- | --- |
| 标签列 | 放在 `粉丝年龄` 后 |
| 备注 | 放在最后一列 |

---

## 9. Agent 执行红线

后续任何 Agent 处理 Master 时，必须遵守：

| 规则 | 要求 |
| --- | --- |
| 不得擅自改数字字段 | 粉丝数、原价、rate 当前阶段禁止改动 |
| 不得覆盖原始报价文本 | 原始商务信息必须保留 |
| 国家和语言统一用中文 | 固定执行 |
| 平台统一用官方平台名 | 固定大小写 |
| 国家列不承担市场判断 | 市场判断写入 `tag_market` |
| 复合国家值不硬拆 | `CA&US`、`UK/EU` 统一用 `多国/混合` |

---

## 10. 当前推荐执行顺序

| 步骤 | 动作 |
| --- | --- |
| 1 | 先清洗 `平台` 字段 |
| 2 | 再清洗 `语言` 字段 |
| 3 | 再清洗 `国家` 字段 |
| 4 | 数字字段全部跳过 |
| 5 | 后续如需报价结构化，再新增 dedicated/integrated/bundle 相关列 |

---

## 11. 标签设计原则

本标签体系不是只基于一张表设计，而是同时参考以下两个 Master 的内容分布后确定：

- `【Master】Rockbase20260307-PartMerge.csv`
- `【Master】2026Mar-KOL.csv`

原因：

1. 你后续会跨两个 Master 复用同一套标签系统。
2. `Rockbase` 更偏当前执行表，`2026Mar-KOL` 更能暴露长期内容类型和边缘类目。
3. 只看单表，标签池会偏窄；同时看两表，标签矩阵才足够稳定。

标签设计红线：

| 规则 | 要求 |
| --- | --- |
| 不做一个总标签列 | 必须按分面拆列 |
| 每列只放同一类信息 | 不得把主题、市场、风险混写 |
| 标签值用英文下划线风格 | 便于筛选、检索、脚本处理 |
| 解释文字用中文 | 便于人工维护 |
| 单列标签数量受控 | 避免一行塞入过多标签 |

---

## 12. 标签列总览

| 字段 | 用途 | 是否必填 |
| --- | --- | --- |
| `tag_topics` | 内容主题标签 | 是 |
| `tag_scenarios` | 使用场景标签 | 是 |
| `tag_audience` | 受众画像标签 | 是 |
| `tag_narrative` | 叙事/表达风格标签 | 否 |
| `tag_platform_fit` | 平台形态适配标签 | 是 |
| `tag_market` | 市场归属标签 | 是 |
| `tag_commercial` | 商业合作属性标签 | 否 |
| `tag_risk` | 风险与排除标签 | 否 |
| `tag_confidence` | 标签判断置信度 | 是 |

---

## 13. 标签填写通用规则

### 13.1 分隔规则

| 规则 | 要求 |
| --- | --- |
| 多标签分隔符 | 统一使用英文竖线 `|` |
| 标签内部 | 不使用空格，统一使用下划线 `_` |
| 顺序 | 先写主标签，再写次标签 |

示例：

```text
AI_Tools|Productivity|SaaS_Review
```

### 13.2 数量规则

| 字段 | 建议数量上限 |
| --- | --- |
| `tag_topics` | 2-4 个 |
| `tag_scenarios` | 2-4 个 |
| `tag_audience` | 1-3 个 |
| `tag_narrative` | 1-3 个 |
| `tag_platform_fit` | 1-2 个 |
| `tag_market` | 1-3 个 |
| `tag_commercial` | 0-3 个 |
| `tag_risk` | 0-3 个 |

### 13.3 留空规则

| 场景 | 处理方式 |
| --- | --- |
| 无足够证据判断 | 留空，不猜 |
| 只是弱推断 | 可填写，但必须在 `tag_confidence` 标注为 `B_Inferred` 或 `C_Weak` |
| 明显不适用 | 留空，不强行补齐 |

### 13.4 置信度规则

| 标准值 | 含义 |
| --- | --- |
| `A_Explicit` | 字段或内容证据非常明确 |
| `B_Inferred` | 基于简介、类目、标题可合理推断 |
| `C_Weak` | 证据很弱，仅作低置信参考 |

---

## 14. tag_topics 主题标签规范

### 14.1 可用标签池

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `AI_Tools` | AI 工具类 | 以 AI 工具介绍、评测、教程为主 |
| `Productivity` | 效率生产力 | 以效率、工作流、提效工具为主 |
| `Study_Hacks` | 学习方法 | 学生、备考、笔记、复习类内容 |
| `Office_Workflow` | 办公工作流 | 团队协作、办公流程、会议流程 |
| `Knowledge_Management` | 知识管理 | 笔记、知识库、PKM、信息整理 |
| `Career_Development` | 职场发展 | 求职、升职、职业成长 |
| `Founder_Operations` | 创业者运营 | founder、solopreneur、business ops |
| `Team_Collaboration` | 团队协作 | team/project/group work 场景 |
| `Education` | 教育内容 | 教师、教育科技、课堂场景 |
| `SaaS_Review` | SaaS 评测 | 软件工具体验、对比、review |
| `Content_Creation` | 内容创作 | 创作者工具、内容生产流程 |
| `Developer_AI` | 开发者 AI | coding、agent、API、ML、工程向 AI |
| `General_Tech` | 泛科技 | 科技资讯、技术解析、综合科技 |
| `Hardware_Gadgets` | 数码硬件 | 实体数码、设备、配件评测 |
| `Filming_Camera` | 摄影拍摄器材 | filming、camera、镜头、拍摄教程 |
| `Video_Creation` | 视频制作 | 剪辑、视频变现、视频工作流 |
| `Make_Money_Online` | 网赚副业 | MMO、online earning、affiliate 等 |
| `Crypto_Web3` | Crypto/Web3 | 代币、交易、区块链推广 |
| `Lifestyle_Student` | 学生日常/轻生活 | 学生记录、studygram、校园生活 |

### 14.2 填写原则

| 场景 | 处理方式 |
| --- | --- |
| AI 与效率并存 | `AI_Tools|Productivity` |
| 明显软件评测号 | 补 `SaaS_Review` |
| 偏代码/Agent 搭建 | 用 `Developer_AI`，不要误打 `Productivity` |
| 偏硬件评测 | 用 `Hardware_Gadgets`，不要误打 `SaaS_Review` |

---

## 15. tag_scenarios 场景标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `Web_Demo` | Web 演示友好 | 明显适合网页录屏演示 |
| `Screen_Record_Friendly` | 适合屏幕录制 | 教程、软件操作展示强 |
| `Tutorial_Explainer` | 教程拆解型 | 擅长 step-by-step 解释 |
| `Before_After_Comparison` | 前后对比型 | 常用 before/after 说服 |
| `Meeting_Workflow` | 会议工作流 | 会议、纪要、对话管理相关 |
| `Lecture_Review` | 课堂/讲座复盘 | 学习、 lecture、备考复盘 |
| `Team_Project_Collaboration` | 团队协作场景 | group project、多人协作 |
| `Knowledge_Base` | 知识库场景 | knowledge base、信息沉淀 |
| `Research_Summary` | 研究摘要场景 | research、summary、报告生成 |
| `Student_Use_Case` | 学生使用场景 | 受众或内容明显偏学生 |
| `Executive_Use_Case` | 管理者/高管场景 | manager、founder、executive |
| `Creator_Workflow` | 创作者工作流 | 创作者日常内容生产 |
| `Extension_Plugin_Demo` | 插件演示友好 | 明显能承接插件或扩展功能 |
| `Mobile_Capture` | 移动端采集场景 | 手机录制、随手采集、移动输入 |

---

## 16. tag_audience 受众标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `Students` | 学生 | 学生/备考/校园受众明显 |
| `Knowledge_Workers` | 知识工作者 | 白领、office、productivity |
| `Managers` | 管理者 | manager、team lead、operator |
| `Founders` | 创始人/创业者 | founder、solopreneur、business owner |
| `Consultants` | 顾问/专业服务 | consultant、advisor、professional service |
| `Creators` | 内容创作者 | creator economy、博主工具 |
| `Developers` | 开发者 | 编程、AI engineering、API 受众 |
| `Educators` | 教育从业者 | 教师、讲师、edtech |
| `Researchers` | 研究型用户 | 学术研究、分析师、深度研究 |
| `SMB_Owners` | 中小企业主 | SMB owner、小老板、business ops |
| `General_Consumers` | 泛大众消费者 | 受众不够垂直时使用 |

---

## 17. tag_narrative 叙事风格标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `Hands_On_Demo` | 上手演示型 | 边操作边讲 |
| `Tutorial_Step_By_Step` | 分步教程型 | 清楚拆步骤 |
| `Problem_Solution` | 痛点解法型 | 先痛点后方案 |
| `Review_Comparison` | 评测对比型 | 比较不同工具/方案 |
| `Case_Study` | 案例型 | 讲具体案例或使用结果 |
| `Authority_Expert` | 权威专家型 | 更像专家判断 |
| `Peer_Sharing` | 同伴分享型 | 更像经验分享而非专家授课 |
| `Short_Hook_Fast_Cut` | 短钩子快切型 | 强短视频节奏 |
| `Thought_Leadership` | 观点领导型 | 更偏洞察、观点、职业表达 |

执行原则：

| 规则 | 要求 |
| --- | --- |
| 该列只描述表达方式 | 不直接描述内容主题或受众 |
| 一般填 1-3 个 | 优先保留最稳定的表达特征 |
| 优先依据内容形态判断 | `Tutorial_Explainer` 不等于一定是 `Tutorial_Step_By_Step`，需结合简介与类目 |
| 资料不足可留空 | 不强行补齐 |

---

## 18. tag_platform_fit 平台适配标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `YouTube_Longform` | 适合 YouTube 长内容 | 以 YouTube 长视频为主 |
| `TikTok_Shortform` | 适合 TikTok 短视频 | 以 TikTok 为主 |
| `Instagram_Reels` | 适合 IG 短内容 | 以 Instagram 为主 |
| `X_Opinion` | 适合 X 观点传播 | 以 X 为主要扩散阵地 |
| `Multi_Platform` | 多平台分发 | 一行内明确包含多个平台 |

执行原则：

| 规则 | 要求 |
| --- | --- |
| 该列只承载平台形态 | 不得混入地区、语言、市场信息 |
| 一般只填 1 个标签 | 多平台账号最多填 2 个，且需有明确依据 |
| 平台信息不明 | 留空，不猜 |

---

## 19. tag_market 市场标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `English_Market` | 英语市场 | 内容主语言为英语 |
| `US_UK_CA_AU` | 核心英语成熟市场 | 明显更偏美英加澳 |
| `India_Pakistan` | 印巴市场 | 国家或受众明显偏印度/巴基斯坦 |
| `MENA_Arabic` | 中东阿语市场 | 阿拉伯语/中东市场 |
| `EU_Mix` | 欧洲混合市场 | 欧洲多国混合 |
| `Multilingual_Market` | 多语市场 | 内容或市场明显多语言 |

执行原则：

| 规则 | 要求 |
| --- | --- |
| 该列只承载市场归属 | 不得混入 YouTube/TikTok/X 等平台信息 |
| 语言市场与国家市场可并存 | 如 `English_Market|US_UK_CA_AU` |
| 复合市场允许保留 | 如 `Multilingual_Market` |
| 国家字段与市场字段分离 | 国家列写归属地，市场列写投放或语言归属 |

---

## 20. tag_commercial 商业标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `Budget_Friendly` | 预算友好 | 明显价格较友好 |
| `Mid_Tier_Efficient` | 中腰部性价比高 | 粉丝/均播/报价结构较均衡 |
| `Premium_Priced` | 偏贵 | 价格明显偏高 |
| `Likely_Open_To_Brief` | 可能较配合 brief | 简介、合作方式、商务感较成熟 |
| `Need_Heavy_Management` | 需要重管理 | 沟通/内容风格/风险较高 |
| `Likely_Good_For_Affiliate` | 适合联盟分成 | 风格偏工具推荐或转化导向 |
| `Good_For_Whitelisting` | 适合投放授权 | 内容结构适合二剪/广告 |
| `Low_Data_Visibility` | 数据不足 | 关键数据不完整 |

执行原则：

| 规则 | 要求 |
| --- | --- |
| 该列只描述商业执行属性 | 不混入内容赛道和风险判断 |
| 一般填 0-3 个 | 只保留最有决策价值的商务标签 |
| 价格信息不足时允许留空 | 不强行猜预算带 |
| 可基于原价、rate、均播、联系信息综合推断 | 但需保持保守 |

---

## 21. tag_risk 风险标签规范

| 标签 | 中文含义 | 何时使用 |
| --- | --- | --- |
| `Geo_Mismatch` | 地区不匹配 | 与项目目标市场冲突 |
| `Language_Mismatch` | 语言不匹配 | 与项目目标语言冲突 |
| `Brand_Mismatch` | 品牌调性不符 | 内容氛围不适合品牌 |
| `Too_Hardware_Heavy` | 过于偏硬件 | 不适合 SaaS/软件叙事 |
| `Too_Filming_Heavy` | 过于偏拍摄器材 | camera/filming 赛道过重 |
| `Too_Video_Creation_Heavy` | 过于偏视频制作 | video monetize/剪辑工作流过重 |
| `Too_MMO_Heavy` | 过于偏网赚 | online earning/副业导向过强 |
| `Too_Developer_Heavy` | 过于偏开发者 | 偏代码、API、Agent 搭建 |
| `Entertainment_Only` | 纯娱乐向 | 缺乏工具承接力 |
| `Crypto_Risk` | Crypto 风险 | crypto/web3 过重 |
| `No_Page` | 页面缺失 | 账号无法有效查看 |
| `Low_Data_Integrity` | 数据完整性弱 | 数据空缺较多 |

---

## 22. 初始打标建议

基于两个 Master 的现有内容分布，第一轮建议优先高频使用以下标签：

| 分面 | 第一轮优先标签 |
| --- | --- |
| topics | `AI_Tools`、`Productivity`、`SaaS_Review`、`Study_Hacks`、`Office_Workflow`、`Hardware_Gadgets`、`Filming_Camera`、`Developer_AI` |
| scenarios | `Web_Demo`、`Screen_Record_Friendly`、`Tutorial_Explainer`、`Before_After_Comparison`、`Meeting_Workflow`、`Student_Use_Case` |
| audience | `Students`、`Knowledge_Workers`、`Managers`、`Founders`、`Creators`、`Developers` |
| narrative | `Hands_On_Demo`、`Tutorial_Step_By_Step`、`Problem_Solution`、`Review_Comparison` |
| platform_fit | `YouTube_Longform`、`TikTok_Shortform`、`Instagram_Reels`、`X_Opinion`、`Multi_Platform` |
| market | `English_Market`、`US_UK_CA_AU`、`MENA_Arabic`、`India_Pakistan`、`EU_Mix`、`Multilingual_Market` |
| commercial | `Budget_Friendly`、`Mid_Tier_Efficient`、`Premium_Priced`、`Likely_Open_To_Brief`、`Likely_Good_For_Affiliate` |
| risk | `Too_Hardware_Heavy`、`Too_Filming_Heavy`、`Too_Video_Creation_Heavy`、`Too_MMO_Heavy`、`Too_Developer_Heavy`、`Geo_Mismatch` |

原因：

1. 这组标签已经足够覆盖两个 Master 里的高频赛道。
2. 这组标签特别适合你现在最常做的 AI SaaS、效率、学习、会议工具类匹配。
3. 先跑通高频标签，再扩展边缘标签，维护成本最低。
