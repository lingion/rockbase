---
name: ag-ocr-sync
description: 对 EasyKOL / Ticnote / 受众分析截图做 OCR，优先使用 Vision OCR + 版式感知规则，识别频道/作者名称、账号ID、Email、粉丝受众、粉丝性别、粉丝年龄，并脚本化回填到 CSV 主表。适用于“根据截图回表”“先备份再写表”“输出同目录 OCR 过程 JSON”的场景。
---

# AG OCR Sync

这个 skill 用于把截图中的账号识别结果回填到 KOL 主表，并在截图目录旁输出可复核的 JSON 过程文件。

默认设计前提：

- 大约 `80%` 的截图版式与 EasyKOL / Ticnote 当前受众分析页一致
- 剩余 `20%` 可能有轻微 UI 偏移、语言差异或 OCR 噪音
- 因此脚本采用 `版式感知 + 双 OCR 融合`，而不是只依赖全文 OCR

## 📍 Workbench 路由前置规则

- OCR 图片在处理前，必须先确认是否已经位于当天 `workbench` 目录中。
- 唯一合法根目录：
  - `${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/workbench/`
- 当天 OCR 图片默认路由：
  - `workbench/{YYYY-MM-DD}/`
- 如果用户给的图片仍在 `Downloads`、桌面或其他目录：
  - 不能直接在原位置处理
  - 必须先**剪切**到当天 `workbench/{YYYY-MM-DD}/` 再处理
- 如果当天目录不存在：
  - 必须先创建当天目录
- 开始 OCR 前，必须显式确认：
  - 图片当前路径
  - 是否已进入当天 `workbench` 目录

推荐动作顺序：

1. 检查图片路径
2. 创建 `workbench/{YYYY-MM-DD}/`（如不存在）
3. 将图片剪切到当天目录
4. 以当天目录中的图片作为唯一 OCR 输入源
5. 在同目录输出 `ocr_results*.json` 和 `issues*.json`

## 适用范围

- 输入是一批 PNG/JPG 截图
- 截图顶部至少能读到以下之一：
  - `账号ID`
  - `频道/作者名称`
  - `Email`
- 截图下半部分至少包含以下一部分：
  - `粉丝受众`
  - `粉丝性别`
  - `粉丝年龄`
- 目标是把截图信息回填到 CSV 主表

## 强制规则

- 修改 CSV 前必须先物理备份到 `Agency/list-bak/YYYY-MM-DD/`
- 只能脚本化修改 CSV
- 不能直接处理 `Downloads` 或临时目录中的原图
- OCR 输入图必须先进入当天 `workbench/{YYYY-MM-DD}/`
- 必须在截图同目录输出过程 JSON，至少包含：
  - `file_name`
  - `image_path`
  - `author_name`
  - `matched_account_id`
  - `duplicate`
  - `formatted`
- 必须额外输出：
  - `duplicate_images*.json`
  - `ocr_summary*.md`
- 优先通过截图顶部的 `账号ID / 作者名 / Email` 定位主表行，禁止仅靠受众数据猜行
- 如果出现重复截图，允许保留进 JSON，但写表时只能写一次
- 必须优先做图片级去重：
  - `exact hash` 去重
  - `visual hash` 近重复去重
  - OCR 默认只处理去重后的主图
- `账号ID` 统一写成标准 `@handle`
- 如果 OCR 识别出的 `Email` 与表内旧值不一致：
  - 只有当 OCR 邮箱通过有效性校验时才覆盖
  - 通过校验的 OCR 邮箱优先于旧值
- `粉丝受众` 统一写成：
  - `国家1 占比 / 国家2 占比 / 国家3 占比 / 国家4 占比`
  - 国家必须中文化
  - 例如：`美国 56.7% / 加拿大 13.5% / 韩国 12.3% / 墨西哥 5.9%`
- `粉丝性别` 统一写成：
  - `男 58%/女 42%`
  - 男必须在左，女必须在右
  - 百分比必须四舍五入为整数，且严格相加等于 `100%`
  - 如果只识别到一个性别，另一侧用余数补齐
  - 如果恰好 `50/50`，强制修正为 `52/48`
- `粉丝年龄` 统一写成：
  - `18-25 (20.5%)/25-45 (79.5%)`
  - `18-25` 必须始终在左侧
  - 括号写法固定，斜杠两侧不加多余空格
  - 这是把 `13-17 / 18-24 / 18-20 / 21-24 / 0-17` 合并为 `18-25`，把剩余成熟年龄桶合并为 `25-45`
- 如果图片显示的是城市榜、语言榜或其他非国家榜，禁止写入 `粉丝受众`
- 如果匹配分数不够、或存在多行候选接近，禁止自动写表，改为写入 `issues/review` JSON
- 如果同一 `账号ID` 在 CSV 中重复出现：
  - 默认禁止自动写表
  - 优先使用 `--partition-filter` 缩小到单一分区
