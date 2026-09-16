# KOL 表格补全设计方案

## 目标

做一套可复用的补全技能，让它能兼容不同达人 CSV 结构，而不是每来一张新表就重写一份脚本。

真正稳定的核心不应该是列位置，而应该是 Agency 的规范字段体系。

这套设计要把任意一张输入表统一转化成以下四层：

1. 规范字段映射
2. 任务档位识别
3. 按字段拆分的抓取方案
4. 带备份的安全脚本回写

## 为什么你现在的体验会重

你现有的素材其实已经有很强的业务逻辑，但它们目前还是偏“绑定某一张表”：

- `Email_Outreach_Strategy.md` 已经定义了很多字段规则和质检标准
- `process_master_email_outreach.py` 里已经有不少提取、标准化和生成逻辑
- 但当前流程仍然默认你在处理一张接近固定 schema 的 Master 表

一旦遇到以下情况，体验就会变重：

- 有的表用 `平台作者`，有的表用 `频道名称`
- 有的表要补 `Email_Hook`，有的表只要补 `CDIK`
- 有的任务只靠 DOM 就够，有的任务必须截图确认
- 有的任务只跑 YouTube，有的任务会混合 X、Instagram、TikTok

所以真正该升级的不是“再写一个更大的脚本”，而是把抽象层往上提一层。

## 建议架构

### 1. 规范字段层

先定义一套内部统一字段，再把所有 CSV 表头在运行时映射进去。

建议的规范字段键名如下：

- `report_time`
- `reporter`
- `platform`
- `handle`
- `author_name`
- `profile_url`
- `language`
- `country`
- `followers`
- `avg_views_10`
- `top_pinned_views`
- `price_original`
- `price_rate_usd`
- `cpm`
- `bio_raw`
- `positioning`
- `audience`
- `gender`
- `age`
- `contact`
- `contact_note`
- `notes`
- `email_hook`
- `greeting_name`
- `email_subject`
- `email_content_v1`
- `email_content_v2`
- `tag_topics`
- `tag_scenarios`
- `tag_audience`
- `tag_narrative`
- `tag_platform_fit`
- `tag_market`
- `tag_commercial`
- `tag_risk`
- `tag_confidence`
- `cdik`
- `easykol_email_visible`
- `evidence_screenshot_path`

常见别名映射示例：

- `author_name` <- `平台作者`、`频道名称`、`Author`、`Channel Name`
- `handle` <- `账号ID`、`Handle`、`Username`
- `profile_url` <- `账号链接`、`主页链接`、`Profile URL`
- `bio_raw` <- `账号简介`、`Bio`、`Description`
- `contact` <- `联系方式`、`Email`、`Contact`

这是整个方案最重要的改动。一旦映射层稳定，后面的脚本就都能复用。

### 2. 任务档位层

每次执行时先选一个 profile，而不是从零开始拼逻辑。

建议至少支持以下几档：

- `master_full`
  - 用于 `【Master】2026Mar-KOL.csv` 这种完整清洗场景
  - 包含标准化、外联补全、画像生成、hook 生成
- `outreach_only`
  - 只处理 `contact`、`contact_note`、`email_hook`、`greeting_name`、`email_subject`、`email_content_v1`、`email_content_v2`
- `ticnote_cdik`
  - 只补 `CDIK` 和 EasyKOL 截图检查
  - 写入范围小，适合项目级 patch
- `discovery_tags`
  - 只处理 `tag_*` 字段和商业匹配判断
- `light_patch`
  - 用户给出少量目标字段和行范围，做轻量补丁

这样用户就不需要每次都重新解释一遍列怎么对应。

### 3. 抓取模式层

不要用一种抓法硬套所有字段。应该按字段选择来源模式。

建议的模式：

- `dom_primary`
  - 适合抓 handle、页面标题、粉丝数、canonical URL、bio 文本
- `dom_plus_cdp`
  - 适合读取登录态页面里渲染后的可见信息
