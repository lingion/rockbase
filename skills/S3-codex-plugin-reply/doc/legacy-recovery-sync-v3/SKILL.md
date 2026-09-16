---
name: ag-reply-recovery-sync-v3
description: V3 版本的 S3 Gmail reply recovery skill。用于持续抓取回复线程、保留正文与附件证据、构建 LLM 输入包、提炼最新有效价格，并分阶段升级 `【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`。
---

# S3 Reply Recovery Sync V3

## 目标

这个 skill 只负责两件事：

1. 把 Gmail 回复与附件证据稳定拉回本地。
2. 基于回复链和附件证据，构建 V3 的价格理解输入与输出链路。

## 不负责

- 不写 Mail2 / Mail3 / MailN 正文
- 不发送任何回复邮件
- 不决定模板
- 不直接替代 `.agent/skills/S3-ag-reply-draft-ops`

## 唯一入口

1. 先读本 `SKILL.md`
2. 再读 `V3_SPEC.md`
3. 再读 `V3_SORT_AND_SYNC_POLICY.md`
4. 需要字段机器对齐时再读 `FIELD_MANIFEST.json`

## 当前保留文档

- `SKILL.md`
- `V3_SPEC.md`
- `V3_SORT_AND_SYNC_POLICY.md`
- `FIELD_MANIFEST.json`

## 固定 Workbench

V3 的专用项目文件夹固定为：

`${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/rockbase-gmail-reply-recovery-v3/`

历史目录映射：

- `workbench/rockbase-gmail-reply-recovery-v1/` 视为历史 Hub V1
- `workbench/rockbase-gmail-reply-recovery-v2/` 视为历史 Hub V2
- `workbench/rockbase-gmail-reply-recovery-v3/` 视为当前唯一写入的 Hub V3

说明：

- 需要调取旧资料时，优先从 V1 / V2 读取
- 需要写入新的 V3 产物时，一律写入 V3
- 为避免打断旧引用，保留旧目录名软链接作为兼容入口

口头指令协议：

- `Hub`：默认指当前主 Hub；写入时默认指 Hub V3，查历史时默认按 Hub V3 -> Hub V2 -> Hub V1 顺序回查
- `Hub V1`：指 `workbench/rockbase-gmail-reply-recovery-v1/`
- `Hub V2`：指 `workbench/rockbase-gmail-reply-recovery-v2/`
- `Hub V3`：指 `workbench/rockbase-gmail-reply-recovery-v3/`

以后 Steve 可以直接说：

- 去 `Hub` 找
- 去 `Hub V1` 找原始材料
- 去 `Hub V2` 找旧批次
- 把新结果写入 `Hub V3`

以后这个 skill 的中间产物、样本、输入包、输出包、审计结果，都应优先写入这个目录。

## 主表口径

- `match / bootstrap` 只参考：
  - `Agency/list-master/【S2 Cold】Corestar-1000-KOL.csv`
  - `Agency/list-master/【S2 Cold】Rockbase-580-KOL.csv`
- `writeback` 只写入：
  - `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL_V3.csv`
- 旧的 `Agency/list-master/【S3 ReplyOps】Corestar-Replied-KOL.csv` 只作为历史兼容参考，不再作为 V3 的正式写入目标
- 系统邮件、newsletter、bounce、地址错误类邮件直接忽略，不进入 `manual_review`

批次规则：

- 根目录固定使用 `rockbase-gmail-reply-recovery-v3/`
- 每一轮执行写入 `runs/{YYYY-MM-DD}_run-XXX/`
- 同一天多批次递增 `run-001`、`run-002`、`run-003`
- 不再把长期产物散落写入普通日期 workbench 根目录
- 若是阶段性总结或人工 review 稿，可在当天 `workbench/{YYYY-MM-DD}/` 保留镜像副本

## 当前保留脚本

- `scripts/capture_replies.py`
- `scripts/fetch_reply_threads.py`
- `scripts/extract_reply_attachments.py`
- `scripts/build_llm_input_pack.py`
- `scripts/sync_master_v3.py`
- `scripts/translation_utils.py`
- `scripts/run_attachment_pipeline_from_preview.py`
- `scripts/run_attachment_pipeline_chunked.py`
- `scripts/ocr_dual_engine.py`
- `scripts/run_dual_ocr.py`
- `scripts/audit_ocr_quality_and_price_signals.py`

## 标准顺序

1. `capture_replies.py`
2. `fetch_reply_threads.py`
3. `extract_reply_attachments.py`
4. `build_llm_input_pack.py`
5. 大模型解释 `latest_price_raw / latest_price_normalized / latest_price_basis / 多平台标记`
6. 分段回写 V3 结果到主表

附件接线补充：

- 当 recovery preview 已经产出后，可直接使用 `run_attachment_pipeline_from_preview.py`
- 它会自动完成：
  - 从 preview 提取 `Reply_Thread_ID`
  - 拉 full thread 与 attachment inventory
  - 下载附件
  - 抽取文本
- 当 preview 规模较大（如 7d combined preview）时，优先使用 `run_attachment_pipeline_chunked.py`
- 它会将大批量 thread 自动分块，逐块执行 fetch + attachment extraction，避免长单批次中断
- 当前 V3 的独立双 OCR 能力固定为：
  - `macOS Vision OCR`
  - `tesseract`
- 独立入口为 `run_dual_ocr.py`
- 附件抽取默认也复用这套双 OCR，而不是只跑单一 OCR
- OCR 全量质检与价格标准化入口为 `audit_ocr_quality_and_price_signals.py`
- 该脚本会输出：
  - `ocr_quality_audit.csv`
  - `ocr_price_candidates.csv`
  - `ocr_price_candidates_trusted.csv`
  - `ocr_quality_summary.md/json`
- 价格标准化规则：
  - 原始命中保留在 `price_raw`
  - 规范化结果统一输出到 `price_normalized`
  - 统一成 `$1,500` / `€3,500` / `£250` 这种货币符号在前、千分位分隔的格式

## 默认策略

- 回复链按 `mail1_reply_block ~ mail5_reply_block` 组织
- `mail1_reply_block ~ mail5_reply_block` 必须是 inbound-only；禁止混入我方 sent 邮件、quoted outbound 内容或系统噪音
- recovery 对 outreach thread 的识别，除 Mail1 初始模板外，还应参考 `⚙️ Skills/S3-ag-reply-draft-ops/references/reply_templates.md` 中 mail2-4 跟进模板的关键措辞
- `Outbound_Message_IDs` 应支持动态 `mailN`，不能只停留在前三波
- 小语种统一补中文翻译
- `latest_price_raw` 保留作者原文
- `latest_price_normalized` 统一为规范货币符号 + 千分位分隔数字
- `latest_price_normalized` 允许同时保留当前有效价与 regular/original 参考价，但必须显式区分：当前有效价使用 `[effective]`，参考价使用 `[regular/original reference]`
- `多平台标记` 由大模型按价格语义生成，不直接继承主表单一平台列；展示位置放在 `平台` 后面
- V3 先以 sample / input pack / output pack 方式验证，再分段升级主表
- 下一阶段优先级调整为：先把网上与 Hub 内的最新资料尽量抓全，再统一清洗与升级
