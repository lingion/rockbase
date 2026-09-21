---
name: ag-gmail-bulk-drafts
description: 当用户要求批量创建 Gmail 草稿、从表格生成邮件、批量补发、续传、去重或对账时使用。强制走 Rockbase 已验证的 Gmail OAuth 路径，不猜链路，不走历史残留方案。
---

# Gmail Bulk Drafts

## Gmail Sending: Single Correct Path

对于当前 Rockbase 环境中的所有 Gmail 发信任务，这就是唯一正确路径。

适用范围：

- 新建普通 Gmail 草稿
- 批量上传 Gmail 草稿
- 回复已有 Gmail thread
- 创建 `Mail2` / `Mail3` reply drafts
- 自动发件循环（已完成草稿后按随机批次送出）

固定规则：

1. 不要先走 `gcloud ADC`
2. 不要先走 `gws`
3. 所有 Gmail 发信都使用 Gmail OAuth token 文件
4. 普通草稿与 reply 草稿共用同一套 token
5. reply draft 额外必须带：
   - `threadId`
   - `In-Reply-To`
   - `References`

## Runtime Guardrails

这轮 Airtap / Allyhub 邮件池已经验证出的硬规则如下：

1. Gmail draft create 默认禁用代理继承
2. 若环境里存在：
   - `HTTP_PROXY`
   - `HTTPS_PROXY`
   - `ALL_PROXY`
   不允许直接继承到 Gmail draft create 请求
3. Gmail 批量建草稿默认优先走“直连 + curl + HTTP/1.1”链路
4. 若出现以下症状：
   - `POST /drafts` 卡住
   - TLS handshake hang
   - `urllib` / `httplib2` 长时间无响应
   先判定为代理 / 旧 HTTP 栈问题，不要继续盲重试
5. 大批量续写草稿前，必须先比较：
   - 本地 manifest `done`
   - 云端 Gmail `DRAFT` label count
6. 若两者差值 `<= 1`，可视为可接受漂移
7. 若差值 `> 1`，必须先做：
   - `reconcile`
   - 必要时 `dedupe`
   - 必要时云端 snapshot 抽查
   然后才允许继续 bulk draft run

## X Manual DM: Single Correct Path

对于当前 Rockbase 环境中的所有 X / Twitter 手动 DM 辅助任务，这就是唯一正确路径。

适用范围：

- 打开下一批 `5` 个 X profile
- 在正确的浏览器身份里手动发 DM
- 按 CSV 顺序输出 matching DM copy in-chat

固定规则：

1. 不要把 `open https://x.com/...` 当成“在 AdsPower 打开”
2. 默认先检查 AdsPower local API：`http://127.0.0.1:50325`
3. 默认 profile：`k19xcq1m`
4. 正确顺序必须是：
   - `browser/local-active`
   - 若未激活则 `browser/start?user_id=k19xcq1m`
   - 读取 `debug_port`
   - 用 Playwright `connect_over_cdp` 在该 profile 内开 tab
5. 打开顺序和 in-chat 输出顺序必须一致
6. 手动反馈结果必须即时写回 `备注`

固定资产：

- X DM 输入工作流：
  `WF_Cold DM Run.md`
- 手动 DM 打开脚本：
  `scripts/x/open_x_profiles_in_adspower.py`
- 手动结果回写脚本：
  `scripts/x/apply_manual_dm_notes.py`
- AdsPower DM 输入底层脚本：
  `${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js`

固定资产：

- token:
  `${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/02 💼 Office/ag-Google-Suite/auth/<YOUR_ACCOUNT_EMAIL>`
- 普通草稿脚本:
  `scripts/gmail/sample_send.py` / `scripts/gmail/bulk_send.py`
- 自动发件循环脚本:
  `scripts/gmail/send_mail1_auto_loop.py`
  `scripts/gmail/send_draft_jittered.py`
  `scripts/gmail/send_mail1_heartbeat_round.py`
- reply 草稿脚本:
  `🔘 Skills/ag-gmail-reply-ops/scripts/create_reply_drafts_with_token.py`

正常 draft run 默认只依赖 token 文件。
只有 token 失效且必须重授权时，才进入 client secret fallback。

固定执行顺序：

1. 先验证 1 封
2. 再验证 5 封 sample
3. 用户确认
4. 再跑全量

