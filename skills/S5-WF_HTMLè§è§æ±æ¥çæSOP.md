---
description: [Output] HTML 视觉汇报生成 SOP | 场景：将匹配策略转化为高颜值 HTML 交付物
---

# 🛰️ Workflow: HTML 视觉汇报生成 SOP (Visual UI Architect)

> **目标**：将内部的达人筛选策略（Strategy）转化为具备 Rockbase 专业质感的静态 HTML 报告，用于甲方的长截图展示。

## 🛠️ Step 1: 品牌色调探测 (Color Extraction)
// turbo
1. **自动获取色卡**：若 Brief 中包含甲方产品 URL，必须使用 `Omni-Chrome` 或 `playwright` 访问该网站。
    - 提取按钮 (CTA) 的 `background-color` 作为 **Primary Color**。
    - 提取 Header/Footer 的深色背景作为 **Secondary/Header Color**。
    - 观察是否存在特定的渐变色或氛围色（光晕效果）。
2. **人工干预**：若无法获取网站或探测失败，**【必须】询问 Steve 明确期望的主色调**（如：科技蓝、活力橙、暗黑风）。

## 🛠️ Step 2: 内容脱水与架构 (Content Grooming)
1. **脱水过滤**：参考 `【SOP】KOL_Matching_Client_Report.md` 中的 Part One，严格过滤内部黑话（T1/Master表/预算/ROI）。
2. **结构化适配**：将 `P4` 策略内容拆解为：
    - `01` 匹配思路 (Highlight Block)
    - `02` 筛选依据 (Card Grid)
    - `03` 重点关注维度 (Card Grid / List)

## 🛠️ Step 3: 视觉渲染逻辑 (Visual Rendering)
强制遵循以下 UI 准则进行 HTML 生成：
1. **重头部反白 (Heavy Dark Header)**：
    - 使用深色渐变底纹。
    - 顶部包含 `ROCKBASE AGENCY EXPORT` 标识。
    - 标题加粗放大部分，并反白显示。
2. **动态色彩适配**：
    - 将 Step 1 提取的品牌色注入 CSS 变量 `--primary`。
    - 编号区块、按钮、高亮左边框强制绑定该颜色。
3. **截图友好排版 (Screenshot-Friendly)**：
    - 容器最大宽度锁定在 `860px - 900px`。
    - 背景使用极浅冷灰色 (`#F8FAFC`)，内容使用纯白悬浮卡片。
    - 行高保持 `1.6 - 1.7`。
4. **Emoji 使用规范 (Emoji Policy)**：
    - **严禁使用 Emoji**：除 Steve 明确要求外，汇报页面严禁使用 Emoji，以保持 Rockbase 的专业商务质感。
    - 若需视觉引导，优先使用图标字体、SVG 或极简的标点符号。

## 🛠️ Step 4: 交付与存档 (Delivery & Archive)
1. **物理备份**：在写入新的 P4.html 前，必须确保对应的 P4.md 已有当日备份。
2. **本地保存**：将生成的 `.html` 文件保存至项目根目录，命名为 `P4_{Project}_KOL_Matching_Strategy.html`。

## 🛠️ Step 5: 即时展示与快照输出 (Instant Preview & HD Export)
// turbo
1. **浏览器即时展示 (Auto-Open)**：在生成 `.html` 文件后，必须通过执行终端指令（如 `open "文件路径"`）直接在浏览器中弹窗打开该页面，供 Steve 实现“所见即所得”的审阅。
2. **生成高清 PNG**（依需执行）：
    - 启动本地服务器（如 `python3 -m http.server`）并使用 `playwright` 访问。
    - 执行全长截图 (`fullPage: true`)。
    - **视口配置**：固定宽度 `900px`，确保内容比例紧凑。
3. **路由存档**：
    - 截图默认保存至项目内部的 `workbench/` 目录，或按照 Steve 明确指定的目录（如 `Downloads`）输出。
    - 命名规则：`Snapshot_P4_{YYYYMMDD}.png`。
4. **结果提示**：在输出回复中明确展示本地文件路径、截图保存路径，以便随时调取。

---
📍 **Workflow Loaded by Friday | Rockbase Output Standard**
