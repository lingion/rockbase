# WF Gmail Plugin Reply Minimum Test

## 目的

在不改大结构、不依赖旧 manifest 完整性的前提下，验证以下能力是否成立：

1. agent 能否从 Gmail 插件中拉取过去 24 小时 inbox
2. agent 能否筛掉明显无关邮件
3. agent 能否识别与 Rockbase 外联直接相关的 reply
4. agent 能否基于真实正文选择现有 reply template
5. agent 能否生成少量可审阅回复

## 当前最小规则

### 时间窗口

- `in:inbox newer_than:1d`

### 先排除

- promotions / newsletters
- 系统通知
- bounce / DSN
- 显然不属于 Rockbase outreach 的工作流邮件

### 保留候选

- subject 明显是 `Re: Paid collaboration ...`
- thread 正文中能看到我方上一封外联内容
- 对方回复内容与报价、意向、brief gate、预算、验证相关

## 当前模板映射规则

- 已明确给价：`RQ1 / RQ2 / RQ3`
- 有兴趣但没给价：`RI1`
- 发了 details 但没给清晰价格：`RI2`
- 先问预算：`RI3`
- 要求先看 brief / verification：`RI4`
- 明确拒绝：`RX1`
- 判断不稳：`RX2`

## 当前最小输出

每轮只需要产出：

1. 相关邮件 shortlist
2. 每封邮件的 template suggestion
3. 每封邮件的一版 reply body

## 当前验证成功点

2026-05-06 已验证：

- 能拉取过去 24 小时 inbox
- 能区分 promotions / bounce / security / workstream / outreach reply
- 能对少量真实邮件生成 3 封以内的可审阅回复草稿文本

## 暂不做

- 不自动写入草稿箱
- 不自动更新 replied master
- 不自动处理附件
- 不自动全量扫所有 thread
