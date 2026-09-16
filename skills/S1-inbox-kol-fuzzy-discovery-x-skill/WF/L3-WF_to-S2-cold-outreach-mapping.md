---
description: "[Workflow] L3 到 S2 Cold Outreach 映射工作流 | 目标：把 L3 shortlist CSV 直接升级成可进入 Mail1 填充与 draft 的 S2 CSV。"
---

# L3-WF_to-S2-cold-outreach-mapping

> 用途：这份 workflow 不负责找人，也不负责补数。  
> 它负责把 `L3 shortlist CSV` 直接转成可进入 `S2 Cold Outreach` 的业务表。  
> 当前默认主链路是：
>
> `L1 -> L2 -> L3 -> S2 -> Mail1 填充 -> Gmail drafts`
>
> 上游硬规则继承：
>
> - `L1 -> L2`: `max_views >= 5000`
> - `L2 -> L3`: `followers_count >= 1000`

## 一、核心目标

`L1 / L2 / L3` 是 skill 内部过程层。  
`S2 Cold CSV` 是触达执行层。

所以这一层的职责是：

- 保留 `L3` 的判断结果
- 转换成 `S2 Cold` 习惯的字段名
- 预留 `Mail1` 相关字段
- 为后续 `Greeting / Hook / Body` 的 LLM 填充准备干净输入

一句话：

**把技术 shortlist 变成可直接进入冷启动触达的 S2 表。**

## 二、输入与输出

### 输入 CSV

- `workbench/{YYYY-MM-DD}/x_kol_L3_shortlist_batch1_{YYYY-MM-DD}.csv`

### 输出 CSV

- `workbench/{YYYY-MM-DD}/x_kol_S2_cold_batch1_{YYYY-MM-DD}.csv`

### 最终阅读副本

- 默认不生成 batch 级 deliverable 副本
- 最终阅读副本由 merge 阶段统一写入：
  - `deliverables/{YYYY-MM-DD}/【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_final.csv`

### 辅助文件

- `workbench/{YYYY-MM-DD}/x_kol_S2_mapping_audit_batch1_{YYYY-MM-DD}.md`
- `workbench/{YYYY-MM-DD}/x_kol_S2_mapping_runlog_batch1_{YYYY-MM-DD}.json`

## 三、S2 建议字段顺序

1. `分区`
2. `备注`
3. `提报人`
4. `账号ID`
5. `频道/作者名称`
6. `平台`
7. `多平台标记`
8. `账号链接`
9. `语言`
10. `博主国家`
11. `粉丝数`
12. `账号类目标签`
13. `账号类目标签__平台抓取`
14. `置顶最高播放`
15. `近期10条均播`
16. `近10条平均ER（按曝光）`
17. `近10条平均ER（按粉丝）`
18. `rate（USD$)报价`
19. `原价`
20. `账号简介`
21. `账号简介__平台抓取`
22. `Sample Content`
23. `Latest Activity Proof`
24. `粉丝受众`
25. `粉丝性别`
26. `粉丝年龄`
27. `联系方式`
28. `联系方式备注`
29. `外链__平台抓取`
30. `Recommendation`
31. `Mail1发出状态`
32. `Mail1_Hook`
33. `Mail1_Greeting_Name`
34. `Mail1_Subject`
35. `Mail1_Content V1`
36. `Mail1_Content V2`

## 四、字段映射表

| S2 字段 | 来源层 | 来源字段 | 当前是否可稳定产出 | 映射规则 |
| :--- | :--- | :--- | :---: | :--- |
| `分区` | - | - | 是 | 当前默认留空 |
| `备注` | - | - | 是 | 当前默认留空 |
| `提报人` | - | - | 是 | 当前默认留空 |
| `账号ID` | L1/L2/L3 | `username` | 是 | 必须映射成带 `@` 的格式 |
| `频道/作者名称` | L1/L2/L3 | `display_name` | 是 | 直接映射 |
| `平台` | 固定值 | `X` | 是 | 固定写 `X` |
| `多平台标记` | 暂无 | - | 否 | 当前留空 |
| `账号链接` | L2/L3 | `profile_url` | 是 | 直接映射 |
| `语言` | L3 | `primary_language` | 部分 | 若有则映射，否则留空 |
| `博主国家` | L3 | `country_inferred` | 部分 | 若有则映射，否则留空 |
| `粉丝数` | L2/L3 | `followers_count` | 是 | 直接映射 |
| `账号类目标签` | - | - | 是 | 当前默认留空 |
| `账号类目标签__平台抓取` | L2 | `bio` / 平台原始标签 | 是 | 当前按执行口径默认留空 |
| `置顶最高播放` | - | - | 是 | 当前默认留空 |
| `近期10条均播` | 暂无 | - | 否 | 当前留空 |
| `近10条平均ER（按曝光）` | 暂无 | - | 否 | 当前留空 |
| `近10条平均ER（按粉丝）` | 暂无 | - | 否 | 当前留空 |
| `rate（USD$)报价` | 暂无 | - | 否 | 当前留空 |
| `原价` | 暂无 | - | 否 | 当前留空 |
| `账号简介` | - | - | 是 | 当前默认留空 |
| `账号简介__平台抓取` | L2/L3 | `bio` | 是 | 直接映射平台原始 bio |
| `Sample Content` | L1/L2/L3 | `top_tweet_url` + `top_tweet_text` / `sample_posts` | 是 | 格式为 `URL - 帖子原文` |
| `Latest Activity Proof` | 后续活跃补全 | `recent post` | 否 | 当前阶段留空 |
| `粉丝受众` | 暂无 | - | 否 | 当前留空 |
| `粉丝性别` | 暂无 | - | 否 | 当前留空 |
| `粉丝年龄` | 暂无 | - | 否 | 当前留空 |
| `联系方式` | L2 | `contact_value` | 部分 | 当前有值则映射，无值留空 |
| `联系方式备注` | L2 | `contact_note` | 部分 | 当前有值则映射，无值留空 |
| `外链__平台抓取` | L2 | `external_links` | 部分 | 当前有值则映射，无值留空 |
| `Recommendation` | - | - | 是 | 当前默认留空 |
| `Mail1发出状态` | 固定值 | - | 是 | 当前默认留空，表示尚未进入发信状态机 |
| `Mail1_Hook` | 后续内容填充 | LLM output | 否 | Phase B 由 LLM 基于 S2 内容填写 |
| `Mail1_Greeting_Name` | 后续内容填充 | LLM output | 否 | Phase B 由 LLM 基于 S2 内容填写 |
| `Mail1_Subject` | 后续内容填充 | LLM output / template rule | 否 | 当前阶段留空，后续由 S2 内容工作流填写 |
| `Mail1_Content V1` | 后续内容填充 | LLM output | 否 | Phase B 由冻结正文 + LLM 变量填充 |
| `Mail1_Content V2` | 后续内容填充 | optional | 否 | 当前阶段默认留空 |

