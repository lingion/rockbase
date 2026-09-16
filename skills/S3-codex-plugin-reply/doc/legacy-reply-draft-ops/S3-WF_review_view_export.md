# Review View Export

> 用途：当 Steve 要对 `M1_3_Replied_Review` 或 `M2_3_Replied_Review` 做人工审阅时，先从主 CSV 抽出一份**专门的 review xlsx**。
> 这里建议统一把 “human review” 叫做 **Operator Review** 或 **Review View**，因为本质上不是随意人工浏览，而是带明确编辑目标的操作界面。

## Part1 总原则

- 行选择只按 `Pipeline_Stage`，不按 Excel 行号。
- 字段选择只按字段名，不按列字母。
- review xlsx 的目标不是“全表复制”，而是：
  - 保留足够上下文
  - 减少视觉干扰
  - 让 Steve 能直接判断模板、正文和阶段
- 所有 review xlsx 必须保留可稳定回写的锚点字段：
  - `账号ID`
  - `账号链接`
  - `Latest_Inbound_Message_ID`

## Part2 M1_3 Review View

用途：

- 审 `Mail2_Reply_Template`
- 审 `Mail2_Body_Final`
- 必要时把 `Pipeline_Stage` 改成 `Z_Manual_Review`

### M1_3 必带字段

| 字段 | 为什么要带 |
| --- | --- |
| `Pipeline_Stage` | 允许 Steve 直接改阶段 |
| `账号ID` | 稳定映射键 |
| `账号链接` | 人眼快速识别账号 |
| `Latest_Inbound_Message_ID` | 稳定映射键，防止重复账号误写 |
| `Mail1_Body_Final` | 我方发出去的 Mail1 正文 |
| `Mail1_Reply_From_Hub` 或 `Mail1_Reply` | 对方第一次回复 Mail1 的正文 |
| `Mail1_Pricing_Excerpt` | 第一轮信价摘要 |
| `Mail1_Reply_Summary` | 快速扫读用 |
| `Mail1_Reply` | 对方完整正文 |
| `Mail1_Attachment_Pricing_Excerpt` | 附件价格线索 |
| `Mail2_Reply_Template` | Steve 直接改模板 |
| `Mail2_Body_Final` | 看当前系统生成正文是否合理 |

### M1_3 可选字段

- `Manual_Review_Reason`
- `Manual_Review_Focus`
- `Owner`
- `Priority`

## Part3 M2_3 Review View

用途：

- 审 `Mail3_Reply_Template`
- 审 `Mail3_Body_Final`
- 必要时把 `Pipeline_Stage` 改成 `Z_Manual_Review`

### M2_3 必带字段

| 字段 | 为什么要带 |
| --- | --- |
| `Pipeline_Stage` | 允许 Steve 直接改阶段 |
| `账号ID` | 稳定映射键 |
| `账号链接` | 人眼快速识别账号 |
| `Latest_Inbound_Message_ID` | 稳定映射键，防止重复账号误写 |
| `Mail1_Body_Final` | 我方 Mail1 发件正文 |
| `Mail1_Reply_From_Hub` 或 `Mail1_Reply` | 对方对 Mail1 的第一次回复 |
| `Mail2_Sent_Body_Quoted` 或 `Mail2_Sent_Body_Raw` | 我方 Mail2 发出去的正文证据 |
| `Mail2_Pricing_Excerpt` | 第二轮信价摘要 |
| `Mail2_Reply_Summary` | 快速扫读用 |
| `Mail2_Reply` | 对方对 Mail2 的完整回复 |
| `Mail2_Attachment_Pricing_Excerpt` | 附件价格线索 |
| `Mail3_Reply_Template` | Steve 直接改模板 |
| `Mail3_Body_Final` | 看当前系统生成正文是否合理 |

### M2_3 可选字段

- `Manual_Review_Reason`
- `Manual_Review_Focus`
- `Owner`
- `Priority`

## Part4 Review XLSX 格式要求

强制要求：

- sheet 名必须清晰，例如：
  - `M1_3_Review`
  - `M2_3_Review`
- 冻结窗格必须打开
  - 建议冻结到“账号识别列 + 上一轮信件列”之后
- 必须开启筛选
- 长文本列必须：
  - 自动换行
  - 顶端对齐
  - 足够列宽
- 标题行必须有明显底色
- 不要把无关字段塞进去，只保留当前决策所需字段

推荐列宽：

- `账号ID`：18
- `账号链接`：28
- `Latest_Inbound_Message_ID`：22
- 各类 body / reply 列：56-60
- template 列：28

## Part5 导出后的交付物

- 一个专用 xlsx
- 文件名建议：
  - `YYYY-MM-DD_M1_3_Replied_Review_review_view.xlsx`
  - `YYYY-MM-DD_M2_3_Replied_Review_review_view.xlsx`

一句话标准：

- **Steve 打开后，应该能一眼看清：我发了什么、对方回了什么、价格是什么、系统建议回什么。**
