"""Stage 3 - Diagnose (SUPERVISOR multi-agent).

A team of five domain specialists is supervised by an L2 helpdesk lead. The
supervisor uses structured output to decide on each iteration whether to
delegate to a specialist (with a constructed task) or finish with a
consolidated diagnosis.

Specialists have access to the helpdesk MCP tools so they can actually look
things up (KB, similar tickets, system status, user history). Only the
specialists carry tools - the supervisor only routes.

Pattern source: 5_Claude_Agent_SDK/python/2_multi_agent/2_supervisor_pattern.py.
"""

import anyio
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    query,
)

from mcp_server import (
    TOOL_CHECK_STATUS,
    TOOL_FIND_SIMILAR,
    TOOL_SEARCH_KB,
    TOOL_USER_HISTORY,
    make_helpdesk_server,
)

MODEL = "sonnet"
MAX_ITERATIONS = 6
SPECIALIST_TOOLS = [TOOL_SEARCH_KB, TOOL_FIND_SIMILAR, TOOL_CHECK_STATUS, TOOL_USER_HISTORY]

SUPERVISOR_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["delegate", "finish"]},
        "delegate_to": {"type": "string"},
        "task": {"type": "string"},
        "answer": {"type": "string"},
    },
    "required": ["action"],
    "additionalProperties": False,
}


def _build_team() -> dict[str, AgentDefinition]:
    """Five domain specialists. All share the same MCP tool surface."""
    return {
        "network-specialist": AgentDefinition(
            description="Diagnoses network and VPN connectivity issues",
            prompt=(
                "You are a senior network/VPN engineer. Investigate the assigned "
                "task using the tools available to you. Be specific about likely "
                "root cause and what data you used to reach it."
            ),
            tools=SPECIALIST_TOOLS,
            model=MODEL,
        ),
        "account-specialist": AgentDefinition(
            description="Diagnoses account, identity, and 2FA/MFA issues",
            prompt=(
                "You are a senior IAM engineer. Investigate the assigned task. "
                "Distinguish between credential, MFA, lockout, and entitlement causes."
            ),
            tools=SPECIALIST_TOOLS,
            model=MODEL,
        ),
        "software-specialist": AgentDefinition(
            description="Diagnoses endpoint application and software issues",
            prompt=(
                "You are a senior endpoint engineer. Investigate software, OS, and "
                "client-config root causes for the assigned task."
            ),
            tools=SPECIALIST_TOOLS,
            model=MODEL,
        ),
        "hardware-specialist": AgentDefinition(
            description="Diagnoses hardware, peripherals, and device-level issues",
            prompt=(
                "You are a senior hardware/device engineer. Investigate the "
                "assigned task focusing on physical or device-level causes."
            ),
            tools=SPECIALIST_TOOLS,
            model=MODEL,
        ),
        "security-specialist": AgentDefinition(
            description="Investigates security incidents and suspicious activity",
            prompt=(
                "You are a SOC analyst. Investigate the assigned task for "
                "security-relevant indicators (phishing, account takeover, "
                "anomalous logins). Recommend containment if warranted."
            ),
            tools=SPECIALIST_TOOLS,
            model=MODEL,
        ),
    }


async def _run_specialist(name: str, defn: AgentDefinition, task: str) -> str:
    """Run one specialist as an isolated session with helpdesk tools wired."""
    print(f"\n  -> delegating to {name}")
    options = ClaudeAgentOptions(
        model=defn.model,
        system_prompt=defn.prompt,
        mcp_servers={"helpdesk": make_helpdesk_server()},
        allowed_tools=defn.tools or [],
    )

    chunks: list[str] = []
    prompt = (
        f"Your role: {defn.description}\n\n"
        f"Task from supervisor:\n{task}\n\n"
        f"Investigate using the tools you have, then report your findings."
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
            elif isinstance(msg, ResultMessage):
                if msg.total_cost_usd:
                    print(f"  [{name}] done (cost ${msg.total_cost_usd:.4f})")
    return "\n".join(chunks).strip()


async def run_diagnose(
    ticket_text: str, dossier: str, triage: dict
) -> str:
    """Supervisor loop until the supervisor returns action='finish'."""
    print("\n" + "=" * 72)
    print("STAGE 3: DIAGNOSE  [SUPERVISOR multi-agent]")
    print("=" * 72)
    team = _build_team()
    team_info = "\n".join(f"- {name}: {d.description}" for name, d in team.items())
    team_names = ", ".join(team.keys())

    history = (
        f"Original ticket:\n{ticket_text}\n\n"
        f"Intake dossier:\n{dossier}\n\n"
        f"Triage outcome: category='{triage['category']}', first response:\n"
        f"{triage['first_response']}"
    )

    supervisor_prompt_base = (
        "You are an L2 helpdesk lead supervising a team of specialists. Your job "
        "is to consolidate a single, well-grounded diagnosis. On each turn, "
        "decide either to delegate a focused investigation to one specialist, or "
        "to finish if you already have enough.\n\n"
        f"Your team:\n{team_info}\n\n"
        "When you are confident in the root cause, set action='finish' and put "
        "the diagnosis in 'answer' (cause + supporting evidence + suggested "
        "remediation direction)."
    )

    for i in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- supervisor turn {i}/{MAX_ITERATIONS} ---")
        options = ClaudeAgentOptions(
            model=MODEL,
            system_prompt=supervisor_prompt_base,
            output_format={"type": "json_schema", "schema": SUPERVISOR_SCHEMA},
        )
        prompt = (
            f"{history}\n\n"
            f"Decide the next step.\n"
            f"- delegate to one of: {team_names}\n"
            f"- or finish with the consolidated diagnosis."
        )

        decision = None
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(f"  supervisor: {block.text}")
            elif isinstance(msg, ResultMessage):
                if msg.structured_output:
                    decision = msg.structured_output
                if msg.total_cost_usd:
                    print(f"  [supervisor] cost ${msg.total_cost_usd:.4f}")

        if decision is None:
            print("  warning: supervisor returned no structured output, retrying")
            continue

        if decision["action"] == "finish":
            answer = decision.get("answer", "").strip()
            print("\n--- DIAGNOSIS ---")
            print(answer)
            return answer

        target = decision.get("delegate_to", "").strip()
        task = decision.get("task", "").strip()
        if target not in team:
            history += f"\n\nERROR: '{target}' is not on the team. Pick from {team_names}."
            continue

        result = await _run_specialist(target, team[target], task)
        history += f"\n\nDelegated to {target}:\n  task: {task}\n  result:\n{result}"

    print(f"\n  supervisor reached MAX_ITERATIONS={MAX_ITERATIONS} without finishing.")
    return history


if __name__ == "__main__":
    async def _demo():
        await run_diagnose(
            "VPN times out after 2FA",
            "Auth gateway shows degraded; KB-003 and T-1006 are similar.",
            {"category": "network", "first_response": "Likely auth/DNS related."},
        )
    anyio.run(_demo)
