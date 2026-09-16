# S4 Workflow: X Part2 Media vs Marketing Classification

## 目标

把 X 平台名单统一分成：

- `P1`：普通个人 KOL
- `P2.1`：个人媒体
- `P2.2`：机构媒体
- `P3`：营销号
- `P4`：404

同时把误装进媒体桶的个人号退回 `P1`。

## 为什么要拆

甲方要单独付费的重点，不是所有“媒体感账号”，而是：

- 缺少个人背书
- 以流量分发、导流推广、营销承接为主
- 可替代性更高

这类账号应归入 `Part2.2 营销号`，并在商务上单独核算。

## 三类对象的定义

### P1 个人号

特征：

- 明确个人身份
- 粉丝主要因为“这个人”而关注
- 内容与本人经历、观点、专业判断绑定
- 即使内容高频，也仍带有稳定个人背书

典型例子：

- 创业者
- 工程师
- 教授 / 研究员
- 个人创作者
- 个人投资人

### P2.1 个人媒体

特征：

- 账号主体是个人
- 但内容形态明显带有栏目化、媒体化、资讯分发或固定报道风格
- 粉丝既消费这个人的判断，也消费其“媒体化分发能力”
- 仍不同于纯机构媒体

典型例子：

- 个人 newsletter 作者
- 个人媒体主持人
- 个人 AI roundup 作者
- 个人记者 / 个人播客主持人

### P2.2 机构媒体

特征：

- 账号主体更像媒体、机构、品牌、公司、社区或 newsletter
- 核心价值是信息分发、栏目化输出、社区触达或官方发声
- 不以个人真实使用和个人背书为主要卖点
- 可以承接传播，但更像媒体位

典型例子：

- 官方机构号
- AI newsletter brand
- 媒体品牌号
- 社区 / 开源组织 / 平台官方号

### P3 营销号

特征：

- 核心价值更偏流量分发、导流、推广、合作承接
- 内容高度模板化、可替代性强
- CTA 重，商务导向强
- 账号和产品之间的真实长期绑定较弱

典型例子：

- Daily AI roundup + DM for collabs
- AI creator for your brand
- submit / feature / promote your AI product
- 高度工具盘点化、导流化、招商化账号

## 核心判断原则

不要只问“像不像媒体”，而要问：

> 这个账号卖的是“个人判断”，还是“分发能力”，还是“推广承接能力”？

判断优先级：

1. 账号主体
2. 内容形态
3. 商业气质
4. 信任来源
5. 可替代性

## 数据源优先级

### 一级证据

- `备注`
- `频道/作者名称`
- `账号简介__平台抓取`
- `账号类目标签`
- `账号简介`
- `Recommendation`

注意：

- 旧的 `media/institution` 备注只算“先验提示”，不是最终真值
- 如果主表 bio 明显是个人号，但同时带强商务导向，应优先考虑 `Part2.2 营销号`
- 如果主表 bio 明显是个人专家号，且缺少机构或营销信号，应退回 `Part1`

### 二级证据

来自 `workbench/2026-03-26/` 的 X 候选池与搜索 JSON：

- `x_layer1_candidate_pool_openclaw-us-en-v1.json`
- `x_layer1_candidate_pool_openclaw-us-en-v2.json`
- `x_layer1_candidate_pool_openclaw-us-en-v21.json`
- 相关 `x_layer1_search_*.json`

其中重点字段：

- `likely_org`
- `looks_personal_name`
- `brandish_handle`
- `marketing_risk`
- `creator_signal`
- `creator_fit_score`
- `sample_text`

说明：

- 这些 JSON 只作为辅助证据
- 若 JSON 缺失，仍以主表字段做判断
- 不允许因为 JSON 没命中就停止分类

## 实际分类规则

### 一步判断：404 优先

若 `备注` 含 `404`：

- 直接保留 `Part3`

### 二步判断：明显媒体号

满足以下任一项，优先归 `Part2.1`：

- `备注` 已标 `media/institution`
- bio 明显是公司、平台、实验室、社区、组织、品牌、newsletter
- 表达主体是 `we / our / company / community / lab / platform`
- 账号本质是官方位或媒体位，而不是个人位

强媒体关键词示例：

- `newsletter`
- `media`
- `lab`
- `community`
- `official`
- `platform`
- `company`
- `we are`
- `daily AI newsletter`

### 三步判断：明显营销号

满足以下 2 项以上，优先归 `Part2.2`：

- bio 中有明显合作导向：`DM for collabs`、`for partnerships`、`for promos`
- 明显招商导向：`feature your product`、`submit your AI`
- 明显品牌代运营 / creator-for-brand 导向
- 内容形式以高频盘点、模板化推荐、导流推广为主
- 账号人格很弱，产品替换性很强
- 备注或证据中出现 `marketing`、`creator for your brand`、`influencer marketing`

强营销关键词示例：

- `DM for collabs`
- `paid promos`
- `for partnerships`
- `creator for your brand`
- `influencer marketing`
- `promote your AI`
- `submit your product`
- `daily updates`

### 四步判断：退回 P1

若账号虽被旧备注放进 `media/institution`，但本质更像个人号，则退回 `P1`。

典型条件：

- 明确个人身份强于媒体身份
- 内容主要来自个人专业判断
- 粉丝关注的核心是这个人，而不是媒体分发壳
- 没有强营销承接信号

容易退回 `Part1` 的类型：

- 教授 / 研究员
- 个人投资人
- 个人创业者
- 个人工程师 / Builder
- 个人教育者

## X 平台特殊注意

- X 上很多人会写 `Founder`、`Builder`、`Writer`
- 这些词本身不能直接证明是媒体号或营销号
- X 上也有很多个人号运营 newsletter，这类账号不能一刀切
- X 上也常见“个人壳 + 商务导流”账号，这类不能因为旧备注写了 `media/institution` 就直接放进媒体号

判断关键：

- 若核心是“个人判断” -> `P1`
- 若核心是“个人媒体分发” -> `P2.1`
- 若核心是“机构媒体分发” -> `P2.2`
- 若核心是“招商导流” -> `P3`

## 强营销补充规则

以下组合出现时，应优先考虑 `P3`：

- 个人身份词：`content creator`、`ai influencer`、`marketer`、`creator`
- 同时出现商务词：`DM for collabs`、`paid collaboration`、`brand partnerships`、`open for promo`
- 内容描述偏通用增长或分发：`helping brands grow`、`build their brand`、`daily updates`

这类账号更像“个人化营销壳”，不是典型媒体号，也不是标准个人 KOL 背书位。

## 商务理解

### 媒体号

- 更像媒体位
- 适合传播和栏目露出
- 但不是典型个人 KOL 背书位

### 营销号

- 更像流量位 / 推广位
- 适合单独采购
- 通常不应按个人 KOL 的背书价格体系购买

### 个人号

- 才是标准 KOL 背书位
- 价格中包含个人信任溢价

## 输出要求

最终 `分区` 只允许：

- `P1`
- `P2.1`
- `P2.2`
- `P3`
- `P4`

## 备注前缀规范

- `P2.1` 默认备注前缀：`media/personal`
- `P2.2` 默认备注前缀：`media/institution`
- `P3` 默认备注前缀：`marketing`
- `P4` 默认备注前缀：`404`

说明：

- `marketing` 用于标记应单独核价的营销号
- 不要再把 `P3` 写成 `media/institution`

## 复核建议

优先人工复核以下边界样本：

- 个人 newsletter 作者
- 个人媒体主持人
- 个人 AI roundup 账号
- 公司创始人兼媒体运营者
- 研究员但被旧备注放入 `media/institution`