## Send Operator Contract

当用户说：

- `继续发`
- `今天发 200`
- `先测 20 封`
- `按 10 分钟 heartbeat 发`

不要直接开跑，先收集核心参数。

固定参数清单：

1. 发信账号
2. 发送来源：`云端草稿箱` / `manifest queue`
3. 本轮模式：`single-run` / `loop` / `heartbeat`
4. 目标发送量：固定值或区间
5. 每封间隔秒数区间
6. 每轮之间停顿区间
7. `dry-run` 还是 `live`

若用户未明确说明，先问最少必要缺口，不要自己脑补。

## 本地验证

- 修改草稿准备、收件人清洗或 Mail1 一致性逻辑后，先运行：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .agent/skills/S2-ag-gmail-bulk-drafts/tests -p 'test_*.py'`。
- 该测试只检查内容门槛；不读取 OAuth token，不创建草稿，不发送邮件。

## Architecture Tree

```text
ag-gmail-bulk-drafts/
├── SKILL.md
├── WF_Cold Mail Run.md
├── WF_Cold Mail Auto Send Loop.md
├── WF_Cold DM Run.md
├── references/
│   ├── bulk_draft_workflow.md
│   ├── cold_mail_copybook.md
│   ├── cold_dm_copybook.md
│   ├── cold_mail_workflow_config.json
│   ├── job_manifest_template.md
│   └── task_plan_template.md
└── scripts/
    ├── gmail/
    │   ├── fill_mail1_with_codex.py
    │   ├── prepare_jobs.py
    │   ├── sample_send.py
    │   ├── bulk_send.py
    │   ├── reconcile_drafts.py
    │   └── dedupe_drafts.py
    ├── x/
    │   ├── open_x_profiles_in_adspower.py
    │   └── apply_manual_dm_notes.py
    ├── shared/
    │   └── common.py
    └── legacy/
        ├── fill_x_dm_llm.py
        ├── fill_x_dm_with_codex.py
        └── apply_x_dm_results.py
