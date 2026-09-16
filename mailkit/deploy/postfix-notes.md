# 公司服务器收信部署（路线B：不用 Cloudflare）

原理：Postfix 收 25 端口 → `transport_maps` 把整个域的投递交给管道 →
`mailkit-pipe` 包装脚本把信封收件人 + MIME 灌进本机 receiver（mailgofer 兼容 API）。

## 0. 服务器前提（先核对，缺一样都跑不通）

- [ ] 入站 25 端口开放（云安全组 + 防火墙 `firewall-cmd`/`ufw`）
- [ ] Python ≥ 3.9（mailkit 纯 stdlib，无需 pip）
- [ ] 本仓库放到服务器，如 `/opt/rockbase-mailkit`
- [ ] 专用系统用户：`useradd -r -m mailkit`

## 1. DNS

```
MX   yourcompany.example.       → mail.yourcompany.example. (10)
A    mail.yourcompany.example.  → <服务器公网IP>
PTR  <公网IP>                    → mail.yourcompany.example.   ← 找 ISP/云厂商开
```

## 2. Postfix：transport_maps 整域进管道

`/etc/postfix/main.cf` 确认/追加：

```ini
myhostname = mail.yourcompany.example
inet_interfaces = all
transport_maps = hash:/etc/postfix/transport
```

`/etc/postfix/transport`（整域接管，**不做**别名改写，避免 alias loop）：

```ini
yourcompany.example    mailkit-pipe:
```

```bash
postmap /etc/postfix/transport
```

`/etc/postfix/master.cf` 追加（pipe 守护进程，`%u %d` = 信封收件人）：

```ini
mailkit-pipe  unix  -  n  n  0  -  pipe
  flags=Fq user=mailkit argv=/usr/local/bin/mailkit-pipe %u %d
```

包装脚本 `/usr/local/bin/mailkit-pipe`（stdin 由 pipe 守护进程喂 MIME）：

```bash
#!/bin/sh
export PYTHONPATH=/opt/rockbase-mailkit
export MAILKIT_RECEIVER_API_KEY='<RECEIVER_API_KEY>'
exec /usr/bin/python3 -m mailkit.postfix_pipe \
  --url http://127.0.0.1:8788 \
  --rcpt-user "$1" --rcpt-domain "$2"
```

```bash
chmod 755 /usr/local/bin/mailkit-pipe
systemctl reload postfix
```

## 3. receiver 常驻（systemd）

`/etc/systemd/system/mailkit-receiver.service`：

```ini
[Unit]
Description=rockbase-mailkit receiver
After=network.target

[Service]
User=mailkit
WorkingDirectory=/opt/rockbase-mailkit
ExecStart=/usr/bin/python3 -m mailkit.receiver \
  --db /var/lib/mailkit/mailkit.db --port 8788 --host 127.0.0.1
Environment=MAILKIT_RECEIVER_API_KEY=<RECEIVER_API_KEY>
Restart=always
StateDirectory=mailkit

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now mailkit-receiver
```

## 4. 验证（从任意外部邮箱发信）

```bash
# 发到任意地址@yourcompany.example（catch-all，无需预先建号），然后：
curl -s -H "x-api-key: <KEY>" \
  "http://127.0.0.1:8788/api/emails?email=anything@yourcompany.example" \
  | python3 -m json.tool

# 排障
journalctl -u mailkit-receiver -f
postqueue -p        # 有 deferred 就是管道没接住
```

## 5. 发信侧 DNS（公司域若已正常发信则多半已齐）

```
SPF:   v=spf1 mx ip4:<服务器IP> -all
DKIM:  opendkim 生成，公钥进 TXT
DMARC: _dmarc  TXT: v=DMARC1; p=quarantine; rua=mailto:dmarc@yourcompany.example
```

## 与路线A（Cloudflare + mailgofer 原版）的取舍

| | A: Cloudflare Email Routing | B: 公司服务器自建 |
|---|---|---|
| 域名托管 | 必须迁到 Cloudflare NS | 不动 |
| 运维 | 零 | Postfix + receiver 自己养 |
| 数据位置 | Cloudflare D1 | 本机 SQLite |
| API 兼容 | mailgofer 原版 | 本仓库 receiver.py（同契约） |

`fetch_replies.py` 对 A/B 通用，只改 `receiver.base_url` / `api_key`。
