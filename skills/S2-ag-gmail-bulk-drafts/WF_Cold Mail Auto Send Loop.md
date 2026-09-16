# Cold Mail Auto Send Loop

> 用途：当 `Mail1` 草稿已经准备好，需要进入自动发件循环时使用。
> 本文档只定义“如何按节奏把草稿送出去”，不负责文案生成，也不负责草稿建单。
> 主执行面优先走 Gmail 插件 / Gmail OAuth 通道；本地脚本只作为可复现的批处理 runner。

## 1. Scope

- 适用场景：
  - 已完成 `Mail1` 填充并生成 `draft_jobs.csv`
  - 已完成 `1` 封 + `5` 封 sample 验证
  - 已确认正文、收件人和 subject 无串稿
  - 需要在一段时间内分批把草稿发出
- 不适用场景：
  - 重新写 `Mail1` 文案
  - 重新补 `Mail1_Subject`
  - 重新生成 manifest
  - 未确认前的全量首发

## 2. Trigger

- 只有在以下条件都满足时，才允许进入自动发件循环：
  - 源表 `Mail1发出状态` 已完成草稿回写，或 manifest 中已标记为 `sampled` / `done`
  - sample 已经通过人工抽查
  - `reconcile` 逻辑已经确认没有明显的 draft 缺口
  - 云端 `DRAFT` 已确认无 exact duplicate，或重复已清理完成
  - 用户明确说“直接发”或“继续自动发”
- 如果任一条件不满足，必须先回到 `WF_Cold Mail Run.md`

## 3. Execution Model

### 3.0 核心参数收集

- 每次真正开始发送前，必须先和用户对齐这组核心参数
- 如果用户只给了部分参数，先补齐缺失项，再发送
- 默认提问顺序：
  - 发信账号：`steve / annabel / steveding`
  - 发送来源：`云端草稿箱` 还是 `manifest queue`
  - 本轮模式：`单轮测试` 还是 `多轮循环`
  - 目标发送量：固定值，或区间值
  - 每封间隔：例如 `20-30 秒`
  - 轮间停顿：例如 `2-3 分钟`
  - 是否 live send：`dry-run / live`
- 若用户说：
  - `先测 20 封`
  - `2-3 分钟一轮`
  - `每封 20-30 秒`
  则不能只记成自然语言，必须落成 sender 参数后再执行

### 3.1 节奏

- 默认按“短轮次循环”执行
- 每轮发送 `8-12` 封，目标值默认 `10` 封左右
- 每轮之间等待 `240-360` 秒，默认约 `5` 分钟上下
- 首轮启动前再加一层 `0-120` 秒随机抖动
- 若用户给了更细粒度要求，优先使用：
  - 每封间隔：`per-email-min-seconds / per-email-max-seconds`
  - 每轮停顿：`min-wait-seconds / max-wait-seconds`
- 这些随机值都要保留上下界，不要写死成固定秒数

### 3.1A Heartbeat 模式

- 当用户明确提到：
  - `Codex 定时任务`
  - `heartbeat`
  - `每 X 分钟提醒一次`
  - `提醒后再随机发一轮`
  默认进入 heartbeat 模式，而不是长窗口常驻模式
- heartbeat 模式的职责拆分：
  - Codex automation 负责：按固定 cadence 唤醒当前 thread
  - 本地 sender wrapper 负责：在本轮内再加一层秒级抖动，并随机决定发送数量
- 推荐默认值：
  - cadence：`10 分钟`
  - heartbeat 唤醒后再加：`15-45 秒` 抖动
  - 单轮发送目标：`15` 封左右
  - 数量浮动：`-3 / +5`
  - 每封间隔：默认 `20-30 秒`
- 对应脚本：
  - `scripts/gmail/send_mail1_heartbeat_round.py`
- 这个脚本每次只发一轮，不做跨轮 sleep；跨轮由 Codex heartbeat 本身负责

### 3.2 拉起方式

- 每一轮开始时，都要重新拉起 Gmail 执行上下文
- 不复用上一轮的旧连接、旧 tab、旧缓存选择结果
- 每轮都要重新读取 manifest，按当前最新状态挑选可发草稿
- 如果当前轮没有可发草稿，直接停止，不空转
- heartbeat 模式下也是同样规则：每次 thread 被叫醒后，重新读 manifest，再决定是否发本轮

### 3.3 选择规则

- 只发送 manifest 中状态为 `sampled` / `done` 且 `draft_id` 非空的行
- 发出成功后，将 manifest 行标记为 `sent`
- 同步把源表对应行写回 `Mail1发出状态 = sent`
- 已经 `sent` 的行不再重复发送

## 4. Gmail Surface

- 主执行通道：
  - Gmail plugin
  - Gmail OAuth token 文件
- 关键要求：
  - 每轮都用新的 Gmail session / connector 初始化
  - 不依赖旧窗口、旧页面或旧选择缓存
  - 每轮发件前先检查 Gmail profile 是否可用
  - 如果插件层失败，先停，再回到 manifest 层排查，不要盲目重试

## 5. Canonical Runner

- 本地 canonical runner：
  - `scripts/gmail/send_draft_jittered.py`