- `screenshot_check`
  - 适合 EasyKOL 这类 UI 才能确认的状态
- `search_fallback`
  - 当主页拿不到字段时，只做一次搜索兜底
- `external_link_one_hop`
  - 在 4-step 预算内，只点最相关的一个外链

字段路由示例：

- `handle` -> `dom_primary`
- `profile_url` -> `dom_primary`
- `easykol_email_visible` -> `screenshot_check`
- `contact` -> `dom_primary`，拿不到再走 `search_fallback`，最后才考虑 `external_link_one_hop`
- `positioning` -> 基于 bio、最近标题、主页元信息的派生字段

### 4. 浏览器运行层

新的补全技能不应该再自己发明浏览器登录逻辑，而应该直接依赖 Omni-Chrome。

要求如下：

- 当 `9222` 没有可接管实例时，执行  
  `bash "${ROCKBASE_HOME}/Documents/GitHub/AG-Skills-Hub/04 🛜 Net/ag-omni-chrome/scripts/launcher_omni_chrome.sh"`
- 如果已经运行，就直接 CDP 接管
- 统一复用 YouTube、TikTok、Instagram、X 的登录态
- 浏览器启动逻辑和项目补全逻辑分层，不要混在一个脚本里

这样浏览器环境才会稳定，补全脚本本身也会更薄。

### 5. CSV 回写层

所有写入都走一套通用处理器。

建议输入参数：

- `--csv-path`
- `--profile`
- `--rows 201-250` 或 `--rows 3,4,5`
- `--target-fields contact,email_hook,greeting_name`
- `--platforms youtube,x,instagram,tiktok`
- `--dry-run`

建议执行顺序：

1. 先对主表做物理备份
2. 用 `utf-8-sig` 读取 CSV
3. 构建表头别名映射
4. 解析本次要处理的规范字段
5. 按行逐个补全
6. 只回写发生变化的行
7. 输出一份 JSON 执行报告

## 现有材料中哪些应该直接复用

### 从 `Email_Outreach_Strategy.md` 复用

这些内容应该变成“可复用规则”，而不是一次性备注：

- `Greeting_Name` 的 fallback 规则
- `平台作者` 和 `@handle` 的优先提取顺序
- YouTube 规范 handle 链接规则
- `博主国家` 中文化规则
- `粉丝数` 的 `K/M` 标准化
- `达人定位简介` 的生成逻辑
- `Email_Hook` 的压缩逻辑
- 4-step 动作预算和单跳外链规则

### 从 `process_master_email_outreach.py` 复用

建议抽成共享工具模块的部分包括：

- 国家标准化
- 粉丝数字标准化
- 称呼 fallback
- handle 标准化
- 频道链接重建
- 联系方式噪音剥离
- 达人画像生成
- hook 主题压缩

这份脚本本身的业务判断已经不错，真正要优化的是把它从“绑定某一张表、绑定某几个输出列”中解耦出来。

## 推荐的技能目录结构

```text
s1-inbox-enrichment/
├── SKILL.md
├── S1-WF_kol-enrichment-sop.md
├── references/
├── scripts/
│   ├── run_basic_enrichment.py
│   ├── run_deep_enrichment.py
│   ├── browser_runtime.py
│   ├── router.py
│   ├── field_registry.py
│   ├── path_resolver.py
│   ├── profiles.py
│   ├── runner_common.py
│   └── extractors/
│       ├── youtube_basic.py
│       ├── youtube_easykol.py
│       ├── tiktok_basic.py
│       ├── tiktok_easykol.py
│       ├── instagram_basic.py
│       ├── instagram_easykol.py
│       └── common.py
└── archive/
```

这一轮先把设计定清楚，后续脚本实现可以直接按这个结构展开。

## 通用输入模型

为了让你的使用体验更轻，用户输入应该尽量只保留这几个要素：

- CSV 路径
- 行范围
- 目标字段或 profile 名称
- 是否要求截图留证

例如：

