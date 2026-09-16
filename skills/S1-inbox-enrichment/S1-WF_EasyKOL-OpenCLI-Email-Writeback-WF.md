---
description: "[Process] EasyKOL OpenCLI Email Writeback WF | 场景：通过 OpenCLI Browser Bridge 接管真实 Chrome，优先读取 EasyKOL 注入面板并回写 email。"
---
# 🛰️ [Process] EasyKOL OpenCLI Email Writeback WF

> **本工作流是 OpenCLI 路线。它依赖 OpenCLI Browser Bridge 扩展连接，不走 Codex Chrome extension backend。**

## Agent Trigger Block

- Required startup skill:
  - `${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/00 📥 Inbox/opencli/.agents/skills/opencli-browser/SKILL.md`
- Required preflight:
  - `opencli doctor`
- Required runtime:
  - `opencli browser <session> ...`
- Recommended session:
  - `yt-email-test`
  - 生产批跑时改成更明确的 session 名
- Preview first:
  - `true`
- Preview batch size:
  - `5`
- Write columns only:
  - `联系方式`
  - `联系方式备注`
- Platforms in scope:
  - `YouTube`
  - `TikTok`
  - `Instagram`
- Forbidden fallback:
  - Codex Chrome backend 失败后自动切回 OpenCLI 且不重做 preflight
  - 普通浏览器手点但不留 review
  - 未经 preview 的直接整批 writeback

## 一、核心定位 (Scope)

本工作流用于：

- 用 OpenCLI 接管真实 Chrome 页面
- 等待 EasyKOL 注入完成后读取右侧邮箱区块
- 将结果写回现有 CSV
- 保留 review 文件，便于续跑

本工作流只写两列：

- `联系方式`
- `联系方式备注`

## Single Entrypoint

唯一推荐执行顺序：

1. 先载入 `opencli-browser` skill
2. 先跑 `opencli doctor`
3. 再对 `5` 行执行 preview
4. 用户确认后，对同批正式写回
5. 再按同一规则继续剩余行

默认写回规则：

- 命中邮箱：`联系方式 = <email>`，`联系方式备注 = EasyKOL获取`
- 明确无邮箱：`联系方式` 保持空白，`联系方式备注 = EasyKOL无法获取`
- 页面错误 / panel 缺失 / 扩展异常：保持原行不变，记 `retry`

## Status Semantics

- `hit`
  - 发现有效邮箱
  - 写 `联系方式 = <email>`
  - 写 `联系方式备注 = EasyKOL获取`
- `no_email`
  - EasyKOL 邮箱区块已经出现
  - 持续等待到上限后仍为空
  - `联系方式` 保持空白
  - `联系方式备注 = EasyKOL无法获取`
- `retry`
  - 页面错误 / panel 缺失 / 扩展异常 / 结果冲突
  - 不写 `EasyKOL无法获取`
  - 只保留 review

## 二、执行入口 (Entrypoint)

后续 agent 遇到本 WF 时，必须先过 `OpenCLI doctor`，再跑 preview/writeback。

### 1. Startup Skill

