# rockbase-mailkit

Rockbase S2/S3 邮件链路适配器：**发信走公司 SMTP，收信走 mailgofer 兼容 API**。
替代原 Gmail OAuth 草稿链路，人工干预点归零。纯 Python stdlib，零第三方依赖。

```
S2 发信:  CSV → mailkit.send → 公司 SMTP (默认 dry-run + 限速 + 断点续传)
S3 收信:  KOL 回信 → [A] Cloudflare Email Routing → mailgofer
                  → [B] Postfix catch-all → postfix_pipe → receiver.py(SQLite)
S3 回收:  mailkit.fetch_replies → replies_YYYY-MM-DD.csv/json → S3 流水线
S3 回填:  mailkit.master_sync → replies 写回 master CSV（wave 归因 + 字段字典协议）
S2 回执:  mailkit.master_sync sent → send manifest 写回 master（MailN_Status/Outbound_Message_IDs）
```

## 快速开始

```bash
cp config.example.toml config.toml   # 填掉全部 PLACEHOLDER
python3 tests/test_smoke.py          # 离线自检（不需要任何凭据）

# 收信端（路线B，公司服务器）
python3 -m mailkit.receiver --db mailkit.db --port 8788 --api-key <KEY>

# 发信（先 dry-run 看计划，再 --execute）
python3 -m mailkit.send --config config.toml --csv batch.csv
python3 -m mailkit.send --config config.toml --csv batch.csv --execute

# 回复回收
python3 -m mailkit.fetch_replies --config config.toml

# 回填 master CSV（S3 字段字典协议；默认 dry-run，--execute 才写）
python3 -m mailkit.master_sync replies --config config.toml --master master.csv
python3 -m mailkit.master_sync replies --config config.toml --master master.csv --execute

# 发送回执回填（MailN_Status=sent + Outbound_Message_IDs）
python3 -m mailkit.master_sync sent --config config.toml --master master.csv --wave mail1 --execute
```

CSV 格式：`email,name,subject,body`，正文可用 `{name}`。
兼容 S2 job manifest：`--to-field to --name-field display_name`。
回信模式：行内带 `in_reply_to`（可选 `references`）列 → 挂线程头发送，
豁免首触链接守卫与节奏上限。

## 内置守卫（对齐 Rockbase SOP）

- 默认 **dry-run**，`--execute` 才真发；SMTP 占位符未填直接拒发
- 节奏：每 2 小时 ≤4 封、日封顶 30（config 可调）
- 首封外链守卫：新联系人正文含 `http(s)://` 直接拦（SOP：初次 DM 不带外链）
- 自动追加退订话术；manifest 去重 → 断点续传不重发
- 收信端 api-key 鉴权；`fetch_replies` 自动排除自寄

## 目录

| 文件 | 作用 |
|---|---|
| `mailkit/send.py` | S2 发信器（限速/守卫/manifest） |
| `mailkit/receiver.py` | 自建收信端，mailgofer 兼容 API + SQLite |
| `mailkit/postfix_pipe.py` | Postfix 管道：stdin MIME → /api/inbound |
| `mailkit/fetch_replies.py` | 轮询收信端 → S3 格式 CSV/JSON |
| `mailkit/master_sync.py` | replies/sent → master CSV 回填（wave 归因，dry-run 默认） |
| `mailkit/events.py` | 结构化事件日志（JSON 行走 stderr，人读输出走 stdout） |
| `mailkit/fake_smtp.py` | 本机模拟 SMTP 对端（彩排/测试专用，🚫生产） |
| `tests/demo_local_loop.py` | 本机全自动收发彩排 |
| `docs/skills-map.md` | 170 个 skill 与 mailkit 的融合映射（哪个关注点用了哪个 skill） |
| `docs/adr/0001-stdlib-only.md` | ADR：保持纯 stdlib 零第三方依赖 |
| `deploy/postfix-notes.md` | 路线B 服务器部署（DNS/Postfix/systemd） |

## 本机彩排（不碰外网）

一台电脑同时扮演「我们的服务器」和「KOL 外部世界」，全自动跑完
mail1 首触 → KOL 自动回信 → 收件入库 → master 硬归因回填 →
mail2 回信（挂线程头、豁免守卫）→ 二次回信 → mail2 回填 的完整剧本：

```bash
python3 tests/demo_local_loop.py
```

全程 127.0.0.1 + tempfile，跑完自动清理。终态 master 应看到：
A（mail1+mail2 双 replied、Outbound 两个 Message-ID）、B（mail1 replied）、
C（mail1 sent 未回）。这是上线前预演；真部署只差 config 填真值 +
`deploy/postfix-notes.md` 的服务器步骤。

## 待填占位符清单

`smtp.host/username/password/from_addr` · `receiver.api_key` · `receiver.domain`
（`receiver.base_url` 路线A 填 mailgofer 地址、路线B 填 `http://127.0.0.1:8788`）
