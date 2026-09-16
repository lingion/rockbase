# S4 Workflow: YouTube Interaction Rate Enrichment

## 目标

为 `S4 Active` 或项目提报表中的 YouTube 账号补全 `互动率`，并统一使用可复算的近视频口径，而不是主页目测值或外部估算值。

本 workflow 只解决 YouTube `互动率`，不负责：

- 新增账号
- 抓联系方式
- 重写简介
- TikTok / Instagram 互动率

## 适用场景

- 表中 `平台 = YouTube`
- `互动率` 为空或需要重算
- 已有 `账号链接`
- 最好已有 `视频链接`，但不是必需

## 核心口径

默认统一为：

`互动率 = 最近 3 条非 Shorts 视频平均 [(点赞 + 评论) / 播放量]`

写回格式：

- 百分比字符串
- 保留两位小数
- 例如：`3.24%`

## 为什么不用主页现成值

YouTube 主页一般不直接提供稳定的 ER 字段。

如果只看频道主页：

- 可能只能拿到订阅数、总播放、频道简介
- 不能稳定拿到近视频的 `点赞 / 评论 / 播放`
- 也无法保证和提报表的“近期内容表现”口径一致

所以这里必须改为：

1. 找最近视频
2. 拉每条视频详情
3. 逐条计算
4. 求平均

## 数据源组合

本 workflow 默认采用两段式：

### 1. 频道页取最近视频

来源：

- YouTube 频道 `/videos` 页面 HTML

用途：

- 提取最近视频 `videoId`
- 过滤掉 `Shorts`
- 形成最近 3 条普通视频 URL

### 2. ScrapeCreators Video API

来源：

- `/v1/youtube/video`

目标字段：

- `viewCountInt`
- `likeCountInt`
- `commentCountInt`

用途：

- 计算单条视频 ER

## 计算规则

### 单条视频

`video_er = (likeCountInt + commentCountInt) / viewCountInt`

### 账号平均互动率

对最近 3 条非 Shorts 视频：

`avg_er = mean(video_er_1, video_er_2, video_er_3)`

最终写回：

`XX.XX%`

## 执行步骤

### Step 1: 选行

从目标 xlsx 中筛出：

- `平台 = YouTube`
- `互动率` 为空

可附加：

- 只处理前 N 行
- 或按指定账号名处理

### Step 2: 标准化频道 URL

进入脚本前先清洗：

- 去掉结尾 `/videos`
- 去掉尾部多余 `/`

保证频道基址统一。

### Step 3: 从 `/videos` 页面取最近视频

通过请求：

`{channel_url}/videos`

从页面源码中提取最近的 `videoId`。

规则：

- 按出现顺序去重
- 优先前面的条目
- 只保留普通视频
- 遇到 `type = shorts` 的视频，跳过

### Step 4: 对最近 3 条视频打 API

对每条视频 URL 请求：

- `/v1/youtube/video`

并提取：

- `viewCountInt`
- `likeCountInt`
- `commentCountInt`

### Step 5: 计算并写回

若至少有 1 条可算：

- 求平均
- 写入 `互动率`

同时：

- 若 `视频链接` 为空，可回填第一条参与计算的视频 URL

### Step 6: 产出复核结果

建议在当天 `workbench/{YYYY-MM-DD}/` 输出：

- 备份 xlsx
- 实验/回填 summary JSON

至少记录：

- 频道名称
- 参与计算的 3 条视频 URL
- 每条视频的 views / likes / comments / er
- 最终平均值

## 异常处理

### 1. 视频详情缺评论数

若 `commentCountInt` 缺失：

- 按 `0` 处理
- 但不阻止整条视频进入计算

### 2. 视频播放量为 0 或缺失

- 跳过该条视频

### 3. 最近条目是 Shorts

- 跳过
- 继续向后找普通视频

### 4. 频道页抓不到视频 ID

- 该账号保留为空
- 不编造互动率

### 5. 只有 1-2 条视频可算

- 可用已有条数求平均
- 不强制必须满 3 条

## 输出要求

### 写回字段

- `互动率`

可选补充：

- `视频链接`

### 百分比格式

- 固定两位小数
- 例如：`1.68%`

## 推荐脚本

本 workflow 的正式脚本：

- `scripts/youtube_interaction_rate_enricher.py`

## 推荐命令

```bash
python3 "scripts/youtube_interaction_rate_enricher.py" \
  --xlsx "/abs/path/to/file.xlsx" \
  --limit 10
```

只处理缺失值：

```bash
python3 "scripts/youtube_interaction_rate_enricher.py" \
  --xlsx "/abs/path/to/file.xlsx" \
  --only-missing
```

## 结论

这条 workflow 的核心不是“抓主页现成值”，而是：

- `频道 /videos 页` 决定最近内容范围
- `video API` 提供互动原子数据
- `脚本统一计算` 保证整表口径一致

这样得到的 `互动率` 才适合进入 Rockbase 的提报表。