- 相对路径：`../../../../../../../..${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/00 📥 Inbox/opencli/.agents/skills/opencli-browser/SKILL.md`
- 绝对路径：[opencli-browser/SKILL.md](<${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/00 📥 Inbox/opencli/.agents/skills/opencli-browser/SKILL.md>)

职责：

- 强制按 OpenCLI 的 browser driving 规则工作
- 优先用 `opencli doctor` 验证 Browser Bridge
- 优先用 `tab/session` 生命周期而不是临时浏览器脚本

### 2. Script Placement

OpenCLI 相关脚本统一放：

- 相对路径：`scripts/opencli/`
- 绝对路径：[scripts/opencli](${ROCKBASE_HOME}/我的云端硬盘%20(<YOUR_ACCOUNT_EMAIL>)/Google%20Drive/Obsidian/My%20vault/400%20%F0%9F%94%B4%20Project/%F0%9F%94%B4%20402%20Social%20Agency/%E2%9A%AA%20skills/S1-inbox-enrichment/scripts/opencli)

建议分层：

- `scripts/opencli/s1_opencli_easykol_writeback.py`
  - 批量 writeback 主入口
- `scripts/opencli/internal/session_runtime.py`
  - OpenCLI 会话、open/wait/eval 封装
- `scripts/opencli/internal/extractors/youtube_easykol.py`
  - YouTube EasyKOL 邮箱区块提取
- `scripts/opencli/internal/extractors/tiktok_easykol.py`
  - TikTok EasyKOL 邮箱区块提取
- `scripts/opencli/internal/extractors/instagram_easykol.py`
  - Instagram EasyKOL 邮箱区块提取
- `scripts/opencli/internal/extractors/common.py`
  - 状态归一、邮箱 regex、字段写回辅助

## 三、硬门槛 (Hard Gate)

以下任一条件不满足，禁止开始 EasyKOL 跑数：

- 未先载入 `opencli-browser` skill
- `opencli doctor` 不是 `Extension: connected`
- Browser Bridge profile 未连上
- 未先完成 `5` 行 preview

不允许的降级：

- 不允许跳过 `opencli doctor`
- 不允许把普通 Chrome 打开页面误认为已进入 OpenCLI 控制链
- 不允许未做 preview 就直接整批回写

## 四、识别链 (Recognition Chain)

### Phase A. 打开页面并等待注入

每行进入页面后：

1. `opencli browser <session> open <url>`
2. 开始轮询 EasyKOL 注入状态
3. 默认每 `3` 秒探一次
4. 最长等到 `25` 秒
5. 一旦 `邮箱` 区块出现就提前结束等待

这里的关键不是“固定 sleep 25 秒”，而是：

- **出现即停**
- **未出现才等满**

### Phase B. 读取 EasyKOL 邮箱区块

优先读取 EasyKOL 注入面板中的 `邮箱` section：

- 先找 host：
  - `#efluns-info-anchor`
  - `#efluns-info-sidebar-anchor`
- 再找 `header` 包含 `邮箱` 的 `section`
- 再读 `.section-body`

只在邮箱区块里判断邮箱，禁止去整页正文里全局扫 `@`。

### Phase C. 结果判定

- `hit`
  - `section-body` 中命中有效邮箱
- `no_email`
  - host 已出现
  - `邮箱` section 已出现
  - 一直等到 `25` 秒仍为空
- `retry`
  - host 未出现
  - `邮箱` section 缺失
  - 同一行结果前后冲突
  - 页面异常或 OpenCLI session 漂移

## 五、平台适配原则 (YT + TT + Instagram)

本 WF 不是只给 YouTube 写的，默认要考虑：

- `YouTube`
- `TikTok`
- `Instagram`

适配方式不要写死在一个脚本里，应该按 extractor 拆开：

- `youtube_easykol.py`
  - 当前已验证存在 `efluns-*` shadow host 路线
- `tiktok_easykol.py`
  - 允许不同 host / section 结构
  - 仍保持同样的 `hit/no_email/retry` contract
- `instagram_easykol.py`
  - 允许不同 host / section 结构
  - 仍保持同样的 `hit/no_email/retry` contract

统一 contract：

- 输入：
  - `url`
  - `platform`
  - `wait ceiling`
  - `poll interval`
- 输出：
  - `status`
  - `email`
  - `note`
  - `elapsed_seconds`
  - `host_found`
  - `section_found`
  - `section_text`

## 六、默认执行规则 (Default Behavior)

默认规则如下：

1. 跳过已有 `联系方式` 的行
2. 先跑 doctor，再跑 preview
3. 最长等待 `25` 秒，期间命中即停
4. 只写 `联系方式 / 联系方式备注`
5. 输出 review / audit 文件

续跑筛选规则：

- 若用户没有指定行号，默认只处理 `联系方式` 为空且 `联系方式备注` 还不是 `EasyKOL获取 / EasyKOL无法获取` 的行
- 已写过 `EasyKOL无法获取` 的行视为已处理，不在续跑时反复打开
- `retry` 行不应被当成 `EasyKOL无法获取`
- 若用户显式指定行号，则按指定行号重跑

## 七、标准步骤 (Run Steps)

### Step 1. 选择待处理行

若用户未指定行号，则默认自动筛选：

- `联系方式` 为空
- `账号链接` 非空
- `联系方式备注` 不是 `EasyKOL获取 / EasyKOL无法获取`

默认 preview 仅取前 `5` 行。

### Step 2. 运行 Preflight

必须先执行：

```bash
opencli doctor
```

只有看到：

- `Daemon: running`
- `Extension: connected`
- `Connectivity: connected`

才进入下一步。

### Step 3. 打开页面

```bash
opencli browser <session> open <url>
```

### Step 4. 最长等待 25 秒

默认轮询节奏：

- 每 `3` 秒探一次
- 最多 `25` 秒
- 中间出现邮箱区块就提前结束

### Step 5. 判定并输出 review

- `write=false`
  - 只产出 review
- `write=true`
  - 先备份主表
  - 再回写命中结果

## 八、输出规范 (Output)

每次运行至少输出：

- 目标表路径
- `opencli doctor` 结果
- 处理行号
- `hit` 数
- `no_email` 数
- `retry` 数
- review 文件路径
- 如本批发生冲突，还应额外报告“需人工复核行”

## 九、关键判断红线 (Red Lines)

- 不得把 host 缺失直接写成 `EasyKOL无法获取`
- 不得在整页正文全局扫 `@` 误判邮箱
- 不得未等到 `25` 秒上限就把空白邮箱区块写成 `EasyKOL无法获取`
- 不得并行复用同一个 OpenCLI session 跑多行页面，避免 tab/session 串页

## 十、建议节奏 (Suggested Cadence)

- 先 `doctor`
- 每次 `5` 行一批
- 每行单独使用顺序页面打开，不在同一 session 并发跑多页
- 每处理 `50` 行做一次阶段备份
- 异常批次优先保留 review，再人工复核

## 十一、恢复锚点 (Recovery Anchor)

发生任何中断时，默认恢复锚点为：

1. 主表当前状态
2. `workbench/{YYYY-MM-DD}/` 下最新 OpenCLI review
3. 主表与 review 的交叉差异

默认不要仅凭对话记忆判断“上一批做到哪里”，要以主表与最新 review 为准。
