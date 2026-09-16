---
description: "[Process] S1 Inbox -> S2 Cold 迁移 SOP | 场景：将 Inbox 中已满足 cold outreach 条件的 KOL 以剪切方式迁入 Corestar / Rockbase。"
---
# 🛰️ [Process] S1 Inbox -> S2 Cold 迁移 SOP

> **本工作流基于 `s1-inbox-enrichment` 技能，负责把 `S1 Inbox` 中已满足条件的 KOL，以剪切方式迁移到 `S2 Cold` 的 Corestar 或 Rockbase 表。**

## 一、 核心目标 (Objective)

把 `【S1 Master】Inbox-All-Platforms.csv` 中已经具备 cold mail 条件的达人，迁移到：

- `【S2 Cold】Corestar-1000-KOL.csv`
- `【S2 Cold】Rockbase-580-KOL.csv`

迁移原则是：

- **先映射、再写入、最后从 S1 移除**
- **使用剪切，不使用复制**
- **只有写入成功且核验通过，才允许从 S1 删除原行**

## 二、 典型触发条件 (Typical Trigger)

本轮优先适用以下场景：

- `S1` 中 `联系方式备注` 显示 `EasyKOL抓取成功`
- `联系方式` 非空
- `账号ID / 频道/作者名称 / 平台 / 账号链接` 基础字段完整

对于本项目当前数据，可先用：

- `联系方式备注 contains EasyKOL`
- 且 `联系方式` 非空

作为 `S1 -> S2 Corestar` 的首轮试跑筛选条件。

## 三、 剪切规则 (Cut Semantics)

`剪切` 的定义必须明确：

1. 从 `S1` 选出待迁移行
2. 按目标表字段映射生成写入行
3. 先写入 `S2`
4. 校验 `S2` 落表成功
5. 成功后，才从 `S1` 删除该行

禁止：

- 先删 `S1` 再写 `S2`
- 未校验写入成功就删除源行
- 同一达人重复迁移到同一目标表

## 四、 目标表选择 (Routing)

### 1. 迁入 `Corestar`

适合：

- 先跑批量 cold mail
- 字段要求较轻
- 先验证迁移链路

### 2. 迁入 `Rockbase`

适合：

- 需要更完整的商务运营字段
- 后续要继续做推荐分、标签体系、利润和投放判断

默认建议：

- **首轮先跑 `S1 -> S2 Corestar`**
- 字段与迁移逻辑稳定后，再扩展到 `Rockbase`

### 3. 正式 S2 文件协议

正式 S2 表必须使用稳定主表路径，不创建日期副本：

- Corestar 默认目标：`Agency/list-master/【S2 Cold】Corestar-1000-KOL.csv`
- Rockbase 默认目标：`Agency/list-master/【S2 Cold】Rockbase-580-KOL.csv`

执行规则：

- 正式迁移写入已有目标表顶部，不写入 `workbench/`
- dry-run / test-copy / preview 只能输出到 `workbench/{YYYY-MM-DD}/`
- 写入前必须同时备份 S1 源表和 S2 目标表到 `Agency/list-bak/{YYYY-MM-DD}/`
- 目标表已有记录时，优先用 `账号链接` 去重；`账号ID` 重名只作为复核提示，不默认阻断跨平台或历史同名账号

## 五、 字段映射关系 (Field Mapping)

### A. 可直接对应的字段

| S1 字段 | S2 Corestar | S2 Rockbase | 规则 |
| :------ | :---------- | :---------- | :--- |
| `备注` | `备注` | `提报备注` | 原样迁移 |
| `账号ID` | `账号ID` | `账号ID` | 原样迁移 |
| `频道/作者名称` | `频道/作者名称` | `频道/作者名称` | 原样迁移 |
| `平台` | `平台` | `平台` | 建议先标准化 |
| `账号链接` | `账号链接` | `账号链接` | 原样迁移 |
| `语言` | `语言` | `语言` | 原样迁移 |
| `博主国家` | `博主国家` | `博主国家` | 原样迁移 |
| `粉丝数` | `粉丝数` | `粉丝数` | 原样迁移 |
| `近期10条均播` | `近期10条均播` | `近期10条均播` | 原样迁移 |
| `rate（USD$)报价` | `rate（USD$)报价` | `rate（USD$)报价` | 当前可为空 |
| `原价` | `原价` | `原价` | 当前可为空 |
| `粉丝受众` | `粉丝受众` | `粉丝受众` | 原样迁移 |
| `粉丝性别` | `粉丝性别` | `粉丝性别` | 原样迁移 |
| `粉丝年龄` | `粉丝年龄` | `粉丝年龄` | 原样迁移 |
| `联系方式` | `联系方式` | `联系方式` | 原样迁移 |
| `联系方式备注` | `联系方式备注` | `联系方式备注` | 原样迁移 |

### B. 需要补进 S2 的平台原始抓取字段

这 3 个字段当前在 `S1` 有，但 `S2` 两张表没有；建议补入并紧跟相似字段之后：

