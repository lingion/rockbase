# Cold DM Run

> 用途：当任务是批量补齐 `Mail1_*` 的 X / Twitter DM 文案字段时，使用本工作流。
> 本文档只定义执行流程，不承载正文模板与 variant 细节。
> 文案资产统一放在 `references/cold_dm_copybook.md`。

## 1. Scope

- 适用场景：
  - X / Twitter 首次陌生私信触达
  - 先破冰，再推进到 email / brief / rates
- 不适用场景：
  - Cold Mail
  - Gmail drafts 创建

## 2. Required Inputs

- 源表至少应具备：
  - `账号ID`
  - `账号链接`
  - `频道/作者名称`
  - `账号简介` 或 `账号简介__平台抓取`
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
  - `Mail1_Content V1`
- 若启用 DM 控制字段，应写入当次 run 使用的控制值或说明字段。

## 3. Field Ownership

- 必须由 `LLM` 逐行判断：
  - `Mail1_Greeting_Name`
  - `Mail1_Hook`
- 必须由脚本按 copybook 规则拼装：
  - `Mail1_Content V1`
- 若启用配置化 run，可由配置文件控制：
  - open
  - context bridge
  - CTA block
  - variant route

## 4. Workflow

1. 先物理备份源表。
2. 选择目标行，优先小批量试跑。
3. 由 `LLM` 逐行生成 `Greeting / Hook`。
4. 按 `references/cold_dm_copybook.md` 的 variant 规则组装 DM 正文。
5. 人工抽查：
   - 开头是否自然
   - Hook 是否与账号内容真的匹配
   - CTA 是否过重
   - 正文是否像 DM，而不是像 Email
6. 通过后再全量写回。
7. 若进入手动输入阶段，继续执行本文件的 `Manual Input Run`。

## 5. Execution Rules

- 默认优先使用当前对话模型，不默认要求外部 API key。
- `Greeting` 不允许纯规则硬刷。
- `Hook` 不允许统一句型群发。
- `Mail1_Content V1` 应保留短句、轻 CTA、可读性强的 DM 结构。
- DM 正文不应直接复用 Mail 正文。

## 6. Manual Input Run

### 6.1 Use Case

- 当 S2 cold DM CSV 已经有 `Mail1_Content V1`
- 且任务变成：
  - 继续后面的 `5` 行
  - 在 AdsPower 打开 X profile
  - 进入 DM 窗口
  - 将 `Mail1_Content V1` 粘贴到输入框
  - 若无法 DM，则回写 `备注`

### 6.2 Safety Rules

- 默认行为永远不发送 DM
- 发送必须同时满足：
  - 用户明确要求
  - 执行时显式带 `--send`
- 批量处理时，每个目标应各自打开一个 tab
- 任何 CSV 回写前都必须先创建物理备份

### 6.3 Standard Command

底层 AdsPower driver 当前位于：

```text
${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js
```

单行：

```bash
node "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js" \
  --user-id k19xcq1m \
  --csv "/absolute/path/to/dm-ready.csv" \
  --row 64
```

5 行批量：

```bash
node "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js" \
  --user-id k19xcq1m \
  --csv "/absolute/path/to/dm-ready.csv" \
  --rows 67-71
```

只有用户明确要求发送时才允许：

```bash
node "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-adspower/scripts/x_dm_input.js" \
  --user-id k19xcq1m \
  --csv "/absolute/path/to/dm-ready.csv" \
  --row 64 \
  --send
```

### 6.4 Status Interpretation

- `pasted_not_sent`
  - 成功，正文已在输入框，未发送
- `sent`
  - 仅在显式使用 `--send` 时才允许出现
- `no_dm_button`
  - 该账号不可 DM，应回写 `DM 没有开通`
- `dm_opened_but_no_input_found`
  - 默认按 `DM 没有开通` 处理，除非视觉检查表明只是临时加载问题
- `error`
  - 停止并上报原始错误

### 6.5 Writeback

- 当目标无法接收 DM，需要回写 `备注` 时，使用：
  - `scripts/x/apply_manual_dm_notes.py`
- 标准回写命令：

```bash
python3 ".agent/skills/S2-ag-gmail-bulk-drafts/scripts/x/apply_manual_dm_notes.py" \
  --input "/absolute/path/to/dm-ready.csv" \
  --set @handle="DM 没有开通" \
  --backup-root "Agency/list-bak"
```

### 6.6 Operator Loop

1. 确定下一批 `5` 个 sheet rows。
2. 使用 AdsPower driver 打开对应 tab。
3. 保留所有 `pasted_not_sent` 的 tab，供人工复核。
4. 对无法接收 DM 的目标回写 `备注`。
5. 向用户汇报 handles 与状态。

## 7. Manual DM Notes

- 当任务是“打开 AdsPower profile 并准备输入 DM”时，使用：
  - `scripts/x/open_x_profiles_in_adspower.py`
- 当目标无法接收 DM，需要回写 `备注` 时，使用：
  - `scripts/x/apply_manual_dm_notes.py`

## 8. QC Checklist

- `Greeting` 是否像对人说话，而不是邮件称呼
- `Hook` 是否来自真实资料
- 正文长度是否适合 DM
- CTA 是否过深推进
- 文案是否避免外链、重营销词和明显风控触发词

## 9. References

- 文案资产：
  - `references/cold_dm_copybook.md`
