---
description: "[Workflow] S2 Cold 到 Mail1 DM Fill | 目标：在当前 skill 内完成 Greeting Name、Hook 与冻结正文拼接。"
---

# L3-WF_to-S2-DM-fill

> 用途：这一步承接 `L3 -> S2` 之后的触达预填充。
> 它不负责重新找人，也不负责改 `S2` 结构列。
> 它只负责把 `Mail1` 相关字段补齐到可进入 DM / drafts 的状态。

## 一、默认职责

- `Mail1_Greeting_Name`：由 LLM 判断
- `Mail1_Hook`：由 LLM 判断
- `Mail1_Content V1`：使用冻结正文模板拼接
- `Mail1_Subject`：由脚本按显示名生成基础版本，可人工后改

一句话：

**LLM 负责判断变量，脚本负责稳定写表。**

## 二、输入与输出

### 输入

- `workbench/{YYYY-MM-DD}/x_kol_S2_cold_*.csv`
- 或 merge 后的 `workbench/{YYYY-MM-DD}/x_kol_S2_merged_filtered_{YYYY-MM-DD}.csv`

### 输出

- preview manifest：
  - `workbench/{YYYY-MM-DD}/*_dm_fill_manifest_{YYYY-MM-DD}.json`
- 正式写回：
  - 原始 `S2` CSV 本身

## 三、生成规则

### `Mail1_Greeting_Name`

- 真人：优先用最自然的 first name
- 品牌、媒体、组织、频道：补 `Team`
- 个人品牌化 handle：可以直接保留
- 不要把 emoji、职业尾巴、括号说明带进称呼

### `Mail1_Hook`

- 必须 1 句话
- 必须是“为什么找你”的匹配理由
- 只能基于当前表内已有字段判断
- 不得编造“看过你哪条内容”
- 语气要具体、克制、商务

### `语言路由`

- `语言=中文`：必须输出中文 `Mail1_Subject / Mail1_Content V1`
- `语言=英语`：必须输出英文 `Mail1_Subject / Mail1_Content V1`
- `语言=其他语言`：当前统一走英文 DM
- `语言` 字段是 DM 语言的 authoritative source，不能靠模型临场猜
- 不允许出现“语言列是中文，但 DM 正文还是英文”的情况

### `Mail1_Content V1`

- 不由模型自由改写
- 固定使用 skill 内冻结 body
- 只替换 `Greeting Name` 和 `Hook`
- 必须保留真实换行
- 必须先按 `语言` 路由，再选择对应语言模板
- 中文模板要保持商务、自然、低 AI 味，不写夸张营销句
- 英文模板同样保持商务语气，不写模板味过重的夸张表达

## 四、执行模式

### Mode A: `conversation_llm`

- 生成 manifest 给当前对话内 LLM 使用
- 不默认要求外部 API key
- 适合 preview、小批量抽查、人工确认风格

### Mode B: `apply_json`

- 读取准备好的 fills json
- 正式写回 CSV
- 写回前必须自动备份

## 五、脚本入口

### 生成 manifest

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_s2_dm_fill.py \
  --input-csv workbench/2026-04-01/x_kol_S2_merged_filtered_2026-04-01.csv \
  --run-date 2026-04-01 \
  --mode conversation_llm
```

### 应用 fills json

```bash
PYTHONPATH=src python3 src/x_kol_discovery/pipelines/run_s2_dm_fill.py \
  --input-csv workbench/2026-04-01/x_kol_S2_merged_filtered_2026-04-01.csv \
  --run-date 2026-04-01 \
  --mode apply_json \
  --fills-json workbench/2026-04-01/x_kol_S2_merged_dm_fill_rows.json
```

## 六、代码落点

- 核心逻辑：
  - `src/x_kol_discovery/layer3_s2_dm.py`
- pipeline 入口：
  - `src/x_kol_discovery/pipelines/run_s2_dm_fill.py`

## 七、为什么放在当前 skill 内

- 这是 `L3 -> S2` 后的自然后续动作
- 输入字段完全来自当前 skill 产出的 `S2` 表
- 它属于触达前准备，而不是另一个独立业务系统
- 把规则和脚本收口在同一个 skill，审计与续跑都更稳定
