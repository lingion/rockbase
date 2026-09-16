# Gmail Reply Ops System Spec

## 目标

`ag-gmail-reply-ops` 负责 Rockbase 在 Gmail 中的两段式运营链路：

- `Phase 1 - recovery`
- `Phase 2 - reply`

它不是单纯的“回邮件模板” skill，而是覆盖：

- 回信拉取
- thread 归因
- 附件抽取
- 报价理解
- review table 构建
- master 回写
- reply 起草
- 草稿回写

## 系统边界

### Phase 1 - recovery

负责：

- 从 Gmail 拉回回复线程
- 落正文与附件
- 生成可读报价结果
- 回写 master

不负责：

- 起草和发送 `Mail2 / Mail3`

### Phase 2 - reply

负责：

- 基于结构化 reply 表分桶
- 选择模板
- 生成 `Mail2_Body_Final`
- 在原 thread 内创建草稿
- 回写 `Mail2_Draft_ID`

不负责：

- 重新做 Gmail recovery
- 在价格未清晰前跳过 intelligence 直接乱回

## 全局主键

推荐稳定主键链路：

- `账号ID`
- `Reply_Contact_Email`
- `Reply_Thread_ID`
- `Reply_Last_Message_ID`

不要用这些字段做唯一主键：

- `频道/作者名称`
- `Greeting_Name`
- `Email_Subject`

## 主表与工作台原则

- master 只放决策所需的摘要字段
- 长正文、附件全文、OCR 文本不直接塞进 master
- 所有中间产物先落到 `workbench/{YYYY-MM-DD}/`
- 结构化 CSV 修改必须走脚本
- 写 master 前必须先做物理备份

## Gmail 发信全局规则

在当前 Rockbase 环境中，所有 Gmail 发信都走同一条已验证路径：

- 不默认走 `ADC`
- 不默认走 `gws`
- 使用 Gmail OAuth token + client secret + 固定脚本

普通草稿与 reply 草稿共用同一套认证资产；reply 草稿额外必须带：

- `threadId`
- `In-Reply-To`
- `References`

## 输出物原则

Phase 1 的关键输出：

- review-ready table
- master sync preview / audit / summary
- 已更新 master

Phase 2 的关键输出：

- reply-ready table
- `Mail2_Body_Final`
- Gmail drafts
- draft write-back
