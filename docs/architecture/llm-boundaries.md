# LLM Boundary Matrix

**Status:** Proposed target contract
**Date:** 2026-09-23
**Scope:** which Rockbase behaviors require OpenAI SDK semantics, which behaviors must remain deterministic, and which behaviors are hybrid

## Decision rule

A behavior uses the OpenAI SDK when its correctness depends on language, meaning, intent, or visual interpretation that no deterministic rule table can express reliably for real-world text. A behavior stays deterministic when it can be expressed as a finite schema, fixed allow-list, regular expression, lookup table, file-format parser, or state machine.

The SDK is not used for authentication, deduplication, opt-out checks, rate limiting, schedule arithmetic, JSON syntax repair, identifier generation, logging, or routing. LLM output is validated against a fixed schema; the model cannot choose a destination, template code, recipient, policy outcome, or send command.

## Required LLM usage

| Behavior | Why semantic | Allowed output | Deterministic validation after |
|---|---|---|---|
| Reply intent classification (`suggest_reply_templates`) | Paraphrased intent (budget timing, conditional interest, delegation, opt-out, language barrier) escapes keyword lists | `intent` from a fixed allow-list, `confidence` in [0,1], `reason` (≤120 chars) | Validate `intent` against allow-list; map `intent` to local template code; flag `manual_review` when confidence < configured threshold |
| Reply conditions and pricing extraction (`run_part2_llm_batch`) | Reply text mixes business terms, currencies, dates, qualifiers | Structured pricing record with platform, basis, values, `[effective]`/`[reference]` labels | Validate required keys, value formats, platform allow-list, ordering rules; reject and queue for human review on schema failure |
| Reply summary for follow-up master fields (`master_sync` summary) | Distilled business meaning (interested, declined, asked for samples, requested terms) | `summary`, `conditions`, `next_action`, `language`, `confidence` | Length bounds, no email addresses/URLs/phones leaking, allow-listed intent/next_action; fallback to bounded preview |
| Multimodal screenshot interpretation (`ag_ocr_sync` `--ocr-engine llm`) | Visual structure (charts, multilingual labels, ambiguous iconography) | Same OCR schema returned by `extract_from_vision` / `extract_from_tesseract` | Re-run deterministic post-processing (regex, country table, percentage pairing, review threshold); dedupe by sha1/dhash |
| Reply language normalization where meaning changes business decision (`translation_utils`) | Business terms, politeness cues, conditional phrasing | Translated text suitable for downstream evidence layer | Spot-check length ratio; never feed back into template routing without human review |

## Hybrid: deterministic first, LLM on demand

| Behavior | Deterministic path | LLM escalation | Trigger |
|---|---|---|---|
| OCR (`auto` engine) | Native macOS Vision + tesseract post-processing | Multimodal LLM | Platform supports native Vision? Otherwise key configured? Otherwise escalate |
| Reply summary (`master_sync`) | Bounded body excerpt (160 chars) labeled `manual_review` and `preview` | Structured summary | Worker configured to enable LLM |
| Reply intent (`suggest_reply_templates`) | Existing keyword classifier (`detect_intent`) | Structured intent | OpenAI SDK client not configured OR call fails OR output fails schema |

## Forbidden in current scope

| Behavior | Reason |
|---|---|
| Local JSON repair in `run_part2_llm_batch` | Deterministic parser (`json` + bounded extraction) handles trailing commas, fenced JSON, surrounding prose; second LLM call is pure cost |
| Reply synchronization, dedupe, ID matching | Pure protocol and identifier arithmetic |
| Master CSV serialization | CSV is a finite format |
| Approval gate evaluation | Compute node + file existence |
| Sending or scheduling outbound email | Compliance; opt-out; rate limit |
| Translation of operational logs, IDs, or fixed product terms | Lossy and unnecessary |
| OCR deterministic post-processing (regex, country table, percentage pairing) | Auditable and predictable |

## LLM call hygiene

- Validate every response against a fixed schema before use; reject non-conforming responses into `manual_review`.
- Cap input size and reject when over budget; log the rejection reason.
- Time out aggressively (5–30 s depending on call type); treat timeout as `manual_review`, not silent retry.
- Treat untrusted text (reply body, OCR payload, summary source) as data, never as instructions; delimit it inside the user message.
- Forbid the model from choosing destination, recipient, send flag, or template code.
- Never embed credentials in prompts; redact local LLM keys, Gmail tokens, and other secrets before logging.
- Cache by stable input hash for deterministic prompts; never cache summary or pricing extraction (reply bodies change).

## Configuration

LLM usage is opt-in per pipeline stage. Default values:

- `summary_enabled = false` (deterministic preview only).
- `intent_llm_enabled = true` when an OpenAI SDK client is available; otherwise deterministic.
- `pricing_extraction_enabled = true` in `S3-ag-reply-recovery-sync-v3`.
- `ocr_auto_engine = "llm"` when `OPENAI_API_KEY` is set and platform is non-macOS; otherwise `tesseract`.

## Open architectural questions resolved by default

- The LLM never selects a destination mailbox, a template code, an opt-out outcome, or a send command. Selection remains local and allow-list based.
- A pipeline stage that requires the LLM proceeds with `manual_review` when the call fails; it never blocks the pipeline.
- The orchestrator never attempts the LLM in `--plan` mode; plan-only output stays deterministic and reproducible.

## Decision artifacts (implemented, 2026-09-25)

Stages S1–S5 expose their semantic output as versioned approval artifacts instead of acting directly:

| Stage | Builder | Deterministic ownership (never the model) | Model share |
|---|---|---|---|
| S1 candidates | `rockbase.llm_stage_contracts.build_candidate_artifact` | API pagination, platform identity, URL/status facts, allow-listed fields | entity_type / relevance / confidence / reason |
| S2 Mail1 | `build_mail1_artifact` | recipient and link policy absent from payload entirely | greeting / hook / reason / variant |
| S3 summary | `ReplySummary.to_artifact` | PII redaction, intent allow-list, fallback preview | summary / intent / confidence |
| S4 enrichment | `build_enrichment_artifact` + `apply_approved_artifact` | label allow-list, evidence retention, approved-version check before any write | label values / confidence |
| S5 OCR + brief match | `build_ocr_artifact` / `match_brief_to_master` | review flags, dedupe, row matching after the model, hard exclusions, candidate-set membership | extraction / ranking / explanation |

Contract invariants:

- `pending_action` (`await_console_decision` / `manual_review`) is derived by deterministic code from validation; the model output has no key that can set it.
- Payloads are bounded (allow-listed keys, size caps, redaction before serialization); `raw_hits`, base64 image data, and contact fields never cross the boundary.
- Apply paths require the persisted record to match the approved artifact id and current version; `execute=False` is always a preview.
- Run modes: `review` pauses each decision stage for a Console decision; `auto` advances only non-forbidden stages under a recorded authorization (`RunManager.authorize_auto_mode`). `is_forbidden_auto_action` permanently blocks send execute, master production writes, and queue-building on send/sync stages; opted-out rows never queue in any mode.