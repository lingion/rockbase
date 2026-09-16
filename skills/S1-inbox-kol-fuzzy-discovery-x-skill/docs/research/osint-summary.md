---
tags:
  - SocialAgency
  - OSINT
  - KOLResearch
  - ReportSplit
date: 2026-03-31
status: done
---

# OSINT相关内容详细总结

来源：基于 `${ROCKBASE_HOME}/Downloads/X API及抓取工具、OSINT相关内容总结报告.md` 按主题拆分整理。

## 一、OSINT核心定义与核心逻辑

### 1.1 定义

OSINT = Open Source Intelligence，中文名称为「开源情报」或「开源情报搜集」，核心是：**从公开可访问的网络信息中，批量、有目标地挖掘数据、找人、找关系、做分析**，全程合法合规，不涉及入侵、破解、隐私窃取，仅抓取公开信息。

### 1.2 与KOL挖掘的关联

当前需求（多平台模糊搜索、批量挖掘KOL），本质就是标准的OSINT工作流，具体对应：

- 目标：挖掘某一领域（如AI、美妆、游戏）的KOL；
- 数据源：X、YouTube、TikTok、Instagram等公开社交平台；
- 核心动作：批量采集公开信息 → 本地清洗、模糊匹配、筛选 → 输出可用于决策的KOL清单；
- 核心工具：所有用于KOL挖掘的开源工具（如Sherlock、snscrape），均属于OSINT工具。

### 1.3 OSINT核心特点

- 合法性：仅抓取公开信息，不入侵、不破解、不碰隐私数据（如私信、未公开手机号）；
- 免费性：绝大多数OSINT工具为GitHub开源免费，无内购、无付费解锁；
- 高效性：自动化批量抓取、筛选，替代人工一个个点开主页复制粘贴，节省大量时间；
- 灵活性：支持跨平台、模糊搜索、多条件筛选，可根据需求自定义挖掘逻辑。

## 二、适合普通人做KOL挖掘的OSINT工具（按GitHub Star降序，Top 10）

以下工具全部免费、无需平台API、开箱即用，核心聚焦KOL挖掘功能，按Star数量从高到低排序，详细信息如下：

|排名|工具名称|Star数|核心功能（KOL挖掘向）|适用平台|无需API|使用门槛|
|---|---|---|---|---|---|---|
|1|Sherlock|73.4k+|用户名跨平台搜索（覆盖300+平台）、批量查询账号归属、找隐藏KOL、导出搜索结果，支持模糊用户名匹配|全平台（X、YT、TikTok、IG等）|✅|低（纯命令行，一行命令即可运行）|
|2|snscrape|45k+|无API批量爬取内容/用户、关键词模糊搜索、导出CSV/JSON，支持X、YouTube等平台的推文/频道数据抓取|X、YouTube、Instagram、Reddit|✅|中（命令行，需基础Python环境）|
|3|yt-dlp|142k+|YouTube视频/频道数据抓取、元数据提取（标题、简介、粉丝数）、批量导出，可辅助挖掘YouTube KOL|YouTube|✅|中（命令行，适合专门挖掘YouTube KOL）|
|4|Social Analyzer|22k+|跨平台KOL搜索、互动数据统计、可视化界面、导出CSV/JSON，支持模糊关键词搜索，可统一筛选粉丝/互动率|YT、TikTok、IG、X、Facebook|✅|低（本地运行，可视化操作，无需复杂代码）|
|5|Maigret|18k+|模糊用户名搜索、账号关联图谱（跨平台找同主体KOL）、覆盖2000+平台、批量导出数据|全平台|✅|低（命令行，支持批量查询）|
|6|SpiderFoot|15k+|自动化情报收集、KOL关联分析（如KOL之间的互动关系）、攻击面映射，适合深度挖掘KOL人脉|全平台+域名/IP|✅|中（有可视化界面，需简单配置）|
|7|Osintgram|12k+|Instagram公开数据抓取、无登录、帖子/粉丝/评论导出，支持模糊关键词搜索，挖掘Instagram KOL|Instagram|✅|中（Python脚本，需基础配置）|
|8|PhoneInfoga|11k+|手机号反查、归属地/运营商/社交账号关联，可通过手机号挖掘KOL的关联社交账号|全平台（手机号→社交账号）|✅|低（命令行/网页版，无需配置）|
|9|TheHarvester|10k+|邮箱/域名/子域名收集、社交账号关联、KOL联系方式挖掘（提取公开邮箱/网址），辅助KOL商务对接|全平台+域名|✅|中（命令行，适合挖掘KOL联系方式）|
|10|Web-Check|9k+|一站式网站/频道分析、技术栈/安全/流量数据，可通过KOL的官网/个人主页，挖掘更多关联信息|网站/YouTube频道|✅|低（网页版/命令行，一键分析）|