- “补这个表的 `CDIK`，顺便看 EasyKOL 有没有显示 email，有就截图。”
- “按 Master 逻辑把这份表彻底清洗补全。”
- “只补外联字段，不动 tag 字段。”

系统应自动把这些自然语言转成：

- profile = `ticnote_cdik` 或 `master_full`
- target fields = 对应的规范字段集合
- evidence mode = 是否启用截图证据

## 表头映射策略

不要优先问用户 Excel 字母列。

应该固定按以下顺序处理：

1. 读取 header
2. 标准化 header 文本
3. 先做精确别名匹配
4. 再做语义别名匹配
5. 标记本次请求中无法解析的字段
6. 如确有必要，再按显示名新增规范列

你这两张真实表正好说明这个逻辑为什么必须有：

`【Master】2026Mar-KOL.csv`

- `平台作者` -> `author_name`
- `账号简介` -> `bio_raw`
- `达人定位简介` -> `positioning`
- `Email_Hook` -> `email_hook`

`P4.1_【KOL】Ticnote_Influencer_List_Rockbase_20260311.csv`

- `频道名称` -> `author_name`
- 没有 `达人定位简介`
- 没有 email content 系列字段
- 已经有大量 `tag_*` 字段

这就是为什么必须用规范字段映射，而不是继续用列号思维。

## 证据模型

部分字段应该有证据链，而不是只写结果值。

建议在列或 JSON 报告里保留：

- `source_mode`
- `source_url`
- `captured_at`
- `screenshot_path`
- `confidence`

以 EasyKOL 场景为例：

- 如果 email 可见，就保存截图路径，并把 `easykol_email_visible = yes`
- 如果不可见，就写 `easykol_email_visible = no`
- 不要因为看不到就臆造 email

## Ticnote 场景示例

对于：

`${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Proj-Ticnote/P4.1_【KOL】Ticnote_Influencer_List_Rockbase_20260311.csv`

推荐的任务档位：

- profile: `ticnote_cdik`
- target fields: `cdik`、`easykol_email_visible`、`contact`、`contact_note`
- evidence mode: 只对 EasyKOL 开启截图
- browser mode: 强制 Omni-Chrome

这类任务不应该假装它是 Master 表，而应该只补用户要求的字段，其他内容保持原样。

## Master 场景示例

对于：

`${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Agency/list-master/【Master】2026Mar-KOL.csv`

推荐的任务档位：

- profile: `master_full`
- target fields: 由 profile 自动解析
- browser mode: 强制 Omni-Chrome
- enrichment scope: 清洗 + 外联补全 + 达人画像生成

这类任务就应该复用现有邮件策略逻辑，但通过“规范字段映射 + 可复用提取模块”的方式来跑，而不是继续绑死在单一列位上。

## 最关键的体验优化

对你来说，最轻的使用方式应该是：

1. 给 CSV 路径
2. 说行范围
3. 说一个 profile 名称，或者直接说要补哪些字段

例如：

- `跑这个表，201-250，profile=master_full`
- `跑这个表，补 CDIK 和 EasyKOL email 截图`
- `只补 outreach 字段，别动标签`

这样就够了。Agent 应该自己去推断实际对应哪些列。

## 推荐实现顺序

### Phase 1

先搭通用骨架：

- header alias registry
- backup-first CSV processor
- profile router
- Omni-Chrome attach helper

### Phase 2

把 `process_master_email_outreach.py` 里的共用逻辑抽出来：

- 命名处理
- 标准化处理
- 画像生成
- hook 生成

### Phase 3

补平台提取器：

- YouTube
- X
- Instagram
- TikTok

### Phase 4

补截图取证和 JSON 执行报告。

## 结论

正确的优化方向不是“再写一个更大的专用脚本”。

正确的方向是：

- 一套可复用 skill
- 一套规范字段体系
- 一层任务 profile 路由
- 一条统一 CSV 回写管道
- 多种抓取模式共同挂在 Omni-Chrome 下面执行

这样你后面面对不同表格时，即使可见列不同，也仍然可以落到同一套工作流里。
