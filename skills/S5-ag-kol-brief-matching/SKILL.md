---
name: ag-kol-brief-matching
description: Use this skill when the user provides a client briefing, campaign brief, discovery analysis, or matching request and wants a KOL matching package. This skill turns a brief plus one or more Master CSV files into a client-facing matching strategy MD and/or a full-field candidate CSV shortlist. It should also be used when the user asks to start the KOL matching workflow or generate a 20-30 person influencer list. Tag production belongs to S4; this skill consumes existing tags for matching.
---

# KOL Brief Matching

Use this skill when the user gives a brief or similar document and wants you to produce:

- a client-facing KOL matching strategy MD
- a filtered candidate CSV that preserves all original fields from the chosen Master
- or both

Default delivery assumption:

- if the user asks to “提取 20/30/40 个名单”, “match 一批达人”, or “生成 shortlist”, you should treat that as requiring both:
  - a client-facing `P4` strategy MD
  - a standalone shortlist CSV
- do not stop at the MD unless the user explicitly says they only want text

## What this skill expects

Minimum inputs:

- one brief / briefing / analysis document
- one or more Master CSV files

Recommended local references:

- `references/kol_matching_client_report_sop.md`

Read them progressively:

1. Read `references/kol_matching_client_report_sop.md` before writing the client-facing MD
2. Treat existing Master tag fields as already-produced inputs from `S4`
3. If the Master lacks usable `tag_*` fields or `账号类目标签`/`账号简介`, switch back to `S4` enrichment first rather than rebuilding the tag system here

## Before executing, ask exactly these things

Ask the user:

1. Output path: where should the results be written?
2. Output scope: strategy MD, candidate CSV, or both?

Defaults if the user does not specify:

- output scope: both
- shortlist size: 30

If the user names a target project folder but does not specify separate filenames:

- write the strategy MD into that project folder as the `P4` document
- write the shortlist CSV into that same project folder as a standalone file

## Default operating assumptions

- Prefer the most complete tagged Master as the main pool
- If two Masters are available, inspect both before choosing the main pool
- Preserve all original fields in exported CSV
- Do not rewrite raw numeric fields unless explicitly requested
- Client-facing MD should be concise and suitable for reporting, not an internal reasoning dump

CSV schema rule:

- shortlist CSV must copy the full Master header and all original columns exactly
- shortlist CSV may only reduce rows, never reduce columns
- do not export a “presentation schema” CSV unless the user explicitly asks for a reduced version

## Workflow

### Step 1. Understand the brief first

Extract:

- product definition
- target audience
- required demo or usage flow
- preferred platforms
- preferred language and market
- explicit exclusions
- narrative need: brand, conversion, education, or workflow fit

Convert the brief into:

- `must_have`
- `should_have`
- `must_avoid`
- `preferred_platform`
- `preferred_market`
- `narrative_need`

### Step 2. Read the Master as-is

Read the chosen Master and confirm whether `tag_*` fields and key summary fields are already present and usable.

Check:

- whether tags already exist
- whether platform / language / country are standardized
- which Master is more complete

### Step 3. Translate the brief into tag requirements

At minimum, map the brief into:

- `tag_topics`
- `tag_scenarios`
- `tag_audience`
- `tag_platform_fit`
- `tag_market`
- `tag_risk`
- `tag_narrative`

### Step 4. Filter, rank, and review

Hard filter first:

- platform mismatch
- language mismatch
- market mismatch
- obvious risk conflicts
- severe data quality issues

Then rank by:

1. topic fit
2. scenario fit
3. audience fit
4. platform and market fit
5. risk level
6. commercial usability

If no formal scoring script is available, use a transparent model-based ranking grounded in the existing tag system and original Master fields.

### Step 5. Produce outputs

If strategy MD is required:

- read `references/kol_matching_client_report_sop.md`
- write a concise client-facing matching rationale
- avoid internal budget, quota, and database language

If CSV is required:

- export the final shortlist
- keep all original columns
- include existing tag columns
- default to Top 30 unless the user specifies another size
- the CSV should be written as a standalone deliverable, not embedded only inside the MD
- if the shortlist comes from one Master, preserve that Master's exact header order
- if tie buckets are relevant to selection logic, use them for internal filtering but do not expose `T0/T1/T2/Master` language in the client-facing narrative

## Output expectations

### Strategy MD

Should explain:

- matching approach
- screening basis
- key dimensions of fit

It should be suitable for client reporting.

### Candidate CSV

Must:

- preserve all original fields
- only narrow rows, not columns
- remain easy for downstream manual editing
- be written into the user-specified output folder by default
- exist even if the MD already contains a shortlist table

Recommended default naming:

- strategy MD: `P4_<Project>_KOL_Matching_Strategy.md`
- shortlist CSV: `P4_<Project>_KOL_Shortlist_<N>.csv`

## Red lines

Do not:

- skip brief understanding and jump straight to keyword filtering
- write budget, bargain logic, or internal shortlist mechanics into the client-facing MD
- strip the CSV down to a reduced schema
- alter raw numeric fields unless requested
- assume a shortlist table inside the MD is a substitute for the standalone CSV

## Portability rule

All bundled references in this skill are accessed with relative paths from this folder. If the entire skill folder is moved, the internal reference structure should still work.