- 默认优先保护已有人工值：
  - `粉丝受众 / 粉丝性别 / 粉丝年龄` 已有内容时，默认不覆盖
  - 只有显式传入 `--force-overwrite` 时才覆盖

## 执行方式

- 先运行 `scripts/ag_ocr_sync.py`
- 默认流程：
1. 先做图片级去重
2. 优先使用 `Vision OCR`
3. 同时允许 `tesseract` 作为字段级兜底
3. 优先提取顶部 `handle / name / email`
4. 对 EasyKOL / Ticnote 常见版式做区域解析，重点提取 `countries / gender / age`
5. 用 `handle > email > name` 的顺序匹配表格行，并支持 `name-as-handle` 兜底
6. 先做第一轮字段级自动写入：
   - 能稳定写的字段直接写
   - 不稳的字段进入 `partial-write`
   - 只有身份不稳或国家字段明显脏时才进入 `review-required`
7. 自动执行**第二轮检查 (Second Pass)**：
   - 对第一轮 `unmatched / review-required / partial-write` 的图片再次尝试修复
   - 先做字段清洗：国家名纠错、性别格式归一、年龄格式归一
   - 再做更激进但受控的二次匹配：允许 `name~name` 与 `name~handle` 的模糊唯一命中
   - 若二次清洗后字段可稳定写入，则直接补写，不再抛给用户
8. 输出 `ocr_results*.json`
9. 如仍有问题图，输出 `issues*.json`
10. 输出 `duplicate_images*.json`
11. 输出 `ocr_summary*.md`
12. 备份 CSV
13. 默认只写回 `粉丝受众 / 粉丝性别 / 粉丝年龄`

执行前新增硬检查：

- 若图片不在当天 `workbench` 目录：
  - 先移动，再 OCR
- 若用户给的是单张图片路径：
  - 仍需先移动到当天 `workbench` 目录
- 若用户给的是多个图片路径：
  - 应统一归集到当天 `workbench` 目录后再批量处理

常用参数：

- `--ocr-engine auto|vision|tesseract`
- `--target-id @handle`
- `--target-name "Channel Name"`
- `--only-files /abs/path/a.png other.png`
- `--partition-filter Part1`
- `--review-threshold 0.75`
- `--dedupe-images` / `--no-dedupe-images`
- `--force-overwrite`
- `--dry-run`

新增硬规则：

- 当使用 `--target-id` 或 `--target-name` 时：
  - 必须把图片范围缩小到单张
  - 推荐搭配 `--only-files`
  - 禁止对整目录直接用 `target-name` 强绑写表

## 二次检查原则

- 默认必须先跑完脚本内建的 `Second Pass`，不能一看到 `issues` 就立刻让用户人工处理
- 只有以下情况仍允许保留到最终汇报：
  - 二次匹配后仍然没有唯一目标行
  - 国家榜明显脏到无法稳定清洗
  - 截图只截到顶部身份，没有截到受众区域
  - 性别/年龄字段缺失过多，无法安全格式化
- 最终给用户的汇报应尽量压缩到“剩余 unresolved 项”，而不是把所有轻微问题都甩回去
- `ocr_summary*.md` 需要明确体现：
  - 第一轮匹配数量
  - 第二轮自动救回数量
  - 最终仍需人工复核数量

## 脚本

- 主脚本：`scripts/ag_ocr_sync.py`

示例：

```bash
python3 scripts/ag_ocr_sync.py \
  --image-dir "/path/to/images" \
  --csv-path "/path/to/master.csv" \
  --partition-filter "Part1"
```

```bash
python3 scripts/ag_ocr_sync.py \
  --image-dir "/path/to/images" \
  --csv-path "/path/to/master.csv" \
  --target-id "@JordanPlatten" \
  --only-files "/path/to/screenshot.png" \
  --force-overwrite
```

## 基于实战的升级建议

- 当前版本已经支持：
  - `Vision OCR` 优先，`tesseract` 字段级兜底
  - `exact hash + visual hash` 重复图识别
  - 国家中文纠错词典
  - `--target-id / --target-name`
  - `--only-files`
  - `--partition-filter`
  - 更激进的字段级自动写入
  - `partial-write` 机制
  - 仅在高风险情况下才 `review-required`
  - `Second Pass` 二次检查与自动补写
  - `ocr_summary*.md`
  - `--dry-run`
  - 默认已有值保护

- 后续仍建议继续升级：
  - 增加 `--json-out` 和 `--issues-out`
  - 增加更多平台感知信号
  - 增加更细的异常值识别
  - 增加更复杂的年龄桶可配置合并逻辑

## 什么时候需要人工复核

- OCR 只识别到名称，没有 `handle/email`
- 邮箱看起来像 OCR 误读，例如 `gmailcom`、`gmai.com`
- 截图展示的是城市榜而不是国家榜
- 年龄桶缺失关键分段，导致无法稳定合并
- 同一账号出现多张截图但结果不一致
- 受众国家与 KOL 所在国家偏差极大，需要进入业务判断而不是 OCR 判断
