# WF-Codex-Chrome

## Goal
- Use the Codex `Chrome` plugin to scan the target X community in `Top` view month by month.
- Capture creators whose posts exceed 1,000 views and whose accounts also exceed 1,000 followers.
- Keep only accounts with a visible DM/contact path on X.
- Output a full-field CSV using the existing S2 schema, filling the fields that can be reliably collected from X.

## Input
- Community URL: `https://x.com/i/communities/1895831432443924780`
- Output root: `deliverables/{YYYY-MM-DD}/`
- Reference schema: `deliverables/2026-04-20/【S2_cold】2026-04-20_x_kol_S2_merged_final.csv`

## Browser Procedure
1. Open the community URL through the `Chrome` plugin.
2. Switch to `Top` ranking.
3. Scroll downward continuously.
4. Treat each visible month separator as one collection unit.
5. Inside each month unit, inspect posts with visible view counts.
6. Keep only posts with `views > 1000`.
7. Open the author profile from the candidate post.
8. Pass only profiles with `followers >= 1000`.
9. Check whether a DM/contact entry is available on profile or post context.
10. If DM/contact path is not visible, skip the profile.
11. Capture profile and sample-post fields.
12. Append one row per qualified creator to the dated CSV.

## Field Fill Policy
- Preserve the full header from the reference CSV.
- Fill directly when available:
  - `账号ID`
  - `频道/作者名称`
  - `平台`
  - `账号链接`
  - `语言`
  - `粉丝数`
  - `账号简介__平台抓取`
  - `Sample Content`
  - `外链__平台抓取`
- Leave unsupported fields blank rather than guessing.
- Derive `语言` from the sampled tweet language.
- Use `X` as the platform value.

## Output Naming
- Dated folder: `deliverables/{YYYY-MM-DD}/`
- Main CSV: `【S2_cold】{YYYY-MM-DD}_x_kol_S2_merged_final.csv`

## Quality Rules
- Do not invent contact information.
- Do not keep creators below the follower threshold.
- Do not keep posts below the view threshold.
- If multiple qualifying posts belong to the same creator, keep one creator row and prefer the strongest or latest usable sample.
