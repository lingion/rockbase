---
name: ag-sheet-overlay-sync
description: 结构化表格同步技能，支持三类 workflow：1) 本地表对本地表的 overlay 覆盖同步；2) 本地 CSV 到飞书在线 master 的 append-only 增量同步；3) 截图 / 名单到 Feishu master 的 DM 回复状态回填。该技能强制先做映射或 schema 读取，再进入 dry-run / sandbox / 正式写入。
---

# Sheet Overlay Sync

这个 skill 现在包含五条独立 workflow：

1. `WF_overlay_sync.md`
   - 用于本地 source -> 本地 target 的覆盖式同步
2. `WF_feishu_X_DM_append.md`
   - 用于本地 CSV -> 飞书在线 master 的 append-only 增量同步
3. `WF_feishu_X_DM_reply.md`
   - 用于截图 / 名单 -> 飞书在线 master 的 `DM 回复状态` 回填
4. `WF_feishu_Gmail_Mail1_append.md`
   - 用于 Gmail 草稿确认后，把名单 append 到指定飞书 master，并写入 `Mail1邮件发送 = Y`
5. `WF_feishu_Gmail_S3_replyops_writeback.md`
   - 用于从 `S3 ReplyOps` 回写 `Mail1 邮件回复 / 报价标准化 / 报价原文`

必须先判断用户需求属于哪一类，再进入对应脚本目录。

## Quick Entry

先用下面这张路由表判断：

| 用户需求 | 走哪条 WF | 脚本目录 |
| :-- | :-- | :-- |
| 用 A 表覆盖 B 表对应字段 | `WF_overlay_sync.md` | `scripts/overlay_sync/` |
| 用 source 回填 master 的已有匹配行 | `WF_overlay_sync.md` | `scripts/overlay_sync/` |
| 把本地 CSV 合并到飞书在线 master 底部 | `WF_feishu_X_DM_append.md` | `scripts/feishu_master_incremental_sync/` |
| 需要先云端去重，再只追加新行 | `WF_feishu_X_DM_append.md` | `scripts/feishu_master_incremental_sync/` |
| 不能动别人备注 / 高亮 / 颜色 | `WF_feishu_X_DM_append.md` | `scripts/feishu_master_incremental_sync/` |
| 本地 `DM 发送状态` 已标记 `Y / DM 未开通`，云端状态按该列同步 | `WF_feishu_X_DM_append.md` | `scripts/feishu_master_incremental_sync/` |
| Gmail 草稿已经写入，确认后把名单同步到飞书，并把 `Mail1邮件发送` 写成 `Y` | `WF_feishu_Gmail_Mail1_append.md` | `scripts/feishu_master_incremental_sync/` |
| 根据截图名字回填 `DM 回复状态` | `WF_feishu_X_DM_reply.md` | `scripts/feishu_dm_reply_reconcile/` |
| 已经是 `Y` 的 pass，空白才写 `Y` | `WF_feishu_X_DM_reply.md` | `scripts/feishu_dm_reply_reconcile/` |
| 根据 Gmail `S3 ReplyOps` 回写 `Mail1 邮件回复 / 报价标准化 / 报价原文` | `WF_feishu_Gmail_S3_replyops_writeback.md` | `scripts/feishu_master_incremental_sync/` |

一句话判断：

- 如果是“命中旧行并改字段”，走 `overlay`
- 如果是“保留旧行，只往后加新行”，走 `feishu master incremental sync`
- 如果是“Gmail draft 已创建，确认后把 Mail1 名单推进飞书”，走 `WF_feishu_Gmail_Mail1_append.md`
- 如果是“根据截图 / 名单只更新 `DM 回复状态`”，走 `feishu dm reply reconcile`
- 如果是“根据 Gmail `S3 ReplyOps` 回写价格和 Mail1 回复状态”，走 `WF_feishu_Gmail_S3_replyops_writeback.md`

当用户表达类似需求时，使用本技能：

- “用这个新表覆盖 master 里相同行的数据”
- “以 A 表为准，回填/覆盖 B 表的对应字段”
- “先建立映射关系，再确认执行”
- “列顺序和命名可能不一样，帮我同步回去”

## 设计原则

本技能采用“规则文档 + 轻量脚本”的设计，而不是把所有逻辑写死在提示词里，也不是做成完全固定的硬编码流程。

