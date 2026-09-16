# Rockbase Skills Release v2.0.0

这是一个脱敏的 Rockbase 达人营销工作流工具包。它包含发现、资料补全、邮件草稿、回复运营、活跃资产化、Brief 匹配、交付检查、OCR、表格同步、查重和发票生成能力。

## 先从这里开始

1. 阅读 [安装说明](docs/SETUP.md)，在独立 Python 3.11+ 环境执行 `pip install -e .`。
2. 运行 `python -m pytest -q`，确认路径层、S1 和 S3 代表性离线用例通过。
3. 从 `skills/` 选择一个 Skill，并阅读其 `README.md` 与 `SKILL.md`。
4. 只安装它需要的可选依赖；始终先用模板和 dry-run 验证。

## V2 可移植性

V2 新增可安装的 `rockbase.paths` 兼容层，路径优先级为：显式参数 → `ROCKBASE_PROJECT_ROOT` → 配置文件 → 安全发现。未解析的环境变量会直接报错，不会在本机生成字面量错误目录。

当前已完成该路径层和 S1/S3 代表性入口的迁移与离线验收；其余历史脚本的占位路径已登记，不宣称已全量平台化。详见 [迁移状态](docs/inventory/MIGRATION_STATUS.md)。

## 工作流地图

`S1 发现/补全` → `S2 草稿` → `S3 回复运营` → `S4 活跃资产` → `S5 匹配、QC 与同步`。

Gmail、Feishu、社媒登录和代理均为可选的本机配置：本包不包含任何 Cookie、token、密钥、真实名单、历史邮件或业务数据。

这是“可安装的源码包”，不是“开箱即用的完整运行镜像”。接收方仍需按说明安装依赖，并自行授权 Gmail、Feishu、社媒或数据服务。

## 重要边界

- 未授权的外部写入操作必须停止；先运行 dry-run 或预览。
- 初次 DM 不带外链与手机号；遵循每 2 小时 3–5 条的发送节奏。
- 联系方式查不到时填写“拿不到”，不得猜测或编造。
- 对生产主表写入前先备份，并在目标系统完成 schema/字段映射确认。

详见 [依赖矩阵](docs/DEPENDENCY_MATRIX.md)、[Gmail 自主授权](docs/GOOGLE_GMAIL_SETUP.md) 和 [安全说明](SECURITY.md)。
