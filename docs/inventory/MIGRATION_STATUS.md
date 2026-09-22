# V2 迁移状态

## 已完成

- 交付 loopback-first Rockbase Console：认证、viewer/operator 角色、CSRF、运行发现、阶段时间线、暂停/恢复/终止、send/sync 审批和 JSONL 审计。
- 提供无构建静态前端、systemd 单元、nginx TLS 反代示例和本地运维恢复指南。
- 保留 V1 的 17 个 Skill 入口及目录结构。
- 新增根级 `pyproject.toml`、pytest 配置和可安装的 `rockbase` 兼容包。
- 将依赖拆为 base、gmail、browser、ocr、social、llm 六组。
- 迁移 S1 通用补全路径 wrapper 和 S3 recovery 路径 wrapper。
- 修复 S3 测试中被脱敏破坏的 CSV fixture，改用 `.example.invalid` 虚构域名。
- 新增共享路径测试与 S1/S3 代表性离线 smoke。

## 本次明确未完成

- 未把 17 个 Skill 重写为统一 CLI。
- 未清零所有历史 `${ROCKBASE_HOME}`、`PYTHONPATH` 和 CWD 假设。
- 未建立全量机器可读 registry、capability 治理、外部通知供应商、真实账号验收和跨系统 CI；控制台的二次确认仅覆盖本机 operator 工作流。
- 未使用真实 Gmail、Feishu、社媒、数据服务或生产主表做端到端验收。
- 未包含账号、Token、Cookie、浏览器 Profile、历史邮件或真实业务数据。

## 接收方建议顺序

1. 在干净 Python 3.11+ 环境安装并运行离线测试。
2. 优先选定实际要用的 2–4 个 Skill，再对这些入口继续清理剩余路径。
3. 使用接收方自有的测试账号和测试数据完成 dry-run。
4. 通过字段映射、备份和人工复核后，才考虑生产读写。
