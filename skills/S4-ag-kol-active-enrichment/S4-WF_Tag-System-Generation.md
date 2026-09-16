# S4 WF Tag System Generation

## 目标

把 `账号类目标签` 和后续 `tag system` 的生成统一收口到 `S4` 阶段完成。

适用字段：

- `账号类目标签`
- `Tag_Section`
- `tag_topics`
- `tag_scenarios`
- `tag_audience`
- `tag_narrative`
- `tag_platform_fit`
- `tag_market`
- `tag_commercial`
- `tag_risk`
- `tag_confidence`

不直接适用于：

- `账号类目标签__平台抓取`
- `账号简介__平台抓取`
- `联系方式`

---

## 设计原则

### 1. 一次判断，双层产出

这套 workflow 不建议把 `账号类目标签` 和 `tag_*` 拆成两次独立生成。

推荐方式：

- 一次分类判断
- 同时产出人类可读层和系统标签层

也就是：

- `账号类目标签` 作为中文显示层
- `tag_*` 作为系统匹配层

### 2. 受控分类优先，不做自由发挥

`账号类目标签` 必须受控：

- 必须参考 `tag-system/account_category_label_standard.md`
- 不允许直接复制平台原始关键词串
- 不允许临场发明新标签

`tag_*` 也必须受控：

- 优先写稳定、可复用、可筛选的标签
- 不写只出现一次的偶发描述

### 3. 先用已有 `账号简介`

在 `S4` 阶段，优先级应改成：

1. `账号简介`
2. `账号简介__平台抓取`
3. `账号类目标签__平台抓取`
4. `平台`
5. `频道/作者名称`
6. `外链__平台抓取`
7. 其他稳定辅助信号

原因：

- `账号简介` 已经是 `S4` 内部压缩后的语义层
- 先看它，能让 `tag system` 更稳定
- 但不能只看它，仍要回看原始抓取字段做校正

### 4. 子 agent 优先

这类任务天然适合并行。

推荐原则：

- 主控 agent 负责切批、发包、收结果、抽查、回写
- 子 agent 只负责生成结构化 JSON
- 不让子 agent 直接改主表

---

## 标准流程

### Step 1. 生成 tag 输入包

脚本负责：

- 从主表抽取目标行
- 汇总证据
- 生成批次输入包

输入字段建议：

- `账号ID`
- `频道/作者名称`
- `平台`
- `账号简介`
- `账号简介__平台抓取`
- `账号类目标签__平台抓取`
- `外链__平台抓取`
- 如已有 `tag_*` 历史字段，也可作为弱参考

建议输出：

- `*_tag_input.jsonl`
- `*_tag_review.md`

### Step 2. 用 LLM 生成结构化分类结果

LLM 负责：

- 理解账号主方向
- 选出正式 `账号类目标签`
- 生成后续 `tag_*`
- 明确给出置信度

输出必须是 JSON。

### Step 3. 质检

主控 agent 负责：

- 检查 JSON 能否解析
- 检查 `账号类目标签` 是否落在正式池内
- 检查 `tag_topics` 是否与 `账号简介` 明显冲突
- 抽查 `low confidence` 样本

### Step 4. 回写主表

回写规则：

- 先做物理备份
- 再按 `账号ID` 匹配主表
- 只写正式输出列
- 不覆盖原始抓取列

---

## 推荐 Prompt 结构

### System Prompt

```text
你是 Rockbase 的 KOL 标签系统助手。你的任务是为账号生成 S4 阶段可复用的分类结果，用于后续筛选、匹配和客户推荐。

要求：
- 必须优先基于提供的证据做判断
- `账号类目标签` 必须使用受控标签池，不允许自由发明
- `账号类目标签` 优先输出单标签；只有确有必要时才输出双标签
- 如果双标签中包含 AI 标签，则 AI 标签必须前置
- `tag_*` 必须是稳定、可筛选、可复用的系统标签
- 证据弱时保守写，并降低置信度
- 只输出 JSON，不输出解释性散文
```

### User Prompt

```text
请基于以下证据，为该账号生成 S4 的 `账号类目标签` 与 `tag system` 字段。

字段：
- 账号ID：...
- 名称：...
- 平台：...
- 当前账号简介：...
- 平台 bio：...
- 平台类目：...
- 外链：...

输出要求：
1. 只输出 JSON
2. JSON 字段必须包含：
   - `账号ID`
   - `账号类目标签`
   - `Tag_Section`
   - `tag_topics`
   - `tag_scenarios`
   - `tag_audience`
   - `tag_narrative`
   - `tag_platform_fit`
   - `tag_market`
   - `tag_commercial`
   - `tag_risk`
   - `tag_confidence`
   - `confidence`
   - `evidence_used`
3. `账号类目标签` 必须符合正式标签池规则
4. 如果证据不足，允许部分字段保守留空，但不得乱写
```

---

## 推荐 JSON 输出格式

```json
{
  "账号ID": "@LangChain",
  "账号类目标签": "AI编程开发",
  "Tag_Section": "AI Builder",
  "tag_topics": "AI_Tools,Developer_AI",
  "tag_scenarios": "Developer Workflow,Agent Build",
  "tag_audience": "Developers,Technical Builders",
  "tag_narrative": "Tool-first,Builder Education",
  "tag_platform_fit": "X,YouTube",
  "tag_market": "Global,English",
  "tag_commercial": "B2D,SaaS,Developer Tools",
  "tag_risk": "Low",
  "tag_confidence": "High",
  "confidence": "high",
  "evidence_used": [
    "账号简介",
    "账号简介__平台抓取",
    "账号类目标签__平台抓取"
  ]
}
```

---

## 子 agent 执行建议

### 推荐默认配置

- 默认每组 `15-20` 条
- 默认 `3` 个子 agent 并行

这是当前最平衡的配置，因为：

- `tag system` 比单独写 `账号简介` 更复杂
- 每条输出字段更多，prompt 更长
- 如果批次过大，风格漂移和 JSON 出错概率会上升
- 如果子 agent 过多，主控抽查和回收成本会变高

### 推荐批次策略

当总量在 `150-300` 条时：

- 推荐 `3` 个子 agent
- 每批 `15-20` 条
- 第一轮先跑 `3` 批做口径验证
- 验证通过后滚动派发剩余批次

当总量低于 `80` 条时：

- 推荐 `2` 个子 agent
- 每批 `10-15` 条

当总量高于 `300` 条时：

- 推荐 `4` 个子 agent`
- 每批 `15` 条左右
- 但必须先抽查首轮，不建议一开始就全量放开

### 推荐分工

- 主控 agent：
  - 切批
  - 派发
  - 回收
  - 校验
  - 统一回写
- Worker A / B / C：
  - 只处理自己分配的批次
  - 只生成 JSON
  - 不碰主表

### 第一轮推荐方案

如果后面要真正跑 `S4 Hot` 的全量标签任务，建议：

1. 先切出 `batch_001 ~ batch_003`
2. 用 `3` 个子 agent 并行跑
3. 主控先抽查：
   - `账号类目标签` 是否符合正式池
   - `tag_topics` 是否合理
   - `tag_confidence` 是否过度乐观
4. 通过后再滚动铺开后续批次

---

## 为什么这套应该单独成 WF

- `账号简介` 是生成任务
- `账号类目标签 + tag system` 是受控分类任务
- 两者输入有重叠，但任务类型不同
- 单独成文件后，后面更容易维护、复跑和升级

结论：

- `S4-WF_X-Bio-LLM-Generation.md` 负责 `账号简介`
- `S4-WF_Tag-System-Generation.md` 负责 `账号类目标签 + tag_*`