- `SKILL.md` 负责定义同步原则、风险边界、确认流程和默认策略
- 脚本负责执行稳定部分，例如读取 CSV、识别真实表头、标准化字段、做匹配、生成 dry-run 报告、备份和回写
- 不信任列顺序、视觉位置或 Excel 列号，只信任语义字段名和匹配键
- 默认优先保证“可预演、可回滚、可复现”，而不是追求一次性自动化到底
- 对于字段映射、覆盖范围、重复键处理等高风险决策，优先通过规则显式化，而不是隐式猜测
- 对于结构不稳定但模式相近的表格，脚本只固化通用能力，不把项目特例全部写死

换句话说，这个 skill 的目标不是“无脑覆盖”，而是“先建立映射方案，再可控执行”。

## 目录结构

当前建议结构如下：

```text
S5-ag-sheet-overlay-sync/
├── SKILL.md
├── WF_overlay_sync.md
├── WF_feishu_X_DM_append.md
├── WF_feishu_X_DM_reply.md
├── WF_feishu_Gmail_Mail1_append.md
├── WF_feishu_Gmail_S3_replyops_writeback.md
├── agents/
│   └── openai.yaml
└── scripts/
    ├── overlay_sync/
    │   ├── sync_overlay.py
    │   └── overlay_pricing_to_master.py
    └── feishu_master_incremental_sync/
        └── feishu_master_incremental_sync.py
    └── feishu_dm_reply_reconcile/
        └── feishu_mark_dm_replied_from_screenshots.py
```

各文件职责：

- `SKILL.md`
  定义工作流、红线、默认匹配逻辑、覆盖策略和执行要求
- `agents/openai.yaml`
  提供 skill 的显示信息与默认调用描述
- `WF_overlay_sync.md`
  解释本地 overlay 覆盖同步的完整工作流
- `WF_feishu_X_DM_append.md`
  解释飞书在线 master append-only 增量同步的完整工作流
- `WF_feishu_X_DM_reply.md`
  解释截图 / 名单驱动的 `DM 回复状态` 回填工作流
- `WF_feishu_Gmail_Mail1_append.md`
  解释 Gmail 草稿创建完成后，经用户确认，把名单 append 到指定飞书 master，并写入 `Mail1邮件发送 = Y` 的工作流
- `WF_feishu_Gmail_S3_replyops_writeback.md`
  解释从 Gmail `S3 ReplyOps` 回写 `Mail1 邮件回复 / 报价标准化 / 报价原文` 的工作流
- `scripts/overlay_sync/sync_overlay.py`
  提供通用 overlay 同步器，支持 `dry-run`、测试副本写入、差异报告、正式写入和备份
- `scripts/overlay_sync/overlay_pricing_to_master.py`
  提供价格字段 overlay 的专用脚本
- `scripts/feishu_master_incremental_sync/feishu_master_incremental_sync.py`
  提供本地 CSV 到飞书在线 master 的增量同步脚本
- `scripts/feishu_dm_reply_reconcile/feishu_mark_dm_replied_from_screenshots.py`
  提供截图 / 名单到 Feishu master 的 `DM 回复状态` 回填脚本

## Workflow 路由

### Route 1: Overlay Sync

适用：

- A 表覆盖 B 表对应行
- 本地 CSV / segmented master / Excel 导出 CSV
- 匹配命中后选择性回填或覆盖字段

工作流文档：

- `WF_overlay_sync.md`

脚本目录：

- `scripts/overlay_sync/`

### Route 2: Feishu Master Incremental Sync

适用：

- 本地 CSV 合并到飞书在线 master
- 先去重后追加到底部
- 不能修改团队其他成员的备注、高亮、颜色
- 需要输出 DM 发送 / 回复统计
- 如果本地 `DM 发送状态` 已标记 `Y / DM 未开通`，则云端 `DM 发送状态` 按该列同步

工作流文档：

- `WF_feishu_X_DM_append.md`

脚本目录：

- `scripts/feishu_master_incremental_sync/`

### Route 3: Feishu DM Reply Reconcile

适用：

- 截图提取达人名字后回填 `DM 回复状态`
- 只想更新回复状态，不改其他列
- 已有 `Y` 跳过，空白才写 `Y`
- 需要统计今天新增加了多少个 `Y`

工作流文档：

- `WF_feishu_X_DM_reply.md`

脚本目录：

- `scripts/feishu_dm_reply_reconcile/`

### Route 4: Feishu Gmail Mail1 Append

适用：

- Gmail 草稿已创建成功
- 需要在用户确认后把名单写入指定飞书 master
- 目标表使用 `Mail1邮件发送` / `Mail1 邮件回复`
- 需要 append-only，不能动已存在行

