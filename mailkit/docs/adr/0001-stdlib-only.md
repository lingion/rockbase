# ADR-0001: mailkit 保持纯 stdlib 零第三方依赖

状态: 已采纳 · 日期: 2026-09-30

## 背景

mailkit 跑在公司服务器与本机彩排环境。收发链路涉及凭据与客户邮件,
依赖树越长,供应链面越大,服务器上部署/排障也越重。

## 决策

只依赖 Python 标准库(smtplib/sqlite3/http.server/email/json 等)。
假 SMTP、HTTP 收件端、MIME 解析全部自写,配离线 smoke 覆盖。

## 后果

- ✅ 服务器 pip install 即可跑,无版本漂移;审计=读 diff,不用审依赖链
- ✅ smoke 离线全绿,CI 只要 setup-python
- ⚠️ 想上 DKIM 签名/SPF 校验时,标准库没有 → 届时立新 ADR 评估
  (dkimpy 单依赖 + 锁 hash)再引入,🚫顺手加