- heartbeat 单轮包装：
  - `scripts/gmail/send_mail1_heartbeat_round.py`
- 固定角色分工：
  - `prepare_jobs.py` 负责把源表转成 manifest
  - `sample_send.py` 负责前置样本验证
  - `bulk_send.py` 负责一次性批量创建草稿
  - `send_draft_jittered.py` 负责自动发件循环
  - `send_mail1_heartbeat_round.py` 负责 heartbeat 唤醒后的一次单轮发送
  - `reconcile_drafts.py` 负责对账

## 5.1 Heartbeat 参数映射

当用户用自然语言表达：

- `默认 10 分钟启动一次`
- `提醒后加减十几秒或几十秒`
- `每次 15 左右，浮动 3-5`

统一映射为：

- automation cadence：
  - `FREQ=MINUTELY;INTERVAL=10`
- 本地单轮 sender：
  - `--base-batch-size 15`
  - `--batch-minus 3`
  - `--batch-plus 5`
  - `--jitter-min-seconds 15`
  - `--jitter-max-seconds 45`
  - `--per-email-min-seconds 20`
  - `--per-email-max-seconds 30`

示例：

```bash
python .agent/skills/S2-ag-gmail-bulk-drafts/scripts/gmail/send_mail1_heartbeat_round.py \
  --job workbench/2026-06-23/2026-06-23_airtap_mail1_draft_jobs.csv::workbench/2026-06-23/2026-06-23_airtap_mail1_master_ready.csv \
  --base-batch-size 15 \
  --batch-minus 3 \
  --batch-plus 5 \
  --base-interval-seconds 600 \
  --jitter-min-seconds 15 \
  --jitter-max-seconds 45 \
  --per-email-min-seconds 20 \
  --per-email-max-seconds 30

### 5.2 单轮 live send 推荐入口

- 当用户明确说：
  - `先发 20 封测试`
  - `每封 20-30 秒`
  - `不需要 heartbeat，先跑一轮`
  优先使用：
  - `scripts/gmail/send_mail1_auto_loop.py`
- 推荐形态：

```bash
python .agent/skills/S2-ag-gmail-bulk-drafts/scripts/gmail/send_mail1_auto_loop.py \
  --token-file '${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>' \
  --min-batch-size 20 \
  --max-batch-size 20 \
  --per-email-min-seconds 20 \
  --per-email-max-seconds 30 \
  --min-wait-seconds 120 \
  --max-wait-seconds 180 \
  --single-run \
  --initial-jitter-seconds 0
```

- 解释：
  - `single-run`：只跑一轮
  - `min/max-batch-size` 相同：固定发 `20` 封
  - `per-email-*`：控制每封之间的随机等待
  - `min/max-wait-seconds`：只影响多轮；单轮测试可保留，但不会进入下一轮
```

## 6. Workflow

1. 先确认草稿已经准备好。
2. 先看 `draft_jobs.csv` 的状态分布，确认 `sampled` / `done` 可发。
3. 通过 Gmail plugin / OAuth 拉起第一轮。
4. 每轮发送 `8-12` 封。
5. 每轮结束后写回：
   - manifest 状态
   - 源表 `Mail1发出状态`
6. 等待 `240-360` 秒后进入下一轮。
7. 如果当前轮剩余草稿不足一个 batch，就按剩余数发完。
8. 如果出现明显失败，先停，再做 `reconcile`。
9. 全部发完后，生成对账结果。

### Heartbeat 版顺序

1. 先确认草稿已经准备好。
2. 创建或更新 heartbeat automation。
3. 每次 heartbeat 唤醒 thread 后：
   - 先检查 pause flag / stop condition
   - 再跑 `send_mail1_heartbeat_round.py`
4. wrapper 自己决定：
   - 本轮抖动秒数
   - 本轮实际发送量
5. 每轮发完后写回：
   - manifest `sent`
   - 源表 `Mail1发出状态 = sent`
6. 下次 cadence 到了以后再唤醒下一轮

## 7. Safety / Stop Conditions

- 任何时候都可以通过 pause flag 停止
- 遇到以下情况立即停：
  - Gmail plugin 不可用
  - token 无效或过期
  - manifest 里没有可发草稿
  - 云端 `DRAFT` 与本地 manifest `done` 差值异常
  - 发现 exact duplicate draft 尚未清理
  - 连续失败达到阈值
  - 用户要求暂停
- 未经过 sample 通过，不允许进入这个循环

## 8. Output Contract

- 发件完成后，至少应看到：
  - manifest 中对应行变成 `sent`
  - 源表 `Mail1发出状态 = sent`
  - `reconcile` 结果可对上

## 9. References

- 草稿与发件总流程：
  - `WF_Cold Mail Run.md`
- 草稿 manifest 生成：
  - `scripts/gmail/prepare_jobs.py`
- 样本草稿：
  - `scripts/gmail/sample_send.py`
- 全量草稿：
  - `scripts/gmail/bulk_send.py`
- 自动发件循环：
  - `scripts/gmail/send_draft_jittered.py`
- 对账：
  - `scripts/gmail/reconcile_drafts.py`
