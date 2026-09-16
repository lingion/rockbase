---
name: s1-inbox-enrichment-x
description: 面向已知 X 名单的字段 enrichment 技能：负责 tweets 抓取、事实字段补全、handle 修复、finalize 标记与 recommendation payload 输出；不负责 fuzzy discovery。
---

# S1 Inbox Enrichment X

本技能只负责一层：

- **Enrichment Layer**
  - 已知名单
  - 已知 `@handle`
  - 已知目标表
  - 需要把 X 的事实字段和计算字段补全

本技能不负责：

- 模糊主题找人
- query expansion
- bird 搜索
- candidate pool discovery
- 最终客户口径写作
- 报价判断
- 主观推荐直接写回

## 适用任务

- 抓取账号最近约 `100` 条 tweets
- 把原始 JSON 固化到当天 `workbench/{YYYY-MM-DD}/`
- 回填：
  - `频道/作者名称`
  - `账号链接`
  - `语言`
  - `粉丝数`
  - `账号简介__平台抓取`
  - `外链__平台抓取`
  - `近期10条均播`
  - `近10条平均ER（按曝光）`
  - `近10条平均ER（按粉丝）`
- 生成 Recommendation 独立步骤所需的本地 JSON 输入

## 目录结构

```text
S1-inbox-enrichment-X/
├── .env -> 全局 SECRTE_API_Key.env 软链接
├── LAYER2-WORKFLOW.md
├── SKILL.md
├── UPGRADE-LOG.md
├── scripts/
│   ├── load_env.py
│   ├── fetch_x_user_tweets.py
│   ├── enrich_x_csv_layer2.py
│   ├── finalize_x_csv_layer2.py
│   ├── repair_x_handles.py
│   ├── audit_x_handles_via_omni.js
│   ├── run_layer2_workflow.py
│   └── build_recommendation_payload.py
```

兼容说明：

- 旧目录名 `S1-inbox-X-enrichment` 已重命名为 `S1-inbox-enrichment-X`
- 若外部脚本、自动化或文档仍引用旧目录名，需要一并切换

## 执行原则

1. 先抓原始 JSON，再回填 CSV
2. 所有 API 原始结果必须进入当天 `workbench/{YYYY-MM-DD}/`
3. Recommendation 必须在 JSON 落盘后独立执行
4. 数字格式统一遵循 spec：
   - `粉丝数`：`K/M`
   - `近期10条均播`：整数 + 千分位
   - `ER`：百分比 + 1 位小数
   - recent-10 指标仅基于独立原创主帖，不纳入 `reply` / `retweet` / `quote tweet`
   - 若源 JSON 最新活动早于 `2026-01-01`，清空 recent-10 指标
5. 标准 Layer 2 默认顺序是：
   - 备份
   - 去重
   - 首轮抓取
   - 首轮回填
   - 失败项 handle 修复
   - 二次抓取 / 二次回填
   - `404` / `unresolved` / `media/institution` 标记与沉底
6. API 抓取默认分批：
   - `10 个一组`
   - 禁止默认全量一次性抓取
7. 如果发现上次遗留的 `fetch_x_user_tweets.py` 进程未退出：
   - 先清理旧抓取进程
   - 再继续新的 `10 个一组` 续跑
8. workflow 的最终收口产物必须包括：
   - 主表 finalize
   - retry queue JSON

## 推荐执行顺序

1. 先读 `LAYER2-WORKFLOW.md`
2. 如需了解最近升级与行为变化，读 `UPGRADE-LOG.md`
3. 标准 enrichment 用 `scripts/run_layer2_workflow.py`
4. 只在需要人工插入 handle 修复时，拆开使用 `fetch` / `enrich` / `repair`
5. 用 `scripts/build_recommendation_payload.py` 生成 Recommendation 独立分析输入

## 脚本入口

- 标准 enrichment workflow：
  - `python3 scripts/run_layer2_workflow.py --csv <csv> --batch-name <name> --mode apply`
- 单账号 / 批量抓取：
  - `python3 scripts/fetch_x_user_tweets.py --csv <csv> --handle-col 账号ID`
- Layer 2 回填：
  - `python3 scripts/enrich_x_csv_layer2.py --csv <csv> --mode preview`
  - `python3 scripts/enrich_x_csv_layer2.py --csv <csv> --mode apply`
- 最终标记与沉底：
  - `python3 scripts/finalize_x_csv_layer2.py --csv <csv> --mode apply`
  - 会自动产出 `x_retry_queue_<table>.json`
- Handle 修复：
  - `python3 scripts/repair_x_handles.py --csv <csv> --mapping-json <json>`
- Omni-Chrome 探针：
  - `node scripts/audit_x_handles_via_omni.js <input.json> <output.json>`
- Recommendation 输入包：
  - `python3 scripts/build_recommendation_payload.py --csv <csv> --product OpenClaw`

## 字段边界

- 只回填 X 可证实事实和基于事实可稳定计算的字段
- 不把 `Recommendation` 当作 API 原生字段
- `博主国家 / 报价 / 粉丝画像 / 联系方式` 不强行猜
- 不承担任何 fuzzy discovery 或主题搜索职责

## Workflow Decision

这个 skill 现在已经明确采用：

- 单独的 enrichment workflow 文件
- 单独的 enrichment 入口脚本
- 失败项 handle repair 循环

也就是说，本技能现在是一套纯字段 enrichment 流程，不再承载 discovery。
