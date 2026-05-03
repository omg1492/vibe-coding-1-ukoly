"""Stage 1 - Intake (PARALLEL workflow, fan-out / fan-in).

Four data-gatherer agents run concurrently against the helpdesk MCP tools:
- kb-searcher        -> search_kb
- similar-finder     -> find_similar_tickets
- status-checker     -> check_system_status
- history-fetcher    -> lookup_user_history

Their outputs are aggregated by a fifth synthesis agent that writes a single
"intake briefing" used by the rest of the pipeline.

This is the canonical fan-out/fan-in pattern from
5_Claude_Agent_SDK/python/3_workflows/2_parallel_workflow.py - tools added.
"""

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from mcp_server import (
    TOOL_CHECK_STATUS,
    TOOL_FIND_SIMILAR,
    TOOL_SEARCH_KB,
    TOOL_USER_HISTORY,
    make_helpdesk_server,
)

MODEL = "sonnet"


async def _run_gatherer(
    name: str,
    system_prompt: str,
    user_prompt: str,
    allowed_tool: str,
) -> tuple[str, str]:
    """Run one data-gatherer agent in an isolated session.

    Each agent gets exactly the one helpdesk tool it needs.
    """
    print(f"  [{name}] starting...")
    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system_prompt,
        mcp_servers={"helpdesk": make_helpdesk_server()},
        allowed_tools=[allowed_tool],
    )

    chunks: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(user_prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(msg, ResultMessage):
                if msg.total_cost_usd:
                    print(f"  [{name}] done (cost ${msg.total_cost_usd:.4f})")

    return name, "\n".join(chunks).strip()


async def run_intake(ticket_text: str, user_id: str) -> str:
    """Fan-out 4 gatherer agents in parallel, then fan-in into a briefing."""
    print("\n" + "=" * 72)
    print("STAGE 1: INTAKE  [PARALLEL workflow]")
    print("=" * 72)
    print(f"Reported ticket: {ticket_text}")
    print(f"User id:         {user_id}")
    print("-" * 72)
    print("Fan-out: 4 gatherers running concurrently")

    gatherers = [
        {
            "name": "kb-searcher",
            "system_prompt": (
                "You are a KB search specialist. Use the search_kb tool with concise "
                "keyword queries derived from the ticket. Report at most 3 KB articles "
                "you think are most relevant, in 1-2 lines each. Do not speculate."
            ),
            "prompt": (
                f"Find KB articles relevant to this user-reported issue:\n\n{ticket_text}"
            ),
            "tool": TOOL_SEARCH_KB,
        },
        {
            "name": "similar-finder",
            "system_prompt": (
                "You are a historical-ticket investigator. Use find_similar_tickets to "
                "look up past incidents that resemble the current one. Report at most "
                "3 hits with their resolutions, briefly."
            ),
            "prompt": (
                f"Find historical tickets similar to this issue:\n\n{ticket_text}"
            ),
            "tool": TOOL_FIND_SIMILAR,
        },
        {
            "name": "status-checker",
            "system_prompt": (
                "You are a service-status checker. Identify the internal services that "
                "appear in the ticket (VPN, Email, Auth, etc.) and call "
                "check_system_status for each one. Summarise: any degraded service "
                "that could explain the issue?"
            ),
            "prompt": (
                f"Check system status for any internal services implicated by this "
                f"ticket:\n\n{ticket_text}"
            ),
            "tool": TOOL_CHECK_STATUS,
        },
        {
            "name": "history-fetcher",
            "system_prompt": (
                "You are a user-history specialist. Call lookup_user_history exactly "
                "once with the supplied user id and summarise any patterns relevant to "
                "the current issue."
            ),
            "prompt": (
                f"Pull recent ticket history for user_id='{user_id}'. The current issue "
                f"is:\n\n{ticket_text}"
            ),
            "tool": TOOL_USER_HISTORY,
        },
    ]

    results: list[tuple[str, str]] = []

    async with anyio.create_task_group() as tg:
        async def runner(spec: dict) -> None:
            r = await _run_gatherer(
                spec["name"], spec["system_prompt"], spec["prompt"], spec["tool"]
            )
            results.append(r)

        for spec in gatherers:
            tg.start_soon(runner, spec)

    print("-" * 72)
    print("Fan-in: synthesising briefing")

    aggregated = "\n\n".join(f"### {name}\n{text}" for name, text in results)

    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=(
            "You are an intake analyst. You will receive raw findings from four "
            "parallel specialists. Write a SHORT briefing (under 200 words) that the "
            "downstream triage and diagnosis stages can use. Lead with the most "
            "load-bearing facts (degraded services, near-identical past tickets). "
            "Do NOT propose a fix - that is for later stages."
        ),
    )

    briefing_chunks: list[str] = []
    async with ClaudeSDKClient(options=options) as client:
        await client.query(
            f"Original ticket:\n{ticket_text}\n\nUser id: {user_id}\n\n"
            f"Findings from parallel specialists:\n{aggregated}\n\n"
            f"Write the intake briefing."
        )
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        briefing_chunks.append(block.text)
            elif isinstance(msg, ResultMessage):
                if msg.total_cost_usd:
                    print(f"  [aggregator] done (cost ${msg.total_cost_usd:.4f})")

    briefing = "\n".join(briefing_chunks).strip()
    print("\n--- INTAKE BRIEFING ---")
    print(briefing)
    return briefing
