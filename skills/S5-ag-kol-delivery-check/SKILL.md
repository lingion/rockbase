---
name: ag-kol-delivery-check
description: 用于 KOL 名单交付前的轻量整理与上传副本准备。默认只执行 Phase 1-2：先备份并清洗主表，再做脏值二次检查，并在确认进入交付副本准备时完成上传副本生成、按基准表头删列、删除 Part2 与 preview；Phase 3 只在用户确认后执行正式上传。目标是尽量脚本化自动处理，只把最后仍不稳定的项汇报给用户。
---

# KOL Delivery Check

这个 skill 接管并内置了原先的规则母版：

- `S5-WF_KOL名单交付前检查_v2.5.md`

默认不再把交付前整理拆成太重的多段式 workflow，而是收敛成一条轻量主流程：

1. 备份主表
2. 统一 Phase 2 格式
3. 做脏值二次检查
4. 输出审计结果

在 `Phase 2` 内，如用户确认进入交付副本准备，则继续：

5. 生成上传副本
6. 按基准 schema 删列
7. 删除 `Part2`
8. 输出 preview、删列清单和上传前摘要

`Phase 3` 只保留“确认后正式上传”。

上传到外部平台不属于本 skill 的默认主流程；本 skill 负责把文件整理到“可交付、可确认”的状态。

## 什么时候用

当用户表达以下意图时使用本 skill：

- “交付前整理这张名单”
- “跑一下 Phase 2/Phase 3 的上传前步骤”
- “按交付口径整理主表并出上传版”
- “检查一下这张 CSV 再生成给客户/飞书上传的副本”
- “只执行 Phase 2”
- “确认后执行 Phase 3”

## 期望输入

最少需要：

- 一张主 CSV

推荐再提供：

- 一个上传 schema 基准 CSV
- 项目名 / 企业名

若用户没有显式给出 schema 基准：

- 优先从同项目内上一版正式 `【KOL】...Influencer_List_Rockbase...csv` 读取表头作为保留列基准

## 默认执行口径

- 默认执行 `Phase 1-2`
- `Phase 3` 必须在用户明确确认后执行
- 用户如果只点名 `Phase 2`，则不生成上传副本、不删上传列
- 用户如果点名 `Phase 3`，默认基于当前主表生成上传副本，不重跑 `Phase 1`
- 若用户要求跳过顺序，只执行某一段，按用户指定的 `Phase` 执行，不强行补跑整条链路

## 默认上传目标

- 若用户未单独指定上传位置，本 skill 的默认上传目标固定为：
  - 飞书 `Friday` 共享文件夹
- 默认上传动作借助：
  - `02 💼 Office/ag-feishu-copilot`
- 因此，当用户说“执行 Phase 3”或“确认上传”时，默认含义是：
  - 将 `Phase 2` 已确认的上传副本，上传到飞书 `Friday` 共享文件夹
- 不要把“上传到哪里”再次回问成开放问题，除非：
  - 用户明确说不上传飞书 `Friday`
  - 或当前环境中确实拿不到飞书上传入口
- 若上传入口不可用，才向用户汇报阻塞点；不要把源文件路径误当成上传目标

## 默认主流程

### Step 1. 备份主表

- 必须先物理备份到 `Agency/list-bak/{YYYY-MM-DD}/`
- 不允许无备份直接改主表

### Step 2. 清洗主表

默认执行：

- `提报时间` 统一为执行当天日期
- `提报人` 统一为 `跃`
- `语言`、`博主国家` 尽量标准化为中文表达
- `粉丝数` 统一为 `K/M`
- `置顶最高播放`、`近期10条均播` 统一为纯数字千分位或 `None`
- 纯数字价格统一为 `$` + 千分位
- 平台与分区重排
- 重复检查

这一阶段默认不删列。

### Step 3. 脏值二次检查

脚本必须自己先做二次检查，而不是把数字清洗全部甩给 LLM。

默认策略：

- 先对清洗前后做字段级对比
- 再优先回看同日 `Agency/list-bak/` 备份
- 必要时再参考 `workbench/` 里的早期过程文件或更早备份，确认量级
- 对可疑数字生成 `dirty_value_audit`
- 只有当备份链条能明确证明量级时，才允许脚本自动修正
- 不能被备份链条直接证实的项，优先由 Friday 结合源值、上下文和历史版本继续判断并闭环修复
- 只有在证据不足、版本冲突或仍然无法稳定判断时，才允许进入人工确认
- 最后只把 Friday 仍然拿不准的残留项汇报给用户

典型可疑项包括：

- 单位丢失后得到异常小数值
- 原值包含 `K/M`，清洗后结果明显不合理
- 价格字段包含文本说明，无法稳定数值化
- 同一字段格式前后差异过大

建议将脏值处理理解为三档：

- `auto-fix`：脚本和备份链条足以直接修正
- `agent-fix`：需要 Friday 结合上下文判断，但仍应默认直接修正
- `manual-review`：只有 Friday 也无法稳定判断时，才汇报给用户

### Step 4. 进入交付副本准备后生成上传副本

只有在用户明确确认进入交付副本准备后，才执行旧的 `Phase 3 / Step 1-4`：

- 复制主表得到上传副本
- 立即重命名成最终交付文件名
- 按基准 schema 保留列
- 按 `X` 平台规则保留或删除 `Sample Content` / `Latest Activity Proof`
- 删除 `Part2`
- 输出 preview summary，供用户确认

### Step 5. 向用户汇报

最少汇报：

- 主表路径
- 上传副本路径
- 最终保留列
- 删除列
- 是否保留 `X` 平台扩展列
- `Part2` 删除情况
- 重复检查结果
- 脏值审计结果
- 仍需人工确认的残留项
- 若已进入 `Phase 3`，还必须明确回报默认上传目标是飞书 `Friday` 共享文件夹

## 红线

不要：

- 在未备份时直接写主表
- 在主表上直接删列
- 让 LLM 直接无约束改数字
- 把本可自行闭环的清洗异常推给用户
- 在用户只要求主表整理时擅自上传

## 脚本

- 主脚本：`scripts/prepare_delivery_package.py`
- 内置规则母版：`S5-WF_KOL名单交付前检查_v2.5.md`

推荐调用方式：

```bash
python3 scripts/prepare_delivery_package.py \
  --mode phase2 \
  --source-csv "/abs/path/source.csv" \
  --schema-baseline-csv "/abs/path/baseline.csv" \
  --project-name "Ticnote"
```

确认后执行 `Phase 3`：

```bash
python3 scripts/prepare_delivery_package.py \
  --mode phase3 \
  --confirm-phase3 \
  --source-csv "/abs/path/source.csv" \
  --schema-baseline-csv "/abs/path/baseline.csv" \
  --project-name "Ticnote"
```

仅做预演：

```bash
python3 scripts/prepare_delivery_package.py \
  --mode phase2 \
  --source-csv "/abs/path/source.csv" \
  --schema-baseline-csv "/abs/path/baseline.csv" \
  --project-name "Ticnote" \
  --dry-run
```

## 产物

默认在主表旁或当天 `workbench/{YYYY-MM-DD}/` 生成：

- 上传副本 CSV
- `delivery_preview_*.md`
- `delivery_preview_*.json`
- `dirty_value_audit_*.json`

## Portability rule

所有引用路径默认相对本 skill 目录可迁移；如果 skill 文件夹被整体移动，内部结构仍应可工作。
