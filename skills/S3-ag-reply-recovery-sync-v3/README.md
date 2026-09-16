# S3 Reply Recovery Sync V3（内部能力层）

供 `S3-codex-plugin-reply` 抓取和整理回复证据、附件与报价信息。不得在没有接收方授权的 Gmail 账号和目标数据表时运行。

V2 已将 `project_paths.py` 接入共享路径层，但该 Skill 仍是 S3 内部能力层。依赖组为 `gmail`，需模型时另加 `llm`；真实 Gmail 授权和回写未包含在离线验收内。
