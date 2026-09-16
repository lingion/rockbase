# Operator Requirements

| Requirement | Needed For | Priority | Owner | Notes |
| --- | --- | --- | --- | --- |
| `TikTokApi` runtime | `content-first` / `account-first` | high | local env | First runtime candidate |
| Playwright browser install | `TikTokApi` | high | local env | Required by wrapper setup |
| `ms_token` or equivalent cookie material | stable search/trending | high | user | Often needed for practical runtime stability |
| skill-local proxy | anti-bot resilience | medium | user / infra | Keep TikTok proxy in skill-local `.env.local`, not in shared global env |
| browser/session fallback | escalation path | medium | implementation | Informed by `MediaCrawler` |

Rule:

- If credentials or session material are missing, the skill must emit a structured blocker with next action.
- Env layering should be:
  1. shared global env symlink for reusable API keys only
  2. skill-local `.env.local` for TikTok-only proxy/session material
  3. skill runtime values override shared values when both exist
- Current locked TikTok proxy target is the Houston node `149.119.188.182:443`; do not add it to the shared global env.
- Default testing rule: use the skill-local static IP by default unless a run explicitly passes `--no-proxy`.
- Current validated proxy protocol for runtime is `http://user:pass@ip:port`, not `https://...` and not `socks5://...`.
