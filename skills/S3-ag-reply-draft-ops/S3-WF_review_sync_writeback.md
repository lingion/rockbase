# Review Sync Writeback

> 用途：当 Steve 在 review xlsx 中完成修改后，把这些修改**稳妥回写**到 `【S3 ReplyOps】Corestar-Replied-KOL.csv`。
> 这个流程只接受“review xlsx 是人工真相源”的前提。

## Part1 总原则

- 回写永远以字段名为准，不以列号为准。
- 回写前必须先备份主 CSV。
- CSV 只允许脚本化修改，不允许手工改原始文本。
- review xlsx 中未修改的字段，不要顺手覆盖。

## Part2 稳定映射键

默认稳定键：

- `账号ID`
- `账号链接`
- `Latest_Inbound_Message_ID`

推荐组合键：

```text
账号ID + 账号链接 + Latest_Inbound_Message_ID
```

为什么不用列号：

- 因为 review xlsx 会为了阅读体验频繁增删列、换位置
- 只要字段名和稳定键还在，回写就不应受影响

## Part3 允许的核心修改类型

### 修改类型 A：改 `Pipeline_Stage`

最常见场景：

- 把 `M1_3_Replied_Review` 或 `M2_3_Replied_Review` 改成 `Z_Manual_Review`

回写规则：

- 主 CSV 对应行更新 `Pipeline_Stage`
- 被改成 `Z_Manual_Review` 的业务行必须集中下沉到 `Z` 区块
- 不要只改字段值却把行留在原位置

一句话标准：

- **改成 manual review 的行，最终必须和其他 manual review 行放在一起。**

### 修改类型 B：改模板字段

最常见场景：

- 改 `Mail2_Reply_Template`
- 改 `Mail3_Reply_Template`

回写规则：

- 主 CSV 同步对应 template 字段
- 根据模板代码，自动重刷对应 body 字段：
  - `Mail2_Reply_Template` -> `Mail2_Body_Final`
  - `Mail3_Reply_Template` -> `Mail3_Body_Final`
- 正文来源必须统一来自：
  - `references/reply_templates.md`

模板规范化规则：

- 支持 Steve 写缩写，例如：
  - `RQ3`
  - `RI2`
- 写回 CSV 前必须规范成 canonical 形式，例如：
  - `RQ3 | quoted_accept_discounted`
  - `RI2 | interested_send_details_no_price`

## Part4 M1_3 回写范围

对 `M1_3` review view，允许回写：

- `Pipeline_Stage`
- `Mail2_Reply_Template`
- `Mail2_Body_Final`
- 必要时人工备注字段，例如：
  - `Manual_Review_Reason`
  - `Manual_Review_Focus`

## Part5 M2_3 回写范围

对 `M2_3` review view，允许回写：

- `Pipeline_Stage`
- `Mail3_Reply_Template`
- `Mail3_Body_Final`
- 必要时人工备注字段，例如：
  - `Manual_Review_Reason`
  - `Manual_Review_Focus`

## Part6 写回顺序

1. 备份主 CSV
2. 读取 review xlsx
3. 用稳定键对齐主 CSV
4. 只提取被修改过的字段
5. 先回写 `Pipeline_Stage`
6. 再回写 template 字段
7. 再按模板库重刷 body 字段
8. 如果有 `Z_Manual_Review`，执行下沉重排
9. 回读校验
10. 输出一份 writeback summary

## Part7 校验要求

至少检查：

- 修改行数是否和 xlsx 差异行数一致
- `Z_Manual_Review` 的数量是否符合预期
- template 字段是否已 canonicalize
- 对应的 `Mail2_Body_Final / Mail3_Body_Final` 是否已经同步更新
- 是否误覆盖未编辑行

## Part8 交付物

每次 writeback 必须产出：

- 主 CSV 备份
- writeback summary
- 如有需要，更新后的 review xlsx

报告强制要求：

- 写回完成后，必须先在当前窗口给 Steve 一个简洁摘要
- 同时必须把完整报告写成 MD，放到当天 `workbench/{YYYY-MM-DD}/`
- 报告中至少列出：
  - 修改了多少行
  - 哪些行改了 `Pipeline_Stage`
  - 哪些行改了 `Mail2_Reply_Template / Mail3_Reply_Template`
  - 哪些正文被联动重刷
  - 是否执行了 `Z_Manual_Review` 下沉

一句话标准：

- **Steve 在 xlsx 里改的是哪几格，CSV 就只精确更新哪几格，再联动更新必须联动的正文，不多改一行。**
