# Gmail：接收方自行授权

Gmail 功能是可选模块。本包没有、也不会请求 Steve 的 Google token。

1. 用接收方自己的 Google Cloud 项目创建 OAuth Client，并只授予所需 Gmail scope。
2. 在接收方自己的私有目录完成 OAuth 授权，token 不进入本包或 Git 仓库。
3. 将 token 文件位置显式传给脚本的 `--token-file` 参数；若脚本支持环境变量，则设置 `ROCKBASE_GMAIL_TOKEN_FILE`。
4. 先执行 dry-run/预览，再由人工确认是否创建草稿或发送。

缺少 token、scope 不足或账号不匹配时应停止。不要复制其他电脑上的 `gmail_token_*.json`，也不要把 token 作为压缩包附件发送。
