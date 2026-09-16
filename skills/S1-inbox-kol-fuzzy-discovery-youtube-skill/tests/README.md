# Validation Scenarios

- YouTube `content-first` multi-query hot-content search returns video rows with creator evidence.
- YouTube `L1` emits one unified table with `row_type = content` and `row_type = creator_summary`.
- Multiple matched videos from one channel aggregate into one creator row.
- Missing or `NA` `channel_id` falls back to a deterministic `creator_handle`.
- `view_count < 1000` rows are marked as not eligible for `L2`.
- YouTube `account-first` can derive shortlist from channel keywords or seed channels.
- Missing `YOUTUBE_API_KEY` does not break the workflow because discover supplement is optional.
- Layer2 can still produce a sortable enriched table without `YOUTUBE_API_KEY`.
- The downstream L2/L3/S2 table shape remains compatible with the shared contract.