工作流文档：

- `WF_feishu_Gmail_Mail1_append.md`

脚本目录：

- `scripts/feishu_master_incremental_sync/`

### Route 5: Feishu S3 ReplyOps Writeback

适用：

- `S3 ReplyOps` 已经判断出有效价格
- 需要把 `Mail1 邮件回复 = Y` 写回飞书
- 需要同时写入 `报价标准化 / 报价原文`
- 对已存在行做 writeback
- 对飞书里还没有的 priced creator 追加到底部，并补标准字段

工作流文档：

- `WF_feishu_Gmail_S3_replyops_writeback.md`

脚本目录：

- `scripts/feishu_master_incremental_sync/`

## Auth Fallback Rule

涉及飞书表格在线读写时，不要再假设只有一种授权路径。

默认探测顺序：

1. 先检查 `lark-cli auth status`
2. 若 `identity = user` 且 `tokenStatus = valid`，记录 user auth 可用
3. 若 user auth 过期、缺 scope、或实际 sheet API 不稳定，则自动回退到 `ag-feishu-copilot` 的 tenant env 凭证

也就是说：

- `lark-cli user auth` 负责“能否直接用用户态”
- `ag-feishu-copilot` 的 `FEISHU_APP_ID / FEISHU_APP_SECRET` 负责稳定 OpenAPI fallback
- 以后 skill 在执行表格读写时，必须把最终采用的 auth route 写进输出

## 使用方法

### 1. Dry Run 预演

默认只读取和计算，不修改任何文件。适合先看映射方案和命中结果。

以下命令中的路径均为占位符，执行时必须替换为当前任务的实际路径。

```bash
python3 '.agent/skills/ag-sheet-overlay-sync/scripts/sync_overlay.py' \
  --source 'SOURCE_CSV' \
  --target 'TARGET_CSV' \
  --source-date 'M月D日'
```

输出重点包括：

- 匹配键顺序
- source / target 行数
- 命中行数
- 实际会变更的行数
- 未命中行数
- 重复匹配风险

执行结束后应看到：

- `Dry run complete. No files were modified.`

### 2. 安全测试模式

如果担心第一次写入会破坏正式表，先使用测试副本模式。该模式会自动复制 target 到测试目录，然后只改副本，不碰原文件。

```bash
python3 '.agent/skills/ag-sheet-overlay-sync/scripts/sync_overlay.py' \
  --source 'SOURCE_CSV' \
  --target 'TARGET_CSV' \
  --source-date 'M月D日' \
  --write-test-copy \
  --diff-report
```

默认测试副本输出到：

- `workbench/{YYYY-MM-DD}/`

文件名必须显式带 `__overlay_test__`，禁止再写入 `target_dir/_overlay_test/` 或 `Agency/list-master/` 下的任何测试目录。

该模式适合检查：

- 行数是否变化
- 分段 marker 是否还在
- 表头是否错位
- 改动是否符合预期

### 3. 正式写入模式

正式写入前，必须先得到用户确认，并且必须先备份 target。

```bash
python3 '.agent/skills/ag-sheet-overlay-sync/scripts/sync_overlay.py' \
  --source 'SOURCE_CSV' \
  --target 'TARGET_CSV' \
  --output 'OUTPUT_CSV' \
  --backup-root 'BACKUP_ROOT' \
  --source-date 'M月D日' \
  --write \
  --diff-report
```

正式写入模式要求：

- 先 dry-run
- 再测试副本
- 再正式执行
- 正式执行前必须创建物理备份

占位符说明：

- `SOURCE_CSV`：本次任务要覆盖进来的源表
- `TARGET_CSV`：本次任务要被覆盖的目标表
- `OUTPUT_CSV`：正式写入输出路径，通常与 `TARGET_CSV` 相同
- `BACKUP_ROOT`：备份根目录，由项目协议决定

## 当前脚本默认行为

`sync_overlay.py` 当前默认策略如下：

- 优先匹配 `账号链接`
- 其次匹配 `账号ID`
- 自动识别 master 中的真实表头行
- 支持处理 `Unnamed:` 假表头和多段 marker
- source 中的 `Part 1` 之类占位行会自动过滤
- `提报时间` 默认只补空，不强制覆盖已有值
- `备注` 默认作为保护列，如果 target 已有内容则不覆盖
- 编码固定为 `utf-8-sig`

## 适用边界

本技能适用于：

