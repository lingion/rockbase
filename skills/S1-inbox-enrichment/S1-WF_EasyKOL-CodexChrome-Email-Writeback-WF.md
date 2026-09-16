---
description: "[Process] EasyKOL CodexChrome Email Writeback WF | 场景：先通过 Codex Chrome Extension bootstrap 建立硬门槛，再执行 DOM 优先、右卡截图兜底的 EasyKOL email writeback。"
---
# 🛰️ [Process] EasyKOL CodexChrome Email Writeback WF

> **本工作流是 Codex 专用路线。它依赖 Codex 内置 Chrome 插件，不是通用浏览器脚本 SOP。**

## Agent Trigger Block

- Required plugin: `[@chrome](plugin://chrome@openai-bundled)`
- Required bootstrap: `.agent/skills/S1-inbox-enrichment/scripts/codex_chrome/s1_codex_chrome_bootstrap.mjs`
- Required runner: `.agent/skills/S1-inbox-enrichment/scripts/codex_chrome/s1_codex_chrome_easykol_writeback.mjs`
- Preview first: `true`
- Preview batch size: `5`
- Write columns only:
  - `联系方式`
  - `联系方式备注`
- Forbidden fallback:
  - 普通浏览器脚本
  - 桌面点击流主方案
  - 未过 bootstrap 的直接写回

## 一、核心定位 (Scope)

本工作流用于：

- 用 Codex Chrome 插件打开目标主页
- 先用 DOM 快扫 EasyKOL 面板邮箱
- DOM 未命中或不稳定时，自动切换到右卡可见截图识别
- 将结果直接写回现有 CSV

本工作流只写两列：

- `联系方式`
- `联系方式备注`

## Single Entrypoint

唯一推荐执行顺序：

1. 先用 `@chrome` 跑 bootstrap
2. 再对 `5` 行执行 `write=false` preview
3. 用户确认后，对同批 `write=true`
4. 再按同一规则继续剩余行

默认写回规则：

- 命中邮箱：`联系方式 = <email>`，`联系方式备注 = EasyKOL获取`
- 明确无邮箱：`联系方式` 保持空白，`联系方式备注 = EasyKOL无法获取`
- 页面错误 / panel 缺失 / 插件异常：保持原行不变，记 `retry`

## Status Semantics

- `hit`
  - 发现有效邮箱
  - 写 `联系方式 = <email>`
  - 写 `联系方式备注 = EasyKOL获取`
- `no_email`
  - 右卡明确可见且无邮箱
  - `联系方式` 保持空白
  - `联系方式备注 = EasyKOL无法获取`
- `retry`
  - 页面错误 / panel 缺失 / 插件异常 / OCR 异常
  - 不写 `EasyKOL无法获取`
  - 只保留 review

## 二、执行入口 (Entrypoint)

后续 agent 遇到本 WF 时，必须先过 `Chrome bootstrap`，再跑 writeback。

### 1. Bootstrap 脚本

