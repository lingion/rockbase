# NOW

## Current Goal
Maintain a lightweight live project snapshot for Social Agency so work can resume cleanly after context loss, project switching, or compacting.

## Current State
The project now has a dedicated live snapshot file in `.agent/NOW.md`, a matching template in `.agent/templates/NOW.template.md`, and a `NOW Context Protocol` section in `AGENTS.md`. The lightweight layer between always-on rules and formal handoff documents is now in place.

## Key Files
- `AGENTS.md` - Project-level rules, SOP, path conventions, and handoff protocol.
- `.agent/templates/NOW.template.md` - Skeleton for rewriting the live snapshot.
- `.agent/NOW.md` - Current live project state snapshot.
- `workbench/handoff/` - Durable handoff artifacts for formal transfer points.

## Decisions Made
- `NOW.md` lives in `.agent/`, not in `workbench/`.
- `workbench/` remains the home for dated outputs and formal handoff artifacts.
- The command surface is intentionally minimal: use `run now`.
- `NOW.md` should be rewritten in full instead of appended like a log.

## Open Loops
- Decide how broadly to replicate the `run now` section across other project `AGENTS.md` files.
- Optionally add a formal handoff helper later, but not in the first version.
- Test the `run now` wording in normal project use and tighten the protocol if it feels too verbose.

## Next 3 Actions
1. Reuse this same pattern in other projects that need lightweight resume support.
2. Test `run now` during a real task switch and see whether the rewritten snapshot is concise enough.
3. If needed, add one project-specific extra section without changing the core structure.

## Resume Point
Start by reading `AGENTS.md` for project rules, then open `.agent/NOW.md` for the live snapshot. If a durable checkpoint is needed, review the latest file in `workbench/handoff/` after reading the live snapshot.
