# Operator Requirements

| Requirement | Needed For | Priority | Owner | Notes |
| --- | --- | --- | --- | --- |
| `yt-dlp` in `PATH` | `content-first search` | high | local env | Main runnable path |
| `YOUTUBE_API_KEY` | `L2` channel/profile enrichment | high | user | Primary metadata path for subscriber count / description / video count |
| channel metadata access strategy | `account-first` | medium | implementation | Can start from search result payloads |
| `scrapecreator` fallback access | `L2` contact/profile fallback | medium | implementation + user | Will later read from shared secrets env symlink |

Rule:

- If `YOUTUBE_API_KEY` is missing, the main workflow should still run unchanged.
- But `L2` quality will be materially weaker without `YOUTUBE_API_KEY`.
- Setup guide: `docs/youtube-api-setup.md`
