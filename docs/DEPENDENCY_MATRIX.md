# 依赖矩阵

| 能力 | 安装组 | 外部依赖 | 默认状态 |
| --- | --- | --- | --- |
| S1 表格补全 | `base`；浏览器流程加 `browser` | 接收方浏览器会话/数据服务 | 路径入口已迁移；外部流程未验证 |
| S1 fuzzy discovery | `base,social`；需浏览器时加 `browser` | 社媒账号、代理或数据 API | 模块可安装；历史路径待迁移 |
| S2 Gmail 草稿 | `base,gmail`；模型生成加 `llm` | Google OAuth、Gmail API | 默认不发送，未做真实授权验收 |
| S3 ReplyOps 离线队列 | Python 标准库 | 无 | 代表性 smoke 已验证 |
| S3 Gmail/回写 | `base,gmail`；模型生成加 `llm` | Google OAuth、Gmail API、目标表 | 默认不读写生产数据 |
| S4 活跃度/标签 | `base,social` | 平台抓取数据 | 尚未做 V2 干净环境验收 |
| S5 OCR | `base,ocr` | 图片输入；部分流程需 Vision 服务 | 尚未做 V2 干净环境验收 |
| S5 表格同步/查重 | `base`；自动化加 `browser` | Feishu/目标 Base | 默认 dry-run，未做真实授权验收 |
| 发票 | `base` | 无 | 保留源码，未做 V2 专项验收 |

所有外部服务都由接收方自行申请、授权、付费和管理。包内不内置第三方凭据。

`base` 对应 `pip install -e .`；可选组对应 `pip install -e '.[组名]'`。版本区间同时写在 `pyproject.toml` 和 `requirements/`，更新时需保持两处一致。
