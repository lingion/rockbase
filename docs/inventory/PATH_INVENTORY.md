# V2 路径盘点

盘点口径：发布目录内全部文本与 Python 文件；历史文档和非正式入口也计入。

| 特征 | 命中文件数 | V2 处理 |
| --- | ---: | --- |
| `${ROCKBASE_HOME}` | 76 | 共享路径层遇到未设置变量时明确报错；未全量改写历史脚本 |
| `Path.cwd()` / `getcwd()` | 7 | 登记为后续迁移点，代表性 S1/S3 不再依赖启动目录 |
| `Agency/` | 74 | 作为业务目录名保留，不再要求用它猜测项目根 |
| `workbench/` | 109 | 作为输出语义保留；创建操作需要入口明确调用 |
| `deliverables` | 47 | 作为业务语义保留；不含真实交付数据 |
| `PYTHONPATH` / `sys.path` 注入 | 45 | 已增加根级可安装包；历史入口的临时注入留待逐项移除 |
| macOS `/Users/...` 绝对路径 | 0 | 通过 |
| Windows `C:\Users\...` 绝对路径 | 0 | 通过 |

## 已迁移

- `rockbase/paths.py`：统一项目根、输入和输出路径解析。
- `S1-inbox-enrichment/.../path_resolver.py`：改为共享路径层兼容 wrapper。
- `S3-ag-reply-recovery-sync-v3/scripts/project_paths.py`：改为共享路径层兼容 wrapper。
- S1/S3 各有一个从外部目录启动的离线 smoke。

## 待迁移集中区

`${ROCKBASE_HOME}` 剩余命中主要集中在 S3 入口与内部能力层、S5 表格同步、S2 Gmail、S1 历史脚本与 discovery 文档。它们已保留原有结构，但不属于本次干净环境通过的入口。

这份清单的作用是防止把“代表性迁移”误表述为“全部路径已清零”。