```

## Intent Map

| 用户场景 | 入口 | 说明 |
| :--- | :--- | :--- |
| 先跑 Cold Mail 内容流程 | `WF_Cold Mail Run.md` | 定义 Mail1 字段生成流程与 QC |
| 进入 Cold Mail 自动发件循环 | `WF_Cold Mail Auto Send Loop.md` | 用 Gmail plugin / OAuth 按随机批次把草稿发出 |
| 先跑 Cold DM 内容流程 | `WF_Cold DM Run.md` | 定义 X / DM 文案生成流程与 QC |
| 查看 Cold Mail 文案资产 | `references/cold_mail_copybook.md` | 管理模板、variant、subject、固定语气 |
| 查看 Cold DM 文案资产 | `references/cold_dm_copybook.md` | 管理模板、variant、CTA、固定语气 |
| 生成 Mail1 字段 | `scripts/gmail/fill_mail1_with_codex.py` | 用 OpenAI-compatible LLM 逐批生成 Greeting / Hook / Variant / Reason，并拼装正文；文件名保留以兼容旧入口 |
| 跑 manifest 和草稿 | `WF_Cold Mail Run.md` | 在 Mail run 内继续执行 draft、sample、bulk、回写 |
| 从表生成 manifest | `scripts/gmail/prepare_jobs.py` | 先建标准任务清单 |
| 先做样本草稿 | `scripts/gmail/sample_send.py` | 默认先 1 封，再 5 封 |
| 跑全量草稿 | `scripts/gmail/bulk_send.py` | 只基于 manifest 执行 |
| 自动发件循环 | `scripts/gmail/send_draft_jittered.py` | 随机批次 + 随机等待的发件窗口 |
| 自动发件循环（推荐包装） | `scripts/gmail/send_mail1_auto_loop.py` | 固定默认批次/等待参数的入口 |
| Heartbeat 单轮发送 | `scripts/gmail/send_mail1_heartbeat_round.py` | 每次服务器调度唤醒只发一轮，批量和抖动都按基准值随机 |
| 对账 | `scripts/gmail/reconcile_drafts.py` | 检查 missing / duplicate / unexpected，默认优先 `to-subject-bodyhash` |
| 清重复草稿 | `scripts/gmail/dedupe_drafts.py` | 只删对账报告确认的重复项 |
| 打开 X 手动 DM 批次 | `scripts/x/open_x_profiles_in_adspower.py` | 通过 AdsPower local API + CDP 打开指定 rows |
| 填入 X DM 输入框 | `WF_Cold DM Run.md` | 在 DM run 内继续执行 AdsPower 打开、粘贴与备注回写 |
| 回写手动 DM 结果 | `scripts/x/apply_manual_dm_notes.py` | 只更新 `备注`，并先物理备份 |

## Canonical Names

默认只认这组入口：

- `WF_Cold Mail Run.md`
- `WF_Cold Mail Auto Send Loop.md`
- `WF_Cold DM Run.md`

- `scripts/gmail/fill_mail1_with_codex.py`
- `scripts/gmail/prepare_jobs.py`
- `scripts/gmail/sample_send.py`
- `scripts/gmail/bulk_send.py`
- `scripts/gmail/send_mail1_auto_loop.py`
- `scripts/gmail/send_draft_jittered.py`
- `scripts/gmail/send_mail1_heartbeat_round.py`
- `scripts/gmail/reconcile_drafts.py`
- `scripts/gmail/dedupe_drafts.py`
- `scripts/x/open_x_profiles_in_adspower.py`
- `scripts/x/apply_manual_dm_notes.py`

说明：

- 历史文档中若出现 `S2-WF_email_content_fill_template.md`，视为旧名称映射，当前统一收口到 `WF_Cold Mail Run.md`
- 当上游 skill（如 YouTube `S1 -> S2`）在 `Mail1 fill` 阶段做 handoff 时，默认目标也应使用 `WF_Cold Mail Run.md`

标准中间产物：

- `draft_jobs.jsonl`
- `draft_jobs.csv`
- `task_plan.md`

正式落点：

- 所有 manifest 必须生成在当天 `workbench/{YYYY-MM-DD}/`
- 禁止写回 `list-master/` 或 skill 根目录

不要再造 `v2`、`final`、`latest` 这类并行入口。

## Sending Defaults

默认建议：

- 单轮人工测试：
  - `single-run`
  - 固定 batch size
  - `per-email-min-seconds` / `per-email-max-seconds` 显式设置
- heartbeat 定时发送：
  - cadence 由服务器 cron/systemd 或其他部署编排控制
  - sender 只负责单轮
  - 秒级随机由 `send_mail1_heartbeat_round.py` 传给 `send_draft_jittered.py`

重要：

- `send_mail1_auto_loop.py` 和 `send_draft_jittered.py` 现在都支持 `--per-email-min-seconds` / `--per-email-max-seconds`
- 轮间停顿和每封间隔是两套参数，不能混用

## X Manual DM SOP

当用户要求“继续后面的 5 个”“在 AdsPower 打开”“把 DM 发到窗口里”时，默认按下面顺序执行：

1. 从主表按 sheet row 取连续 `5` 行，或取用户指定 rows
2. 读取：
   - `账号ID`
   - `频道/作者名称`
   - `账号链接`
   - `Mail1_Content V1`
   - `备注`
3. 优先读取 `WF_Cold DM Run.md`
4. 用 AdsPower DM 输入脚本把每个目标打开为独立 tab，并把 `Mail1_Content V1` 粘贴进 DM 输入框
5. 默认不发送，等待人工确认
6. 若脚本或用户反馈：
   - `DM未开放`
   - `DM 没有开通`
   - `no_dm_button`
   - `dm_opened_but_no_input_found`
   - `This account is temporarily restricted`
   - 其他明确可落表结论
   则先物理备份，再用 `scripts/x/apply_manual_dm_notes.py` 回写 `备注`

执行原则：

- 默认浏览器不算完成
- AdsPower profile 内成功打开才算完成
- 如果 localhost / CDP 被执行环境拦住，应尽快切到可访问 localhost 的执行方式，不要继续用错误路径重试

## PART2 Dedup

- `PART2` 按联系人主体发，不按频道逐行发
- 默认按 `联系方式` 去重；同邮箱视为同一主体
- 同组已有 `sent`：其他行标 `skip_same_contact`
- 同组全空白：只留一行继续待发，其余标 `skip_same_contact`
- `sent` 只表示真实发出

## Source Status

- 源表 `Mail1发出状态` 为空：待处理，可进候选池
- `skip_same_contact`：同主体去重，不进 manifest
- `drafted`：Gmail 草稿已创建完成
- `sent`：邮件已真正发出

不要把 `drafted` 和 `sent` 混用。

## Draft Eligibility

哪些行进入 Gmail 草稿箱，必须先在源表里判定，不靠临场猜。

默认入池规则：

- `Mail1发出状态` 为空
- `联系方式` 非空
- `Mail1_Greeting_Name` 非空
- `Mail1_Subject` 非空
- `Mail1_Content V1` 非空
- 若源表存在 `manual_clean_decision`，其值必须不是 `drop`
- 若源表存在 `email_qc_flag`，其值必须不是 `dirty / invalid / suspect`

默认排除规则：

- `Mail1发出状态 = sent`
- `Mail1发出状态 = drafted`
- `Mail1发出状态 = skip_same_contact`
- `联系方式` 为空
- `Subject / Body / Greeting` 任一缺失
- `manual_clean_decision = drop`
- `email_qc_flag in {dirty, invalid, suspect}`

一句话：

- **只有“状态为空且 Mail1 三件套完整”的行，才允许进入 draft manifest。**

## Bulk Draft Continuation

当用户说“继续后面的 300 / 500 / 全部写完”时，默认按下面顺序执行：

1. 先读 manifest 状态分布
2. 先检查下一批候选：
   - 与 `done / sent` 邮箱不能重叠
   - 候选批次内部邮箱不能重复
3. 若云端已有大量草稿：
   - 先比较本地 `done` 与云端 `DRAFT`
   - 必要时跑 `reconcile`
4. 批量创建成功后：
   - manifest 写 `done + draft_id`
   - 源表写 `Mail1发出状态 = drafted`
5. 若用户怀疑重复，或 bulk run 发生中断：
   - 先扫云端草稿
   - 先按 `to + subject + body_hash` 找 exact duplicate
   - exact duplicate 每组只保留 `1` 封
6. dedupe 完成后，再回读云端 `DRAFT` label count

不要把“继续 bulk draft run”和“直接进入发送 loop”混成一个动作。

## Recipient Cleaning

- `联系方式` 在进入 manifest 前必须先做邮箱清洗
- 若脏值里能提取出合法邮箱，则用清洗后的邮箱入 manifest
- 若清洗后仍不是合法邮箱，则该行排除，不进 manifest
- 对明显 telemetry / asset-style junk email 直接放弃，不进 manifest

执行定位：

- `SKILL.md` 负责定义“哪些行可以进草稿箱”
- `WF_Cold Mail Run.md` 负责定义“Mail1 怎么跑”
- `references/cold_mail_copybook.md` 负责定义“Mail1 文案怎么写”
- `references/cold_mail_workflow_config.json` 负责定义“Mail1 机器可执行配置怎么拼”

## Execution SOP

1. 先读本文件
2. 再读 `references/bulk_draft_workflow.md`
3. 若邮件文案规则未定，先读 `WF_Cold Mail Run.md`，再读 `references/cold_mail_copybook.md`
4. 若任务边界不清，先基于 `references/task_plan_template.md` 产出计划
5. 用 `scripts/gmail/prepare_jobs.py` 生成 manifest，且必须写入当天的 `workbench/{YYYY-MM-DD}/`
6. manifest 生成后，先向用户汇报“今天待发总数”
7. 先跑 `1` 封，再跑 `5` 封 sample
8. 用户确认后，再跑 `scripts/gmail/bulk_send.py`
9. draft 创建成功后，把源表对应行回写为 `drafted`
10. 结束后必须 `reconcile`

## Manifest Minimum Fields

每条任务至少包含：

- `row_id`
- `to`
- `subject`
- `body`
- `body_hash`
- `status`
- `draft_id`
- `error`
- `source_status`
- `source_ref`

幂等键默认：

- `to + subject`

更严格时升级为：

- `to + subject + body_hash`

## Self-Healing

- 任务中断：只基于 manifest 续传，不重跑全量
- 出现重复：先 `reconcile`，再 `dedupe`
- 不对账前，不要凭 Gmail 草稿总数做判断