## 五、两阶段执行

### Phase A: L3 -> S2 Base Mapping

这一步只做结构化映射，不做文案生成。

补充强规则：

- `workbench/` 内的 `x_kol_S2_cold_*.csv` 是正式底稿
- `deliverables/{YYYY-MM-DD}/` 默认只保留 merge 后写入的唯一 final
- `L3 -> S2` 完成时默认不再同步生成 batch 级 deliverable 副本
- 只有显式要求镜像时，才允许额外输出 batch 级 deliverable
- 当前默认会优先回填 `L2` 的 `contact_value/contact_note/external_links`，所以 email 若已在 `Layer2` 命中，会直接进入 `S2`

补充约束：

- `S2` 只承接合法 `L3 shortlist`
- 默认输入应为 `keep/review only` 的 shortlist；若上游历史文件混入 `drop`，应先过滤再映射
- 如果输入的是历史旧版 `L3`，映射脚本也要继承 `L1 views gate`，避免旧残留再次进入 `S2`

### Phase B: S2 Mail1 Content Fill

这一步才进入 `LLM` 驱动的内容填充。

当前历史参考工作流已内收进本 skill：

- `WF/L3-WF_to-S2-DM-fill.md`

若用户明确要求使用 `3.2` cold DM 模板，优先参考：

- `../S2-ag-gmail-bulk-drafts/WF_Cold DM Template.md`
- section `3.2 Approved DM Template - Launch / Media Kit First`

填充目标：

- `Mail1_Greeting_Name`
- `Mail1_Hook`
- `Mail1_Content V1`

可选补充：

- `Mail1_Subject`
- `Mail1_Content V2`

执行原则：

- `Mapping` 脚本不负责直接生成文案
- `LLM` 填充脚本不负责改结构字段
- 两者分开，便于审计和续跑
- 当前 skill 内建议入口：
  - `src/x_kol_discovery/pipelines/run_s2_dm_fill.py`

## 六、字段格式契约

- `账号ID`
  最终统一成带 `@` 的格式。

- `平台`
  统一标准值，只允许 `X`。

- `博主国家`
  统一成中文标准国别，不允许中英混写。

- `语言`
  统一成中文标准表达，例如 `英语`，不允许混用 `en`、`English` 等写法。

- `联系方式备注`
  一旦填写，必须写成“来源 + 结果”的格式，不写空泛备注。

- `外链__平台抓取`
  多个值统一用 ` | ` 拼接；只写原始链接或主域名，不写解释句，不写邮箱。

- `账号简介__平台抓取`
  直接写平台原始 `bio`；不做人工脱水，不做改写。

- `Sample Content`
  必须统一写成 `URL - 帖子原文`；它表示本批主题下最相关的一条命中帖。

- `Mail1_Content V1`
  后续进入 LLM 填充时必须保留真实换行，不能压成单行字符串。

## 七、排序规则

- `S2 Cold CSV` 默认按 `粉丝数` 降序
- `S2` 是执行层，默认先看账号体量，不再按 `max_views` 排序
- 如果 `粉丝数` 相同，再按 `账号ID` 升序

## 八、当前必须留空的字段

- `分区`
- `备注`
- `提报人`
- `多平台标记`
- `账号类目标签`
- `账号类目标签__平台抓取`
- `置顶最高播放`
- `近期10条均播`
- `近10条平均ER（按曝光）`
- `近10条平均ER（按粉丝）`
- `rate（USD$)报价`
- `原价`
- `账号简介`
- `Latest Activity Proof`
- `粉丝受众`
- `粉丝性别`
- `粉丝年龄`
- `Recommendation`
- `Mail1发出状态`
- `Mail1_Hook`
- `Mail1_Greeting_Name`
- `Mail1_Subject`
- `Mail1_Content V1`
- `Mail1_Content V2`

原则：

- 可以保留列
- 但不能编造值
- 当前拿不到就留空

## 九、为什么不再以 S1 为主线

- `S1` 更像 shortlist / review 中间表
- `S2` 才是实际进入冷启动触达的执行表
- 你的当前业务目标不是单纯入池，而是尽快进入 `Mail1` 触达

所以：

- `S1` 退成 legacy / optional
- `S2` 升级为默认业务输出

## 九、脚本方向

当前已有独立脚本：

- `src/x_kol_discovery/pipelines/run_l3_to_s2_mapping.py`

多 batch 合并与 `3.2` handoff 参考：

- `WF/S2-WF_merge-deliverables-and-dm-3.2.md`
