---
name: ag-skywork-dedupe
description: 对 Skywork 达人 CSV 做飞书 Base 查重、分批断点续传和截图 QC。仅在用户明确指定浏览器与目标 Base 后使用。
---

# 🛰️ Skill: ag-skywork-查重

负责 Skywork 项目的博主名单查重任务。通过接管 `omni-chrome` 浏览器实例，自动在飞书 Base 系统中验证博主 ID 是否重复。

## 🛠 核心功能
- **自动化查重**: 自动读取 CSV 文件中的博主 ID 列（默认 D 列）。
- **浏览器接管**: 基于 CDP 协议接管 9222 端口的现有浏览器环境。
- **状态判定**: 智能识别“重复”与“可用”状态。
- **QC 抽查验证**: 每处理 10 条数据自动捕获 1 张实时搜索截图，用于后期真实性审计。
- **断点续传**: 分批处理数据，防止系统频率限制。

## 📦 设置与前提 (Prerequisites)
1. **浏览器环境**: 必须先执行 `/omni-chrome` 启动专用浏览器。
2. **目标页面**: 在浏览器中打开飞书查重链接（Master URL）：
   `https://rg975ojk5z.feishu.cn/share/base/query/shrcn5CSZ6pe8aBPO2Vz62dhpUb?from=notion_content_v7`

## 🚀 使用指南 (Usage)

### 1. 启动查重
执行以下指令对指定 CSV 进行全量查重：
```zsh
node [SkillPath]/scripts/skywork_dedupe.js [CSV_PATH]
```

### 2. 输出位置
结果将保存在原文件同级目录下，文件名为 `{OriginalName}_deduped_{Date}.csv`。

## 📝 自动化协议 (Turbo)
// turbo
- `node scripts/skywork_dedupe.js` 会自动开始任务。

## 📋 维护记录
- 2026-03-05: 初始化 Skill，集成 Playwright-core 自动化引擎。
