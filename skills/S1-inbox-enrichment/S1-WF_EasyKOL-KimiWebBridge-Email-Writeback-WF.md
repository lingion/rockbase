---
description: "[Process] EasyKOL KimiWebBridge Email Writeback WF | 场景：通过 Kimi WebBridge 接管真实 Chrome，优先读取 EasyKOL 注入面板并回写 email。"
---
# 🛰️ [Process] EasyKOL KimiWebBridge Email Writeback WF

> **本工作流是 Kimi WebBridge 路线。它依赖本机 `kimi-webbridge` daemon 与浏览器扩展，不走 Codex Chrome backend，也不走 OpenCLI Browser Bridge。**

## Agent Trigger Block

- Required startup skill: `.agent/skills/S1-inbox-enrichment/S1-WF_EasyKOL-KimiWebBridge-Email-Writeback-WF.md`
- Required preflight: `~/.kimi-webbridge/bin/kimi-webbridge status`
- Required runtime: `http://127.0.0.1:10086` Kimi WebBridge daemon
- Recommended session: `tt-email-writeback`
- Preview first: `true`
- Preview batch size: `5`
- Write columns only:
  - `联系方式`
  - `联系方式备注`
- Platforms in scope:
  - `TikTok`
  - `Instagram`
  - `YouTube`
- Forbidden fallback:
  - Codex Chrome backend 失败后自动切回 Kimi WebBridge 且不重做 preflight
  - OpenCLI Browser Bridge 作为主方案
  - 普通浏览器手点但不留 review
  - 未经 preview 的直接整批回写

## 一、核心定位 (Scope)

本工作流用于：

- 用 Kimi WebBridge 接管真实 Chrome 页面
- 等待 EasyKOL 注入完成后读取右侧邮箱区块
- 将结果写回现有 CSV
- 保留 review 文件，便于续跑

本工作流只写两列：

- `联系方式`
- `联系方式备注`

## Single Entrypoint

唯一推荐执行顺序：

1. 先跑 `kimi-webbridge status`
2. 再对 `5` 行执行 preview
3. 用户确认后，对同批正式写回
4. 再按同一规则继续剩余行

默认写回规则：

- 命中邮箱：`联系方式 = <email>`，`联系方式备注 = 来源: KimiWebBridge`
- 明确无邮箱：`联系方式` 保持空白，`联系方式备注 = 来源: KimiWebBridge 无邮箱`
- 页面错误 / panel 缺失 / 扩展异常：保持原行不变，记 `retry`

## Status Semantics

- `hit`
  - 发现有效邮箱
  - 写 `联系方式 = <email>`
  - 写 `联系方式备注 = 来源: KimiWebBridge`
- `no_email`
  - 右卡明确可见且无邮箱
  - `联系方式` 保持空白
  - `联系方式备注 = 来源: KimiWebBridge 无邮箱`
- `retry`
  - 页面错误 / panel 缺失 / 扩展异常 / 结果冲突
  - 不写 `无邮箱`
  - 只保留 review

## 二、执行入口 (Entrypoint)

后续 agent 遇到本 WF 时，必须先过 `kimi-webbridge status`，再跑 preview/writeback。

### 1. Preflight

必须先执行：

```bash
~/.kimi-webbridge/bin/kimi-webbridge status
```

只有看到：

- `running: true`
- `extension_connected: true`

才进入下一步。

### 2. Browser Runtime

- 先用 `navigate` 打开目标页面，首次使用 `newTab:true`
- 若已有目标标签页，优先用 `find_tab` 接管
- 统一使用同一个 session 名，避免会话漂移
- 右侧 EasyKOL 面板优先通过 `snapshot` 读取

## 三、硬门槛 (Hard Gate)

以下任一条件不满足，禁止开始 EasyKOL 跑数：

- `kimi-webbridge status` 不是健康状态
- 扩展未连接
- 页面未能打开
- 未先完成 `5` 行 preview

不允许的降级：

- 不允许自动降级成普通 Chrome 打开页面
- 不允许自动降级成 OpenCLI 路线作为主方案
- 不允许在 preflight 失败时直接进入 writeback

## 四、识别链 (Recognition Chain)

### Phase A. 页面打开与等待

每行进入页面后：

1. 打开目标 `账号链接`
2. 等待页面主内容稳定
3. 让 EasyKOL 异步注入完成
4. 先读 `snapshot`，再读右侧面板文本
5. 如果页面上出现 `更新` 按钮或 `LinkScan` 区域，优先把这两个区域当成邮箱候选源

### Phase B. DOM / Snapshot 快扫

先读取页面树和可见文本，只在 EasyKOL 面板切片中判断：