| S1 字段 | S2 建议新增字段 | 插入位置建议 |
| :------ | :-------------- | :----------- |
| `账号类目标签__平台抓取` | `账号类目标签__平台抓取` | 放在 `账号类目标签` 后面 |
| `账号简介__平台抓取` | `账号简介__平台抓取` | 放在 `账号简介` 后面 |
| `外链__平台抓取` | `外链__平台抓取` | 放在 `外链(S列)` 后面 |

### C. 目标表独有字段

#### `Corestar` 独有字段

- `提报时间`
- `提报人`
- `Mail1_Mode`
- `Mail1_Variant`
- `Mail1_Greeting_Name`
- `Mail1_Hook`
- `Mail1_Subject`
- `Mail1_Content V1`
- `Mail1_Content V2`
- `Mail1_Reason`

#### `Rockbase` 独有字段

- `分区`
- `Email发出时间`
- `提报人`
- `多平台标记`
- `置顶最高单条播放量`
- `CPM`
- `利润`
- `tag_topics`
- `tag_scenarios`
- `tag_audience`
- `tag_narrative`
- `tag_platform_fit`
- `tag_market`
- `tag_commercial`
- `tag_risk`
- `tag_confidence`
- `Rockbase推荐分`
- `联系方式_alt`
- `Greeting_Name`
- `Email_Hook`
- `Email_Subject`
- `Email_Content V1`
- `Email正文`

## 六、 默认补值规则 (Default Fill Rules)

### 1. `Corestar`

- `提报时间`：写入迁移当天日期
- `提报人`：按本轮执行人填写
- `分区`：写入迁移当天日期，例如 `2026-04-15`
- `Mail1_Mode`：默认 `A_unified`
- `Mail1_Variant`：默认 `A1_media_kit_soft`
- `Mail1_Greeting_Name / Mail1_Hook / Mail1_Subject / Mail1_Content V1 / Mail1_Content V2 / Mail1_Reason`：留空，后续 `S2` cold mail workflow 再生成

### 2. `Rockbase`

- `提报备注`：来自 `S1` 的 `备注`
- `Email发出时间`：写入入表当天
- `提报人`：按本轮执行人填写
- `多平台标记`：默认留空
- `置顶最高单条播放量`：留空
- `CPM`：留空
- `利润`：留空
- `tag_*`：留空，后续补
- `Rockbase推荐分`：留空
- `联系方式_alt`：留空
- 邮件字段：留空，后续 cold mail 准备时补

## 七、 当前缺失字段判断 (Gap Summary)

### 1. `Corestar` 当前缺的关键字段

- `账号类目标签__平台抓取`
- `账号简介__平台抓取`
- `外链__平台抓取`

### 2. `Rockbase` 当前缺的关键字段

- `账号类目标签__平台抓取`
- `账号简介__平台抓取`
- `外链__平台抓取`

### 3. 不建议从 `S1` 直接写入的字段

- `Email_Hook`
- `Greeting_Name`
- `Email_Subject`
- `Email_Content V1`
- `Email_Content V2`
- `Email正文`
- `Mail1_Greeting_Name`
- `Mail1_Hook`
- `Mail1_Subject`
- `Mail1_Content V1`
- `Mail1_Content V2`
- `Mail1_Reason`
- `tag_*`
- `Rockbase推荐分`
- `CPM`
- `利润`

这些字段属于 `S2 / S4 / S5` 的后续生成层，不属于 `S1 Inbox` 原始迁移层。

## 八、 首轮试跑建议 (Pilot Run)

首轮建议只做：

- `S1 -> S2 Corestar`
- 筛选条件：`联系方式备注 contains EasyKOL抓取成功`
- 且 `联系方式` 非空

原因：

- 当前样本量足够，已有 `83` 条左右可试跑
- `Corestar` 字段较轻，更适合验证剪切逻辑
- 能先确认平台原始抓取字段补位是否顺手

## 九、 执行顺序 (Run Order)

1. 先备份 `S1` 和目标 `S2` 表
2. 检查目标 `S2` 是否已补齐 3 个平台抓取字段
3. 按筛选条件选出待迁移行
4. 生成字段映射表
5. 正式写入 `S2`
6. 校验写入条数、关键字段和去重结果
7. 校验成功后，从 `S1` 删除原行
8. 输出迁移日志与回执到 `workbench/{YYYY-MM-DD}/`

## 十、 输出产物 (Output)

- 迁移日志
- 写入前后行数对比
- 迁移字段映射表
- 删除前源行备份
- 去重与异常报告

## 十一、 命名建议 (File Naming)

本文件建议命名为：

- `S1-WF_inbox-to-S2-cold-migration-sop.md`

原因：

- 保持与 `S1-WF_kol-enrichment-sop.md` 命名风格一致
- 明确来源阶段是 `S1`
- 明确目标阶段是 `S2 Cold`
- 明确本文件是迁移型 workflow
