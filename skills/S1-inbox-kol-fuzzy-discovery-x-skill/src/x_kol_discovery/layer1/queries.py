from __future__ import annotations

from x_kol_discovery.config import SearchQuery


DEFAULT_OPENCLAW_QUERIES: list[SearchQuery] = [
    SearchQuery(
        name="openclaw_core_ai",
        query='"OpenClaw" (AI OR "AI agents" OR automation OR "developer tools") -crypto -trader -airdrop',
    ),
    SearchQuery(
        name="openclaw_workflow",
        query='"OpenClaw" (workflow OR productivity OR coding OR devtools OR build) -crypto -trader -airdrop',
    ),
    SearchQuery(
        name="openclaw_roles",
        query='"OpenClaw" (builder OR founder OR engineer OR researcher OR creator) -crypto -trader -airdrop',
    ),
    SearchQuery(
        name="openclaw_content",
        query='"OpenClaw" (tutorial OR demo OR review OR usecase OR walkthrough) -crypto -trader -airdrop',
    ),
    SearchQuery(
        name="openclaw_product",
        query='"OpenClaw" (startup OR SaaS OR product OR team OR launch) -crypto -trader -airdrop',
    ),
    SearchQuery(
        name="openclaw_agentic",
        query='"OpenClaw" (agentic OR copilot OR copilots OR assistant OR assistants OR operators) -crypto -trader -airdrop',
    ),
]

