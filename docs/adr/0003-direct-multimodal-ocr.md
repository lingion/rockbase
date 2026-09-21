# ADR-0003: S5 OCR 直接使用多模态 LLM

状态: 已采纳 · 日期: 2026-09-21

## 背景

S5 OCR 之前依赖 macOS Vision Swift 或服务器上额外安装的 tesseract。前者不能在服务器运行，后者对社交平台截图中的小字、中文和图表布局不稳定；OCR 结果随后还要经过既有匹配、审查和 CSV 写回链。

## 决策

增加显式 `--ocr-engine llm`，使用 OpenAI-compatible Chat Completions 的图片输入直接读取截图。模型返回与现有 `ScreenshotData` 对应的 JSON：handle、author_name、email、countries、gender、age、confidence。结果继续进入既有 `evaluate_review_flags`、匹配、dry-run、备份和写回流程。

- `--llm-api-key` 或 `OPENAI_API_KEY` 提供凭据。
- `--llm-base-url` 与 `--llm-model` 由部署配置。
- 未选择 `llm` 时，原有 `auto`/`vision`/`tesseract` 路径不变。
- 缺 key 在读取图片/CSV 前 fail-fast；dry-run 仍不写回。

## 备选方案

### 继续使用 macOS Vision

- 优点：本机原生、无 API 费用。
- 拒绝：服务器不可用，且不是跨平台部署路径。

### 服务器安装 tesseract

- 优点：无外部 API。
- 拒绝：复杂截图布局和中文质量不足，部署还需要系统语言包；保留为旧 fallback 而非服务器主路径。

### OCR API + 文本 LLM 二段式

- 优点：可分别优化 OCR 和语义抽取。
- 拒绝：两次网络调用、字段对齐和中间文本丢失视觉布局；当前多模态 endpoint 已能直接完成结构化抽取。

## 后果

- ✅ 服务器不再需要 Swift/macOS；图片直接送到部署侧 vision-capable endpoint。
- ✅ 原有审查、匹配、备份和 dry-run 安全边界继续生效。
- ✅ 测试可用本地 loopback HTTP 验证真实 SDK 请求体和 data URL。
- ⚠️ 需要选择支持图片输入的模型；普通文本模型会返回错误或无效结果。
- ⚠️ 图片会发送到配置的 LLM endpoint，部署方必须按数据合规要求管理 endpoint、日志和保留策略。