## 三、OSINT工具分类（按使用场景）

### 3.1 跨平台通用工具（最推荐，一键搜多平台）

适合需要跨平台（X、YT、TikTok、IG）批量挖掘KOL的用户，无需分别操作不同工具，效率最高：

- **Sherlock**：核心优势是跨平台覆盖广，可快速查询某一用户名在多个平台的账号，找隐藏KOL、同名KOL；
- **Social Analyzer**：核心优势是可视化操作，支持模糊关键词搜索、互动数据统计，可直接导出KOL清单，最适合普通人；
- **Maigret**：核心优势是账号关联图谱，可挖掘同一主体在不同平台的KOL账号，适合深度关联分析。

### 3.2 单平台专用工具（精准挖某平台KOL）

适合只专注于某一个平台挖掘KOL，需要更精准、更全面的数据：

- X平台：snscrape（无API、批量抓推文/用户）、Twint（历史推文、关注/粉丝抓取）；
- YouTube平台：yt-dlp（频道数据、视频元数据抓取）、vidIQ（免费版，关键词搜索、相似KOL推荐）；
- TikTok平台：TikTok Scraper（无API、批量抓视频/用户）、TikFinity（免费版，关键词/标签搜索、KOL数据统计）；
- Instagram平台：Osintgram（无登录、公开数据抓取）、Toutatis（提取公开邮箱/电话）。

### 3.3 浏览器插件（边刷边挖，一键导出）

适合不想安装软件、不想操作命令行，边浏览平台边挖掘KOL的用户：

- EasyKOL（免费版）：支持YT、TikTok、IG，可查看相似KOL、计算互动率、预览KOL数据，一键导出；
- Influencer Analytics by Wednesday：支持TikTok、IG，免费查询KOL受众、真实粉丝数、合作价，辅助筛选优质KOL。

### 3.4 开源脚本（适合批量/自动化）

适合有基础Python能力，需要自动化批量挖掘、自定义筛选规则的用户：

- twitter-kol-discovery：专门用于X平台KOL挖掘，支持关键词批量抓取、本地模糊筛选、导出表格；
- union-search-skill：跨平台统一模糊搜索，整合多平台结果，支持标准化输出、批量脚本化搜索。

## 四、OSINT工具挖掘KOL的核心流程（普通人直接照做）

无论使用哪种OSINT工具，挖掘KOL的核心流程均为5步，简单易操作：

1. 确定目标：明确要挖掘的领域（如AI工具、美妆测评、游戏直播），确定筛选条件（粉丝量≥1万、互动率≥1%、近期有发帖）；
2. 选择工具：跨平台用Social Analyzer/Sherlock；单平台用对应专用工具（如X用snscrape、IG用Osintgram）；
3. 模糊搜索：输入领域关键词（如“AI”“LLM”），工具自动批量抓取相关候选用户/内容；
4. 批量导出：将抓取到的KOL信息（昵称、简介、粉丝数、互动数据）导出为CSV/JSON，保存到本地；
5. 深度筛选：在本地表格中去重、验粉，按粉丝量、互动率、领域相关性进一步筛选，最终得到高质量KOL清单。

## 五、OSINT工具挖掘KOL联系方式的原理（关键说明）

OSINT工具挖掘KOL联系方式，无任何黑科技，仅通过3种公开、合法的途径，博主未公开的联系方式一律无法获取：

### 5.1 核心原理（3种途径）

- 途径1：从博主个人主页简介提取（最常见，占90%）：工具自动扫描博主主页简介，识别并提取其中的公开信息，如邮箱、微信、WhatsApp、官网链接等；
- 途径2：从置顶帖/“联系我们”提取：工具顺着博主置顶帖、主页链接（如Linktree），爬取其中公开的商务合作方式；
- 途径3：公开情报交叉匹配（进阶）：通过博主公开的官网域名，反查域名注册邮箱，或匹配公开的商务邮箱记录，实现联系方式挖掘。

### 5.2 工具绝对做不到的事情（避坑提醒）

