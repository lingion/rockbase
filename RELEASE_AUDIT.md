# Release Audit — v2.0.0

构建日期：2026-09-10

## 交付结论

本包是 V1 的轻量可移植性升级：保留 17 个 Skill 的源码与目录结构，新增根级安装元数据、分层依赖、共享路径层和代表性 S1/S3 离线验收。它不是完整运行镜像，也不是对方 PRD 中完整平台工程的实现。

## 已验证

- 使用干净 Python 3.11.14 环境按 `pyproject.toml` 安装 base + test 依赖成功，共安装 25 个包。
- 另用干净 Python 3.14.6 环境执行 pip editable 安装（无依赖、无网络模式）成功。
- `rockbase` 及四个 discovery `src/` 模块均可从项目外部目录导入。
- 根级离线测试：7/7 通过。
- S1 原路径测试：2/2 通过。
- S3 recovery 原测试：3/3 通过。
- S3 离线队列原测试：4/4 通过。
- 17/17 个 Skill 均通过 `skill-creator` 结构校验。
- 306 个 Python 源文件通过 AST 语法解析。
- 已安装的 base + test 依赖一致性检查通过。

## 脱敏与结构检查

- macOS 个人绝对路径：0 个文件命中。
- Windows 个人绝对路径：0 个文件命中。
- 非示例邮箱：0 个文件命中；测试数据只使用 `.example.invalid` 保留域。
- Google API key、OAuth access/refresh token 和私钥高置信特征：0 个文件命中。
- 未包含 `.env`、token JSON、credential JSON、Cookie 文件、私钥或软链接。
- `templates/.env.example` 只含空占位，由接收方复制到包外并自行填写。

## 已知限制

- 76 个历史文件仍含 `${ROCKBASE_HOME}` 占位符；它们已登记，未被误表述为全量迁移完成。
- 干净环境只验证共享路径层和代表性 S1/S3 入口，未遍历 17 个 Skill 的所有运行分支。
- S3 旧全量测试集在收集时需要 Google SDK。本次尝试安装 `gmail` 可选组时，本机访问 PyPI 出现 TLS 握手中断，因此没有将该全量测试标记为通过。
- 没有使用任何真实 Gmail、Feishu、社媒、数据服务或生产主表做验收。接收方仍需安装对应可选依赖、完成自己的授权并先做 dry-run。