- CSV 主表覆盖
- 多段式 master 表
- 列名相近但不完全一致的导出表
- 以 profile URL / 账号 ID 为核心匹配键的达人表格同步

本技能不适合直接处理：

- 完全无稳定匹配键的表
- 需要复杂模糊匹配才能对齐的表
- 用户尚未确认覆盖范围的高风险写入
- 结构未知且没有经过 dry-run 的正式表

## 核心原则

- 默认把 `A 表` 视为 source，把 `B 表` 视为 target
- 任何写入前，必须先输出映射方案，不允许直接修改
- 映射方案未获确认前，只做读取、解析、统计和 dry-run
- 结构化表格只允许通过脚本修改，不手工改文本
- 写入前必须做物理备份，保留可回滚副本
- 不信任列顺序、Excel 列号或视觉位置，只按语义字段名和匹配键处理

## 默认流程

### 第 1 步：读取并识别表结构

先判断 source 和 target 是否为以下类型：

- 标准单表头 CSV
- 多段表头 CSV，例如 `----- T0 -----`、`----- TIER 1 -----`
- Excel 导出 CSV，存在 `Unnamed:` 假表头
- 含空行、重复表头、分层 section marker 的主表

如果表头不是第 1 行，不要直接按默认 CSV 表头读入。先恢复真实字段名，再进入映射阶段。

### 第 2 步：建立映射方案

必须先给用户一个明确方案，至少包含：

- source 和 target 的字段列表摘要
- 公共字段映射
- source 独有字段
- target 独有字段
- 建议主匹配键及优先级
- 预计命中多少行
- 重复键、空键、歧义键的处理方式
- 哪些字段会覆盖，哪些字段会保留 target 原值

如果存在明显语义映射，也要显式说明，例如：

- `平台博主 -> 频道名称`
- `账号链接 -> 账号链接`
- `匹配核心理由 -> 不写入或新增列后写入`

### 第 3 步：等待确认

在用户明确确认之前，不执行任何写入。

确认语义包括但不限于：

- “可以执行”
- “按这个方案去操作”
- “就这么覆盖”

如果用户只确认部分字段或部分规则，按确认后的范围收缩执行，不擅自扩大。

### 第 4 步：执行前备份

开始写入前必须：

- 创建按日期归档的备份目录
- 将 target 原文件物理复制到备份目录
- 备份名附带时间戳

如果当前项目已有既定备份协议，优先遵守项目协议。

### 第 5 步：脚本化覆盖

推荐使用 `pandas` 或 `csv` 脚本执行覆盖。写入脚本应满足：

- 文件路径固定且明确
- 编码保持 `utf-8-sig`
- 不破坏原有 section marker、分段结构和空行布局
- 按匹配键命中 target 行
- 仅覆盖用户确认的字段
- target 独有字段默认保留原值
- 能处理 source 与 target 同一实体在格式上的轻微差异

优先匹配顺序建议：

1. 标准化后的 profile URL / `账号链接`
2. 标准化后的 `账号ID + 平台`
3. `名称 + 平台` 作为兜底，不作为首选

标准化通常包括：

- 去掉 URL query string
- 去掉末尾 `/`
- 统一域名和大小写
- `账号ID` 去掉开头 `@`
- 平台名统一到同一枚举值

### 第 6 步：写后校验

执行后至少校验：

- 更新命中行数
- 实际变更行数
- 未命中行数
- 是否存在 target 重复匹配
- 抽查 2 到 5 条关键记录

如果二次重跑结果为 0 变更，应在汇报中说明结果已稳定。

## 覆盖策略默认值

除非用户另有说明，默认采用以下策略：

- source 公共字段覆盖 target 对应字段
- target 独有分析列、标签列、派生列保留不动
- source 独有字段先列入方案，不默认新增到 target
- 若 target 中同一匹配键出现多行，默认在方案中先提示；执行时只有在规则明确后才批量同步

## 输出格式

### 方案阶段

输出应包含：

- 匹配键方案
- 字段映射表
- 覆盖字段范围
- 预计命中和风险点
- 明确一句“暂未修改任何文件”

### 执行阶段

输出应包含：

- 备份路径
- 执行脚本路径
- 命中行数与更新行数
- 抽查结果
- 是否还有残留风险

## 红线

禁止：

- 在未确认前直接修改 target
- 手工编辑 CSV 正文
- 因为列名略有不同就主观猜测写入
- 把名称模糊相似当作唯一匹配依据
- 未备份先写文件
- 覆盖 target 中用户未授权覆盖的专属字段
