# Codex Plug In Reply

日期：2026-05-06

这是 `S3-ag-reply-draft-ops` 下的临时聚合目录，用来承接今天开始的这条新能力线：

- Gmail 插件直接读 inbox / thread
- 大模型直接读取真实邮件正文并判断 reply intent
- 继续沿用本地 Gmail OAuth token 路线把 reply 写进 Gmail draft
- 后续再接定时任务、日报同步、附件分流

当前策略：

- 先把今天产生的过程文档集中落在这里
- 先验证最小闭环，不急着立即拆成新的独立 skill
- 等流程稳定后，再决定怎么拆回 `docs / references / scripts / WF`

## 当前包含

- `SPEC-升级方案-2026-05-06.md`
- `WF_Gmail-Plugin-Reply-Minimum-Test.md`
- `WF_Gmail-Plugin-Reply-Auto-Draft.md`
- `NEXT-STEPS.md`

## 当前结论

这个能力暂时不建议独立成新 skill。

更合适的路径是：

1. 先在 `S3-ag-reply-draft-ops` 内部新增 plugin-first workflow
2. 先把 Gmail 插件读信 + 本地 OAuth 写 draft 的混合闭环跑稳
3. 等自动化、附件分流、日报同步都稳定后，再评估是否独立 skill