- 相对路径：`.agent/skills/S1-inbox-enrichment/scripts/codex_chrome/s1_codex_chrome_bootstrap.mjs`
- 绝对路径：[s1_codex_chrome_bootstrap.mjs](<${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S1-inbox-enrichment/scripts/codex_chrome/s1_codex_chrome_bootstrap.mjs>)

职责：

- 强制检查 `agent.browsers.list()`
- 强制要求出现 `type=extension`
- 打开 `https://example.com/` 做最小成功探针
- 只返回 `ready / blocked`

### 2. Writeback 脚本

- 相对路径：`.agent/skills/S1-inbox-enrichment/scripts/codex_chrome/s1_codex_chrome_easykol_writeback.mjs`
- 绝对路径：[s1_codex_chrome_easykol_writeback.mjs](<${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/.agent/skills/S1-inbox-enrichment/scripts/codex_chrome/s1_codex_chrome_easykol_writeback.mjs>)

职责：

- 读取 CSV
- 先走 DOM 快扫
- 失败后自动切到右卡截图 OCR
- 输出 `hit / no_email / retry`
- 可选正式写回

## 三、硬门槛 (Hard Gate)

以下任一条件不满足，禁止开始 EasyKOL 跑数：

- 没有 `@Chrome` 上下文
- `agent.browsers.list()` 里没有 `type=extension`
- `runCodexChromeBootstrap(...)` 未返回 `ready=true`
- `example.com` 探针未成功
- 未先完成 `write=false` preview

不允许的降级：

- 不允许自动降级成普通 Chrome 打开页面
- 不允许自动降级成桌面点击流作为主方案
- 不允许在 bootstrap 失败时直接进入 writeback

## 四、识别链 (Recognition Chain)

### Phase A. DOM 快扫

先读取 `tab.playwright.domSnapshot()`，只在 EasyKOL 面板切片中判断：

- 完整邮箱 `<YOUR_ACCOUNT_EMAIL>`
- 合法分段邮箱，如 `team` + `@barnettx.com`

DOM 命中则直接写回，不进入截图兜底。

### Phase B. Visible Panel Fallback

若 DOM 未命中，或只得到不稳定线索，则自动切到可见右卡识别：

- 截当前可见区
- 固定裁出右卡 panel 区
- 再固定裁出你确认过的 `邮箱` 输入框
- 对 panel / email crop 做 OCR

这里的**最终裁决面**是右卡的 `邮箱` 输入框。

### Phase C. 结果判定

- `hit`
  - DOM 命中，或右卡 OCR 命中邮箱
  - 写 `联系方式 = <email>` 与 `联系方式备注 = EasyKOL获取`

- `no_email`
  - 右卡明确可见
  - 邮箱框为空占位态或 OCR 明确无邮箱
  - 写 `联系方式备注 = EasyKOL无法获取`

- `retry`
  - panel 未出现
  - OCR 失败
  - 页面错误
  - 插件异常
  - 不写 `EasyKOL无法获取`

### Phase D. 置信分层

- `dom hit`
  - 高置信
  - 默认可直接写回

- `visible no_email`
  - 中高置信
  - 仅在右卡明确可见，且邮箱输入框明确为空占位态时，才允许写 `EasyKOL无法获取`

- `visible hit`
  - 中等置信
  - 默认允许写回，但应优先保留 panel / email crop 与 OCR 文本，便于后续复核

- `retry`
  - 低置信或未完成状态
  - 只能保留 review，不得写成 `EasyKOL无法获取`

## 五、默认执行规则 (Default Behavior)

默认规则如下：

1. 跳过已有 `联系方式` 的行
2. 先过 bootstrap，再跑 writeback
3. EasyKOL 右卡是最终有效来源
4. 允许把右卡中合法分段邮箱重组为完整邮箱
5. 只写 `联系方式 / 联系方式备注`
6. 输出 review / audit 文件

续跑筛选规则：

- 若用户没有指定行号，默认只处理 `联系方式` 为空且 `联系方式备注` 还不是 `EasyKOL获取 / EasyKOL无法获取` 的行
- 已写过 `EasyKOL无法获取` 的行视为已处理，不在续跑时反复打开
- `retry` 行不应被当成 `EasyKOL无法获取`
- 若用户显式指定行号，则按指定行号重跑
- 若上一批发生超时或中断，优先根据最新 review 与主表交叉确认，再决定补跑范围

## 六、标准步骤 (Run Steps)

### Step 1. 选择待处理行

若用户未指定行号，则默认自动筛选：

- `联系方式` 为空
- `账号链接` 非空
- `联系方式备注` 不是 `EasyKOL获取 / EasyKOL无法获取`

默认 preview 仅取前 `5` 行。

### Step 2. 运行 Bootstrap

必须先执行：

```js
await runCodexChromeBootstrap({
  probeUrl: "https://example.com/",
  keepProbeTab: false,
});
```

只有返回 `ready=true`，才进入下一步。

### Step 3. 打开 TikTok 页面

使用通过 bootstrap 确认过的 Chrome extension backend：

1. 新建或接管 tab
2. 打开目标 `账号链接`
3. 等待页面主内容
4. 先给 EasyKOL 异步注入窗口

### Step 4. DOM 快扫

在 EasyKOL 面板文本切片中判断：

- 完整邮箱
- 合法分段邮箱

若命中，直接记为 `hit`。

### Step 5. 自动切换到右卡截图识别

若 DOM 未命中：

1. 截当前可见区
2. 裁 panel 区
3. 裁邮箱输入框
4. 先 OCR 邮箱框
5. 再结合 panel OCR 做辅助判断
6. 若第一次不稳定，再等待一次并重试

右卡判空的强制条件：

1. 右卡 panel 其他结构明确可见
2. 你确认过的 `邮箱` 输入框位置明确为空
3. 输入框表现为空占位态，例如“输入邮箱地址”

只有三者同时成立，才允许记 `EasyKOL无法获取`。

### Step 6. 写回 CSV

若 `write=true`：

- `hit`：写 `联系方式` 与 `联系方式备注 = EasyKOL获取`
- `no_email`：保持 `联系方式` 为空，写 `联系方式备注 = EasyKOL无法获取`
- `retry`：保持原行不变

若 `write=false`：

- 只输出 review，不改原表

### Step 7. 超时与恢复

若单批执行超时、浏览器工具超时、或结果不完整：

1. 不要立刻整批重跑
2. 先查看主表中本批行号是否已有落表结果
3. 再查看最新 `review.json / review.md`
4. 将本批拆成：
   - 已成功落表的行
   - `retry` 行
   - 仍未决的空白行
5. 只补跑 `retry` 与仍未决的空白行

恢复顺序：

- 先主表
- 再最新 review
- 最后才重新打开页面

## 七、输出规范 (Output)

每次运行至少输出：

- 目标表路径
- bootstrap 是否成功
- 处理行号
- DOM 命中数
- visible fallback 命中数
- `no_email` 数
- `retry` 数
- review 文件路径
- 如启用留证，再输出 panel / email crop 路径
- 如本批发生超时，还应额外报告“已落表行 / 待补跑行”

## Fast Locate

如果后续 agent 只想快速定位主链路，优先看这两个点：

1. `Agent Trigger Block`
2. `Single Entrypoint`

这两个块里已经把 `[@chrome](plugin://chrome@openai-bundled)`、bootstrap 和 preview/write 顺序写死了。

## 八、关键判断红线 (Red Lines)

- 不得把 `panel_missing` 直接写成 `EasyKOL无法获取`
- 不得在整页 caption / hashtag / comment 区全局扫 `@` 误判邮箱
- 不得在 bootstrap 失败时硬跑 writeback
- 不得把普通 Chrome 打开页面误认为已经进入 Codex Chrome Extension 控制链

## 九、建议节奏 (Suggested Cadence)

- 先 bootstrap
- 每次 `5` 行一批
- 若接近运行时上限，或同类 profile 明显更慢，可改成 `2 + 3` 或更小批次
- 每处理 `50` 行做一次阶段备份
- 异常批次优先保留 review，再人工复核

## 十、恢复锚点 (Recovery Anchor)

发生任何中断时，默认恢复锚点为：

1. 主表当前状态
2. `workbench/{YYYY-MM-DD}/codex_chrome_easykol_writeback/` 下最新 `review.json`
3. 同目录下的 panel / email evidence

默认不要仅凭对话记忆判断“上一批做到哪里”，要以主表与最新 review 为准。
