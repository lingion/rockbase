# ADR-0002: Mail1 语义生成使用 OpenAI-compatible SDK

状态: 已采纳 · 日期: 2026-09-21

## 背景

S2 Mail1 生成原先通过本机 Codex CLI 子进程调用。这个入口依赖 macOS/CLI 安装、用户配置和工作目录，无法作为服务器上的稳定服务运行；调用失败也难以由服务器统一重试、记录和监控。

部署环境已经能够提供 OpenAI 或 Anthropic 兼容的 LLM endpoint，因此业务代码不应该绑定某个厂商或 CLI。

## 决策

使用 `openai` Python SDK 的 `chat.completions.create`，通过 `base_url` 注入部署侧的 OpenAI-compatible endpoint。

- `OPENAI_API_KEY` 或 `--api-key` 提供凭据。
- `--base-url` 提供 endpoint，默认 OpenAI `/v1`；部署侧可指向 Anthropic-compatible gateway。
- `--model` 提供模型名，默认 `gpt-4o-mini`。
- `run_llm_batch` 接收可注入 client，保持批量输入和 Mail1 四字段输出契约不变。
- dry-run 仍然只生成 audit，不写回 CSV。

脚本文件名暂时保留 `fill_mail1_with_codex.py`，避免破坏现有工作流和外部引用；其 Codex 实现已经删除，后续重命名另立迁移变更。

## 备选方案

### 继续调用 Codex CLI

- 优点：保留原有行为，改动较小。
- 拒绝：依赖 macOS CLI 和用户级配置，服务器部署不稳定，也不能统一控制 endpoint、超时和凭据。

### 直接分别集成 OpenAI SDK 与 Anthropic SDK

- 优点：可使用各厂商原生特性。
- 拒绝：业务逻辑出现供应商分支，部署配置和测试矩阵翻倍；当前需求只要求兼容 endpoint。

### 引入重量级 Agent/Workflow 框架

- 优点：可能提供更丰富的编排能力。
- 拒绝：Mail1 是单次结构化批量生成，框架成本高于收益；编排将在后续用轻量进程/定时任务完成。

## 后果

- ✅ 服务器只需配置 API key、base URL 和 model，不需要 Codex 或 macOS。
- ✅ client 可注入，离线测试不触网；独立 HTTP 合约测试可以验证真实 SDK 协议。
- ✅ OpenAI/Anthropic 兼容网关可在部署层切换。
- ⚠️ 只依赖兼容 endpoint 的 Chat Completions 请求形状；厂商原生特性不在本阶段范围内。
- ⚠️ API key 必须通过部署密钥管理提供，不能写入 CSV、日志或仓库。
