# Skills 融合映射 — 哪个 skill 落在 mailkit 哪里

源:`~/.copilot/skills/`(170 个,自 Claude skill 库复制)。本表记录已融合的关注点,
新会话做相关任务时先按表调 skill,再动手。

| 关注点 | Skill | 落地在 mailkit | 怎么用 |
|---|---|---|---|
| 收件端加固 | `agent-skills-skills-security-and-hardening` | `mailkit/receiver.py`:hmac.compare_digest 防时序侧信道、请求体 10MB 上限(413)、地址 ≤254、nosniff/no-store 头、错误码不外泄内部细节、handler_error 事件 | 改 receiver 任何输入路径前先调该 skill 过 STRIDE |
| 可观测性 | `agent-skills-skills-observability-and-instrumentation` | `mailkit/events.py`:一行一 JSON 事件(stderr),send_ok/send_fail/http_request/inbound_accepted/auth_failed/mime_parse_failed;X-Request-Id 全链路关联 | 排查线上收发问题:`python -m mailkit.receiver ... 2>events.jsonl` 后 grep 事件名 |
| 邮件流 E2E | `qa-skills-skills-email-testing` | `tests/demo_local_loop.py`:唯一收件人、轮询不盲睡(wait_inbox)、断言主题/发件人/线程头而非仅存在性 | 新增收发剧本时按"capture→poll→assert content"三段写 |
| 测试稳定性 | `qa-skills-skills-test-reliability` | `mailkit/fake_smtp.py` socket 15s 超时防挂死;demo 全部轮询;smoke 离线起服不依赖外网 | 套件再出现 flake/挂死先调该 skill 分类根因 |
| CI | `agent-skills-skills-ci-cd-and-automation` | `.github/workflows/ci.yml`:compileall + smoke,push/PR 触发 | 加新测试后确认 ci.yml 覆盖;🚫在 CI 里发真邮件 |
| 零依赖决策 | `documentation-and-adrs` | `docs/adr/0001-stdlib-only.md` | 改依赖前先读;推翻需新 ADR |

## 事件目录(receiver/send stderr)

| 事件 | 字段 | 含义 |
|---|---|---|
| `http_request` | request_id, method, route, status, dur_ms | 每个 API 请求一条 |
| `auth_failed` | request_id, peer | 鉴权失败(含来源 IP) |
| `inbound_accepted` | request_id, to, external_id | 收信落库 |
| `mime_parse_failed` | request_id, error | raw 解析失败 |
| `handler_error` | request_id, route, error | 未预期异常(500) |
| `send_ok` / `send_fail` | to, wave, key, message_id/error, dur_ms | 每封真发一条 |
