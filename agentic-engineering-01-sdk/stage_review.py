"""Stage 4 - Review (SWARM multi-agent).

Three peer reviewers form a swarm with explicit handoff lists. Each one looks
at the diagnosis from its own angle and can either hand off to another peer
or finish with a validated (or revised) diagnosis. There is no hierarchy.

Reviewers:
- engineering-reviewer  - challenges technical correctness
- security-reviewer     - looks for security implications
- impact-reviewer       - assesses urgency / user impact

Pattern source: 5_Claude_Agent_SDK/python/2_multi_agent/3_swarm_pattern.py.
"""

import anyio
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from mcp_server import (
    TOOL_FIND_SIMILAR,
    TOOL_SEARCH_KB,
    make_helpdesk_server,
)

MODEL = "sonnet"
MAX_HANDOFFS = 6
REVIEWER_TOOLS = [TOOL_SEARCH_KB, TOOL_FIND_SIMILAR]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["handoff", "finish"]},
        "handoff_to": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["action", "content"],
    "additionalProperties": False,
}


class _Peer:
    def __init__(self, name: str, defn: AgentDefinition, handoffs: list[str]):
        self.name = name
        self.defn = defn
        self.handoffs = handoffs


def _build_swarm() -> dict[str, _Peer]:
    return {
        "engineering-reviewer": _Peer(
            "engineering-reviewer",
            AgentDefinition(
                description="Senior engineer. Challenges technical correctness of the diagnosis.",
                prompt=(
                    "You are a senior engineer doing peer review of a helpdesk "
                    "diagnosis. Your job is to challenge the technical reasoning. "
                    "If the diagnosis looks solid, hand off to security-reviewer "
                    "for the security angle, or finish if everything checks out."
                ),
                tools=REVIEWER_TOOLS,
                model=MODEL,
            ),
            handoffs=["security-reviewer", "impact-reviewer"],
        ),
        "security-reviewer": _Peer(
            "security-reviewer",
            AgentDefinition(
                description="Security reviewer. Flags security-relevant aspects of the diagnosis.",
                prompt=(
                    "You are a SOC analyst doing peer review. Look at the diagnosis "
                    "for security implications: phishing, account takeover, data "
                    "exposure, missing logging. Hand off to impact-reviewer for "
                    "blast radius, or finish if the diagnosis is acceptable."
                ),
                tools=REVIEWER_TOOLS,
                model=MODEL,
            ),
            handoffs=["impact-reviewer", "engineering-reviewer"],
        ),
        "impact-reviewer": _Peer(
            "impact-reviewer",
            AgentDefinition(
                description="User-impact reviewer. Sizes urgency and blast radius.",
                prompt=(
                    "You are reviewing the helpdesk diagnosis for user impact and "
                    "urgency. Is this affecting one user or many? Should it be "
                    "escalated to a major-incident workflow? You will normally be "
                    "the last reviewer in the swarm and should finish with a final "
                    "validated diagnosis (combine the prior reviewers' concerns)."
                ),
                tools=REVIEWER_TOOLS,
                model=MODEL,
            ),
            handoffs=["engineering-reviewer"],
        ),
    }


async def run_review(ticket_text: str, diagnosis: str) -> str:
    """Swarm loops handing off until one agent action='finish's."""
    print("\n" + "=" * 72)
    print("STAGE 4: REVIEW  [SWARM multi-agent]")
    print("=" * 72)

    swarm = _build_swarm()
    current = "engineering-reviewer"
    history: list[dict[str, str]] = []
    initial_task = (
        f"Original ticket:\n{ticket_text}\n\n"
        f"Diagnosis under review:\n{diagnosis}"
    )

    for i in range(MAX_HANDOFFS):
        peer = swarm[current]
        print(f"\n--- handoff {i + 1}/{MAX_HANDOFFS}: {current} ---")

        prior = "\n\n".join(f"[{h['agent']}]: {h['content']}" for h in history) or "(none yet)"
        handoff_targets = ", ".join(peer.handoffs) if peer.handoffs else "(none, you must finish)"

        prompt = (
            f"You are '{current}', one of three peer reviewers.\n"
            f"Your role: {peer.defn.description}\n\n"
            f"Original task:\n{initial_task}\n\n"
            f"Previous reviewers said:\n{prior}\n\n"
            f"Your handoff options: {handoff_targets}\n\n"
            f"Decide: 'handoff' to one of your options, or 'finish' if review is "
            f"complete. Always include your contribution in 'content'."
        )

        options = ClaudeAgentOptions(
            model=MODEL,
            system_prompt=peer.defn.prompt,
            mcp_servers={"helpdesk": make_helpdesk_server()},
            allowed_tools=peer.defn.tools or [],
            output_format={"type": "json_schema", "schema": RESPONSE_SCHEMA},
        )

        decision = None
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            print(f"  {current}: {block.text}")
                elif isinstance(msg, ResultMessage):
                    if msg.structured_output:
                        decision = msg.structured_output
                    if msg.total_cost_usd:
                        print(f"  [{current}] cost ${msg.total_cost_usd:.4f}")

        if decision is None:
            print(f"  warning: {current} returned no structured output")
            continue

        history.append({"agent": current, "content": decision["content"]})

        if decision["action"] == "finish":
            print(f"\n  {current} finished the review chain.")
            return decision["content"]

        nxt = decision.get("handoff_to", "")
        if nxt not in peer.handoffs:
            print(f"  warning: {nxt!r} is not a valid handoff for {current}")
            continue
        print(f"  >>> handing off to {nxt}")
        current = nxt

    print(f"  swarm reached MAX_HANDOFFS={MAX_HANDOFFS} without finish.")
    return history[-1]["content"] if history else diagnosis


if __name__ == "__main__":
    async def _demo():
        await run_review(
            "VPN timeout after 2FA",
            "Root cause: Auth gateway is degraded; symptom matches T-1006.",
        )
    anyio.run(_demo)
