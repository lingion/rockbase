# 安装与自检

## 基础安装

建议使用 Python 3.11+ 与独立虚拟环境。先安装基础依赖：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pytest -q
```

只在需要对应能力时安装可选组：

```bash
python -m pip install -e '.[gmail]'
python -m pip install -e '.[browser]'
python -m pip install -e '.[ocr]'
python -m pip install -e '.[social]'
python -m pip install -e '.[llm]'
```

也可使用 `requirements/requirements-*.txt` 逐组安装。`constraints.txt` 提供可接受的主版本上界，不是锁死到单一补丁版本的 lockfile。

## 路径配置

推荐在本机设置项目根：

```bash
export ROCKBASE_PROJECT_ROOT="/your/path/to/rockbase-project"
```

或者在当前目录的 `.rockbase/config.toml` 写入：

```toml
[paths]
project_root = "/your/path/to/rockbase-project"
```

优先级是显式参数、`ROCKBASE_PROJECT_ROOT`、配置文件、安全发现。配置的根目录必须已存在；输出父目录不会被默认创建。

## 使用方式

把本包的 `skills/` 放入你的 Codex skill 目录，或在 Agent 配置中注册该目录。先读取目标 Skill 的 `SKILL.md`，然后用其 README 中的示例输入运行 dry-run。

## 本机配置

复制 `templates/.env.example` 到一个不受版本控制的本机 `.env`。不要把 `.env` 放回此发布包。任何标有 `${ROCKBASE_HOME}` 的旧路径都是尚未迁移的历史占位符；在启用该脚本前，必须改用接收方的路径、命令行参数或共享路径层。

## 验收

- 每个 `skills/*/` 都应存在 `SKILL.md`。
- 在不放入任何凭据的情况下，`python -m pytest -q` 应完成离线检查。
- 需要 Gmail、Feishu 或社媒会话的功能，在配置缺失时应停止并提示配置，而不是读取其他账户。

## 能力边界

本包是可安装的源码包，不是带齐账号、数据、浏览器会话和运行环境的完整镜像。V2 方案一只对共享路径层及代表性 S1/S3 入口做了干净环境验收；其他历史脚本需按迁移清单逐项改造。
