Layer2 is the enrichment layer.

Current runnable baseline:

- `Scweet user-info` enrichment for profile basics
- `ScrapeCreators` env + client scaffolding for cross-platform enrichment patterns

Planned next providers:

- `ScrapeCreators` X-specific endpoint wiring
- `OmniChrome` fallback

Notes:

- Skill root `.env` should be a symlink to the shared secret env file.
- `scrapecreators_client.py` carries the reusable env-loading and field-normalization helpers migrated from `ag-kol-scraper`.
