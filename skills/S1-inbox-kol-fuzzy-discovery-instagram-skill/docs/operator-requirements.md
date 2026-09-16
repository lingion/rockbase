# Operator Requirements

| Requirement | Needed For | Priority | Owner | Notes |
| --- | --- | --- | --- | --- |
| `SCRAPECREATORS_API_KEY` | `content-first` / `account-first` | high | global env | 当前默认主路径 |
| `instaloader` in `PATH` | optional supplement | medium | local env | 只用于 session-backed 补充线 |
| valid session file | hashtag / profile collection | medium | user | Instaloader 补充线 |
| browser/session assisted fallback | escalation | medium | implementation | Only after `instaloader` path is validated |

Rule:

- Instagram v1 should not claim platform-wide trending access when only hashtag/profile routes are available.
- Real validation on `2026-04-10` shows: `ScrapeCreators reels search` is the most stable `content-first` path.
- Real validation on `2026-04-10` also shows: `Instaloader` can reuse cookies-derived session, but hashtag/profile stability still weaker than `ScrapeCreators`.
- Therefore current default L1 should be `ScrapeCreators reels search`, while `Instaloader` stays as a session-backed optional path.
