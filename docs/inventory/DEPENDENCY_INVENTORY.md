# V2 依赖盘点

## 安装层级

| 组 | 文件 | 主要用途 |
| --- | --- | --- |
| base | `requirements-base.txt` | CSV/表格、HTTP、HTML、图片与配置 |
| gmail | `requirements-gmail.txt` | Gmail API 与 Google OAuth |
| browser | `requirements-browser.txt` | Playwright 浏览器自动化 |
| ocr | `requirements-ocr.txt` | OpenCV 图像处理 |
| social | `requirements-social.txt` | Instagram/X 等平台辅助工具 |
| llm | `requirements-llm.txt` | OpenAI 兼容 SDK |
| constraints | `constraints.txt` | 各组的主版本上界 |

`pyproject.toml` 复刻上述分组，便于使用 `pip install -e '.[gmail]'` 安装。本包不提供 lockfile：它是跨机器源码交接，而不是固定操作系统和 CPU 架构的运行镜像。

## 非 Python 依赖

- Python 3.11 或更高版本。
- Playwright 能力另需安装对应浏览器内核。
- Gmail 需接收方自行创建 OAuth 客户端并授权。
- Feishu、社媒、代理和数据 API 由接收方账号和环境提供，不属于 pip 依赖。

## 验证边界

干净环境验收覆盖可编辑安装、共享路径层和代表性 S1/S3 离线流程。可选组完成了元数据与版本区间整理，不等于已使用真实外部账号做端到端验收。
