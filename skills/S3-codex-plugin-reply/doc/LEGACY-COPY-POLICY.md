# Legacy Copy Policy

日期：2026-05-07

## 为什么要复制旧 skill

当前 `S3-codex-plugin-reply` 已经被提升为新的正式 skill。

为了避免第一次重构时直接破坏旧系统，这里采取的是：

- 旧 skill 保持不动
- 把旧 skill 的关键文档和脚本复制一份到新 skill 内
- 后续只在新 skill 的副本上继续修改、拼装、实验

## 当前复制范围

### 文档副本

- `doc/legacy-recovery-sync-v3/`
- `doc/legacy-reply-draft-ops/`

### 脚本副本

- `scripts/legacy-recovery-sync-v3/`
- `scripts/legacy-reply-draft-ops/`

## 当前工作原则

1. 不直接改旧的 `S3-ag-reply-recovery-sync-v3`
2. 不直接改旧的 `S3-ag-reply-draft-ops`
3. 新逻辑、新 workflow、新 writeback 方案，都优先在 `S3-codex-plugin-reply` 内落地
4. 等新系统稳定后，再决定是否回写 / 替换旧 skill

## 好处

1. 旧系统还能随时回退参考
2. 新系统可以大胆试错
3. 不需要一开始就做艰难的原地改造

