# rockbase-mailkit

Rockbase S2/S3 邮件链路适配器：**发信走公司 SMTP，收信走 mailgofer 兼容 API**。
替代原 Gmail OAuth 草稿链路，人工干预点归零。纯 Python stdlib，零第三方依赖。

```
S2 发信:  CSV → mailkit.send → 公司 SMTP (默认 dry-run + 限速 + 断点续传)
S3 收信:  KOL 回信 → [A] Cloudflare Email Routing → mailgofer
                  → [B] Postfix catch-all → postfix_pipe → receiver.py(SQLite)
S3 回收:  mailkit.fetch_replies → replies_YYYY-MM-DD.csv/json → S3 流水线
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
```

CSV 格式：`email,name,subject,body`，正文可用 `{name}`。

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
| `deploy/postfix-notes.md` | 路线B 服务器部署（DNS/Postfix/systemd） |

## 待填占位符清单

`smtp.host/username/password/from_addr` · `receiver.api_key` · `receiver.domain`
（`receiver.base_url` 路线A 填 mailgofer 地址、路线B 填 `http://127.0.0.1:8788`）