- 不能看到博主私信、未公开的手机号/微信；
- 不能破解博主账号、获取隐藏信息；
- 不能获取删除的内容、后台数据、粉丝隐私信息；
- 不能绕过平台限制，获取私密账号的内容。

## 六、OSINT工具使用关键注意事项（必看）

- 工具本身100%免费：所有推荐的GitHub OSINT工具，均为开源免费，无内购、无付费解锁、无订阅，无需向工具作者付费；
- 可能产生的费用：仅两种情况可能付费——① 若工具调用平台官方API（如twitter-kol-discovery调用X API），费用交给平台，而非工具作者；② 为避免被平台反爬，自行购买代理IP（可选，不买也能用，只是稳定性略差）；
- 无需API：绝大多数OSINT工具（90%以上）无需申请任何平台API，无需填写API Key，靠模拟浏览器访问、抓取公开网页数据工作；
- 合规性：仅抓取公开信息，用于个人学习、非商业用途，避免违规抓取、商用未授权，否则可能面临平台风控（如账号封禁）；
- 反爬提醒：批量抓取时，建议控制速度、添加延迟，避免频繁访问平台，防止IP被封禁；
- 工具稳定性：开源工具可能因平台页面结构变更而暂时失效，需关注工具GitHub页面的更新记录，及时更新版本。

## 七、OSINT工具与平台官方API的区别（核心对比）

|对比维度|OSINT工具（开源免费）|平台官方API（如X API、YT API）|
|---|---|---|
|费用|工具免费，仅代理IP可选付费|均需付费（无免费读数据权限）|
|API需求|无需任何平台API，开箱即用|需申请API Key，开通付费套餐|
|模糊搜索能力|极强，支持本地模糊匹配+多条件筛选|弱，仅支持简单通配符，不支持用户模糊搜索|
|稳定性|中，可能因平台反爬、页面变更失效|极高，官方维护，稳定可靠|
|风控风险|中低，控制速度可降低风险|无，官方通道，合规安全|
|适合场景|个人、非商用、小批量KOL挖掘，低成本|企业、商用、大批量抓取，需合规|

## 八、总结

OSINT是普通人批量挖掘多平台KOL的最优方案，核心优势的是免费、高效、灵活，无需复杂技术和高昂成本。所有推荐的OSINT工具均为开源免费，无需平台API，仅通过抓取公开信息实现KOL挖掘，全程合法合规。

对于普通人而言，优先选择跨平台工具（Social Analyzer、Sherlock），可快速实现多平台KOL模糊搜索；若专注于某一平台，选择对应单平台专用工具（如X用snscrape、IG用Osintgram），精准挖掘数据。使用时需注意控制抓取速度，避免IP被封禁，仅用于非商业用途，即可高效完成KOL挖掘需求。

> （注：文档部分内容可能由 AI 生成）

## 附：项目 GitHub 链接补充

以下仅补充已确认到的公开官方 GitHub 仓库；商业服务、浏览器插件或当前未检索到明确官方仓库的项目，单独标注说明。

- `Sherlock`：https://github.com/sherlock-project/sherlock
- `snscrape`：https://github.com/JustAnotherArchivist/snscrape
- `yt-dlp`：https://github.com/yt-dlp/yt-dlp
- `Social Analyzer`：https://github.com/qeeqbox/social-analyzer
- `Maigret`：https://github.com/soxoj/maigret
- `SpiderFoot`：https://github.com/smicallef/spiderfoot
- `Osintgram`：https://github.com/Datalux/Osintgram
- `PhoneInfoga`：https://github.com/sundowndev/phoneinfoga
- `TheHarvester`：https://github.com/laramies/theHarvester
- `Web-Check`：https://github.com/Lissy93/web-check
- `Twint`：https://github.com/twintproject/twint
- `Toutatis`：https://github.com/megadose/toutatis
- `twitter-kol-discovery`：暂未检索到可明确确认的公开官方 GitHub 仓库
- `union-search-skill`：暂未检索到可明确确认的公开 GitHub 仓库
- `vidIQ`：商业产品，未提供本报告内可确认的官方 GitHub 仓库
- `TikTok Scraper`：名称对应项目较多，暂未补充，以免误链到非目标仓库
- `TikFinity`：商业产品，未提供本报告内可确认的官方 GitHub 仓库
- `EasyKOL`：商业产品/工具服务，未提供本报告内可确认的官方 GitHub 仓库
- `Influencer Analytics by Wednesday`：产品服务，未提供本报告内可确认的官方 GitHub 仓库
