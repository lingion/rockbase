# S5 Sheet Overlay Sync

支持本地表 overlay、CSV 到 Feishu 增量同步和 DM 状态回填。首次运行必须读取目标 schema 并 dry-run；Feishu 地址与 Sheet ID 由接收方配置。

V2 依赖：`base`；需浏览器同步时加 `browser`。Feishu 连接是接收方外部配置，本入口未纳入 V2 干净环境 smoke。
