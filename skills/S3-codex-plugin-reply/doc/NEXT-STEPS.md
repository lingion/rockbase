# Next Steps

## 现在已经明确的事

1. Gmail 插件可以直接读 inbox 和真实正文
2. 现有 reply template system 可以直接用于小规模判断
3. Gmail 插件本身不能独立承担 create draft
4. 本地 OAuth token 路线仍然是正式写草稿方案

## 下一步最值得做的事

1. 先修 2026-05-06 sample 暴露出的两个系统性问题：
   - 价格策略没有严格贴模板
   - reply body 混入 quoted history
2. 把“完整 thread -> template_code -> pricing_state -> clean reply body”做成固定 workflow
3. 回看昨天已建的 8 封草稿，决定哪些需要重写 / 更新 / 删除
4. 增加一份北极星文档，明确：
   - 何时保守
   - 何时压价
   - 何时接受标准报价
   - 何时停止回复
5. 增加 daily summary 输出规范
6. 再决定是否拆分独立 skill

## 当前建议

短期：

- 文档先集中留在 `Codex plug in reply/`
- 流程稳定前，不急着拆成正式 `references / scripts / WF`

中期：

- 等 sample 写 draft 能力稳定后，再拆分正式脚本与 workflow

长期：

- 若 inbox triage + auto draft + summary + attachment routing 都稳定，再考虑独立 skill
