# S1 Inbox Enrichment

用于补全已有达人名单的主页事实、联系方式线索与平台标签。输入为接收方提供的 CSV；输出先写入新文件或 dry-run 预览。需要浏览器或第三方数据服务时，由接收方自行登录/配置。

## V2 安装与路径

- 基础：`python -m pip install -e .`
- 浏览器流程：`python -m pip install -e '.[browser]'`
- 项目根：设置 `ROCKBASE_PROJECT_ROOT`，或使用 `.rockbase/config.toml`
- 验收：`python -m pytest -q tests/test_s1_path_smoke.py`

已迁移路径解析入口；真实浏览器会话、数据服务和生产 CSV 未包含也未代为验证。
