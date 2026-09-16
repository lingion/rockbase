---
name: s1-inbox-enrichment
description: 当用户要对 S1 Master、Inbox 表或原始 KOL 汇总池做达人主页原始信息抓取、字段补全、联系方式探测、平台标签回填时使用。本技能只负责平台可抓取事实和轻度清洗，不负责客户友好包装、商业定位提炼或 Active KOL 资产化写作。
---

# S1 Inbox Enrichment

本技能服务 `S1` 阶段，也就是把零散 KOL 先补全成可进入 `S2 Cold` 的基础资料表。

## 适用任务

- 补 `账号ID / 频道/作者名称 / 国家 / 粉丝数 / 语言`
- 抓 `账号简介__平台抓取`
- 抓 `账号类目标签__平台抓取`
- 探测 `联系方式 / 联系方式备注 / 外链__平台抓取`
- 只补平台原始事实，不写客户口径摘要

## 不做的事

- 不写 `S4 Active` 的客户友好版简介
- 不做商业定位、brief 匹配、合作建议
- 不产出最终交付标签
- 不回填报价判断和投放结论

## 执行原则

- 先物理备份，再写表
- 默认 `dry-run -> test-copy -> write`
- 只按字段语义工作，不依赖固定列号
- 平台差异走 extractor，不把平台逻辑堆在主脚本
- 所有过程文件进入 `workbench/{YYYY-MM-DD}/`

## 读取顺序

1. 先读本文件
2. 再读根目录的 [S1-WF_S1-kol-enrichment-sop.md](S1-WF_S1-kol-enrichment-sop.md)
3. 若任务明确是 EasyKOL 联系方式探测，先判断是否为 OpenCLI 或 Codex Chrome 路线：
4. 若请求是“用 kimi webridge 跑 EasyKOL”“通过 Kimi WebBridge 接管真实 Chrome 读右侧面板并写回”，优先读 [S1-WF_EasyKOL-KimiWebBridge-Email-Writeback-WF.md](S1-WF_EasyKOL-KimiWebBridge-Email-Writeback-WF.md)
5. 若请求是“用 opencli 跑 EasyKOL”“默认启 OpenCLI browser skill”“通过 OpenCLI 接管真实 Chrome 读右侧面板并写回”，优先读 [S1-WF_OpenCLI-EasyKOL-email-writeback.md](S1-WF_OpenCLI-EasyKOL-email-writeback.md)
6. 若请求是“用 codex chrome 跑 EasyKOL”“打开 Chrome 读右侧面板并写回”“批量拿 EasyKOL email 并回写表格”，优先读 [S1-WF_Codex-Chrome-EasyKOL-email-writeback.md](S1-WF_Codex-Chrome-EasyKOL-email-writeback.md)
7. 若只是通用 EasyKOL 联系方式探测或截图取证，读 [S1-WF_EasyKOL-contact-enrichment.md](S1-WF_EasyKOL-contact-enrichment.md)
8. 再按需读 [references/platform_extraction_notes.md](references/platform_extraction_notes.md)
9. 再按需读 [references/kol_master_enrichment_design.md](references/kol_master_enrichment_design.md)

## S1 推荐字段

- `账号ID`
- `频道/作者名称`
- `平台`
- `账号链接`
- `语言`
- `博主国家`
- `粉丝数`
- `账号类目标签__平台抓取`
- `近期10条均播`
- `账号简介__平台抓取`
- `联系方式`
- `联系方式备注`
- `外链__平台抓取`

## Canonical 字段建议

- `handle`
- `author_name`
- `platform`
- `profile_url`
- `language`
- `country`
- `followers`
- `avg_views_10`
- `bio_raw`
- `contact`
- `contact_note`
- `external_links_raw`
- `tag_topics_raw`
- `notes`

## 字段边界

- `bio_raw` 对应 `账号简介__平台抓取`
- `tag_topics_raw` 对应 `账号类目标签__平台抓取`
- `external_links_raw` 对应 `外链__平台抓取`
- 若主页无原始 bio，则清空旧值后保持空白
- 若主页无明确类目标签，则保持空白，不主观发挥

## 脚本入口

- API 主入口：`scripts/api/`
- 浏览层主入口：`scripts/browser/s1_browser_basic_enrichment.py`
- EasyKOL 主入口：`scripts/easykol/s1_easykol_enrichment.py`
- Kimi WebBridge EasyKOL 入口：`scripts/kimi_webbridge/`
- OpenCLI EasyKOL 入口：`scripts/opencli/`
- EasyKOL 截图取证：`scripts/easykol/s1_easykol_capture_panels.py`
  - 当前推荐口径：截图前先定位右侧 `EasyKOL` 面板，尽量把面板居中后再裁 `panel / emailbox`
  - 适用于 `email` 只能通过 UI 面板确认、需要截图留证、或 OCR 需要更干净输入的场景
- 浏览层内部路由：`scripts/browser/internal/router.py`
- 浏览层内部字段映射：`scripts/browser/internal/field_registry.py`
- 浏览层公共执行器：`scripts/browser/internal/runner_common.py`
- 浏览层平台实现：`scripts/browser/internal/extractors/*`
- 历史脚本归档：`archive/`

## 交接原则

当 `S1` 原始抓取完成后：

- 进入 `S2` 用于 cold outreach 素材准备
- 或进入 `S4` 做 Active KOL 资产化提炼

若用户要求“写成客户更容易读的版本”“提炼商业定位”“生成内部速览”，不要继续在本 skill 里硬做，应切到 `S4` 技能。

## 安全校验

- 迁移、改路径或改浏览层路由后，先运行：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .agent/skills/S1-inbox-enrichment/tests -p 'test_*.py'`。
- 该校验只验证项目根定位，不启动浏览器、不读写表格。
