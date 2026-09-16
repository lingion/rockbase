---
tags: [KOL, Audit, Feedback, SOP, Workflow]
date: 2026-03-16
status: active
---

# 🛰️ KOL 审计反馈全程工作流 (KOL Audit Feedback SOP)

> **定位**：定义从“拆解甲方 Briefing”到“输出达人审计报告”，最后“生成反馈邮件”的全链路标准化流程。

> [!IMPORTANT]
> **执行顺序准则**：
> 1. **两阶段先行**：首先完成 **第一部分 (Part One)** 的基准构建与 **第二部分 (Part Two)** 的专项审计走查。
> 2. **中断等待**：在输出含有前两部分的审计报告后，必须**停止**后续动作。
> 3. **确认授权**：仅在 Steve 审阅审计结果并给出明确的“确认/Accept”指令后，方可启动 **第三部分 (Part Three)** 的反馈邮件撰写。

---

## ⚪️ 第零部分：项目初始化 (Part Zero: Initiation)

**目标**：在项目根目录下建立物理隔离的“审计工作舱”，确保过程文档归档有序。

### 1. 目录初始化
- **操作规范**：在甲方指定的项目文件夹内（如 `Proj-Ticnote/`）手动或通过脚本创建名为 `audit_feedback/` 的子目录。
- **命名规范**：强制统一使用 `audit_feedback`，禁止使用 `audit+feedback` 或其他变体，以保证路径兼容性。

### 2. 文档存储协议
- 所有生成的审计报告（MD）必须存储在 `audit_feedback/` 目录下。
- 文件命名建议包含日期或 KOL 名称，例如：`QC_Audit_{KOL_Name}_{YYYYMMDD}.md`。

---

## 🟢 第一部分：项目审计基准构建 (Part One: Audit Standard)

**目标**：基于甲方 Briefing 建立项目的“法律底线”，确保所有审计项有据可查。

### 1. 核心操作规范
- **身份画像提取**：明确甲方要求的受众群体（如职场人、学生、技术极客）。
- **硬指标像素级对标**：从 Briefing 中提取必须出现的动作（Actions）和功能（Features）。
- **【强制】原文引用协议**：
    - 每一项审计指标必须附带甲方说明的**英文原文**。
    - 必须标注原文所在的**行号（Line Number）**，确保审计的客观性与权威性。

### 2. 文档结构要求
- 定义受众定位（Persona Selection）。
- 建立 `Compliance Checklist` 表格，包含：审计要求、甲方原文、行号。

---

## 🔵 第二部分：达人专项审计执行 (Part Two: KOL Specific Audit)

**目标**：针对具体 KOL 提交的脚本/大纲进行逐项核对，输出结构化报告。

### 1. 审计表格格式规范
必须使用 Markdown 表格进行核对，字段包括：
- **阶段/模块**：视频的结构部分。
- **审计状态**：使用 `🆗 (优秀)`、`⚠️ (建议优化)`、`❌ (违规)`。
- **审计意见/建议**：具体的改进点。

### 2. 核心注意事项
- **对标 Part One**：所有判定逻辑必须回归到第一部分设定的基准。
- **动作场景化**：不仅检查功能是否提到，更要检查“演示动作”是否符合甲方要求（如：是否展示了点击按钮的特写）。
- **改进方案建议**：审计不仅仅是“挑错”，必须给出具体的、可落地的“补救措施”。

---

## 🔴 第三部分：Agent 反馈转写方法论 (Part Three: Feedback Email)

**目标**：将“强硬的硬性要求”包装为“专业的商务建议”。保持客气、共赢的沟通姿态（Professional & Appreciative Tone），避免居高临下的审核者态度。

### 1. 沟通结构 SOP (The Feedback Framework)
Agent 在起草针对达人的反馈信落款时（通常为英文），必须严格遵循以下三段式结构：

1. **破冰与赞美 (The Icebreaker & Praise)**：
   - **动作**：先明确指出大纲/视频草稿中的**具体亮点**（例如某个场景演示得很好、某个观点的契合度高）。
   - **目的**：建立友好的合作氛围，让达人感受到他们的创意受到了尊重和认可。
   - **话术参考**：*"Thank you so much for the draft! We thoroughly enjoyed... Your walkthrough of [Specific Feature] really captured the essence..."*

2. **核心诉求“软包装” (The "Soft" Adjustments)**：
   - **动作**：将甲方的修改意见转化为对达人或受众“有益”的建议。
   - **目的**：降低抗拒心理。不使用 "Action Required" 或 "Must Do"，而是使用 "Adjustment"、"Quick tweak" 或 "Action"。
   - **技巧**：
     - **提供上下文**：先说明目前的状况（Context）。
     - **赋予动机**：解释为什么修改（是为了观众体验更好、免费福利对观众是一种吸引力等）。
   - **话术参考**：*"To ensure it perfectly aligns with the current phase... Here are two quick adjustments... This will be a great selling point for your audience!"*

3. **友好的收尾 (The Positive Closing)**：
   - **动作**：重申整体的高品质，并表明 Agency 随时提供支持的合作姿态。
   - **目的**：完美收尾，促成快速修改。
   - **话术参考**：*"Other than those minor points, it looks phenomenal. Let us know if you need anything else!"*

### 2. 反馈语气准则 (Tone & Voice Checklist)
- [ ] **平等对等**：绝不以居高临下的“雇主”身份命令，而是以“合作伙伴（Partnership）”的视角沟通。
- [ ] **拒绝生硬**：把“你需要（You need to）” 换成 “您可以考虑（Could you please / We'd love to have）”。
- [ ] **明确具体**：在给出修改建议时，必须附带**精确的时间戳（Timestamp）**和**可以直接使用的文案素材（Copy/Prompt）**，极大降低达人的修改成本。
- [ ] **情绪抚慰**：针对由于 Briefing 变更导致的反复审改，要表达“这是为了最终的双赢”的抱歉与鼓励。

### 3. 发布格式准则 (Delivery Format - Dual-Version)
为了确保反馈能快速部署到飞书、微信等非 Markdown 平台，Agent 输出时必须提供双版本：
1.  **高可读版 (Formatted)**：使用标准的 Markdown 标题、加粗和列表。
2.  **一键复制版 (Plain Text Code Block)**：包裹在 ` ```text ` 中，去掉所有 Markdown 符号，确保背景干净。

---
📍 **Friday 提醒**：本工作流旨在确保 Agency 在甲方与达人之间起到“专业脱水机”的作用。