- 完整邮箱 `<YOUR_ACCOUNT_EMAIL>`
- 合法分段邮箱，如 `team` + `@domain.com`
- 拆分显示邮箱，如 `press @duolingo.com`、`team @ klymandco.com`
- 右卡 `LinkScan` 行里直接出现的邮箱
- `邮箱` 区块里的完整邮箱
- 右卡顶部账号摘要区里直接出现的邮箱

命中则直接写回，不进入更深一步的人工分支。

### Phase C. Visible Panel Fallback

若 snapshot 未命中，或只得到不稳定线索，则继续检查可见右卡：

- 读取右卡面板内 `邮箱` 区块
- 再判断邮箱输入区是否为空
- 若出现 `查找邮箱` 按钮，优先点击一次再复读
- 若出现 `更新` 按钮，优先点击一次再复读
- 若 `LinkScan` 或账号摘要区已出现邮箱，直接记为 `hit`
- 若右卡有邮箱候选但格式被拆开，允许重组
- 若明显出现邮箱文本，记为 `hit`
- 若右卡明确可见但为空，记为 `no_email`
- 若右卡未出现或页面异常，记为 `retry`

### Phase D. 结果判定

- `hit`
  - DOM / snapshot / 右卡文本命中邮箱
  - 写 `联系方式 = <email>` 与 `联系方式备注 = 来源: KimiWebBridge`

- `no_email`
  - 右卡明确可见
  - 邮箱区块为空或明确无邮箱
  - 写 `联系方式备注 = 来源: KimiWebBridge 无邮箱`

- `retry`
  - panel 未出现
  - 页面错误
  - 扩展异常
  - 会话漂移
  - 不写成 `无邮箱`

### Phase E. 二次确认

当第一轮 snapshot 没命中，但你肉眼看到页面里可能有邮箱时：

1. 等待 8 到 12 秒再 snapshot 一次
2. 如果存在 `更新` 按钮，可先点一次再读
3. 仍未命中时，才允许记 `no_email`

这条是为 TikTok 右卡晚到注入和 `LinkScan` 行延迟渲染准备的。

## 五、默认执行规则 (Default Behavior)

默认规则如下：

1. 跳过已有 `联系方式` 的行
2. 先跑 preflight，再跑 preview
3. 只写 `联系方式 / 联系方式备注`
4. 输出 review / audit 文件

续跑筛选规则：

- 若用户没有指定行号，默认只处理 `联系方式` 为空且 `联系方式备注` 还不是 `来源: KimiWebBridge / 来源: KimiWebBridge 无邮箱` 的行
- 已写过 `来源: KimiWebBridge 无邮箱` 的行视为已处理，不在续跑时反复打开
- `retry` 行不应被当成 `no_email`
- 若用户显式指定行号，则按指定行号重跑

## 六、标准步骤 (Run Steps)

### Step 1. 选择待处理行

若用户未指定行号，则默认自动筛选：

- `联系方式` 为空
- `账号链接` 非空
- `联系方式备注` 不是 `来源: KimiWebBridge / 来源: KimiWebBridge 无邮箱`

默认 preview 仅取前 `5` 行。

### Step 2. 运行 Preflight

必须先执行：

```bash
~/.kimi-webbridge/bin/kimi-webbridge status
```

只有返回健康状态才进入下一步。

### Step 3. 打开页面

```json
{"action":"navigate","args":{"url":"<account_url>","newTab":true},"session":"tt-email-writeback"}
```

### Step 4. 读取页面

优先执行：

```json
{"action":"snapshot","args":{},"session":"tt-email-writeback"}
```

若需要更强判断，再用：

- `click`
- `evaluate`
- `screenshot`

`evaluate` 只用于读取页面中已经渲染出来的文本，不再单独依赖 `document.body.innerText` 粗扫；应优先从 `snapshot` 和右卡面板节点里找邮箱。

### Step 5. 写回结果

命中邮箱则写：

- `联系方式 = <email>`
- `联系方式备注 = 来源: KimiWebBridge`

未命中且确认空邮箱则写：

- `联系方式 =`
- `联系方式备注 = 来源: KimiWebBridge 无邮箱`

### Step 6. 继续下一批

完成 preview 后：

1. 先确认结果格式
2. 再继续下一批 5 或 10 条
3. 全程保留 review / audit

## 七、已知失误修正

如果出现“你肉眼能看到邮箱，但脚本抓不到”的情况，优先按下面顺序修正，不要直接判 `no_email`：

1. 先检查是否是 `LinkScan` 或右卡摘要区里的邮箱
2. 再检查是否需要二次 `snapshot`
3. 再检查是否是邮箱被拆成 `name` + `@domain`
4. 再检查是否是 `查找邮箱` 按钮未点开
5. 最后才允许 `no_email`
