"""Stage 5 - Resolve (LOOP workflow + HITL).

Iterative refinement loop where the human user is the evaluator. Each turn:
1. proposer agent drafts a step-by-step fix grounded in the diagnosis
2. ask_user_question polls the user: did it work?
3. If yes, exit. Otherwise feed the user's feedback back into the proposer.

Max 3 iterations - we stop and escalate-via-final-status rather than loop
forever. The reference pattern uses an LLM evaluator
(5_Claude_Agent_SDK/python/3_workflows/4_loop_workflow.py); we substitute the
user, which is more honest for a helpdesk demo.
"""

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from hitl import ask_user_question
from mcp_server import TOOL_SEARCH_KB, make_helpdesk_server

MODEL = "sonnet"
MAX_ITERATIONS = 3


async def _propose_fix(
    ticket_text: str,
    diagnosis: str,
    review: str,
    prior_attempt: str | None,
    user_feedback: str | None,
    iteration: int,
) -> str:
    """Run the proposer agent, optionally with feedback from the previous turn."""
    print(f"\n--- proposer turn {iteration}/{MAX_ITERATIONS} ---")

    system_prompt = (
        "You are an L2 helpdesk engineer producing a remediation plan for the "
        "user. Output a SHORT numbered list of concrete steps the user can take "
        "right now. Reference the KB if it helps (you have search_kb available). "
        "Do not propose anything that requires admin escalation in the first "
        "round. Keep it under 120 words."
    )

    if prior_attempt and user_feedback:
        user_prompt = (
            f"Ticket:\n{ticket_text}\n\nDiagnosis:\n{diagnosis}\n\n"
            f"Peer review:\n{review}\n\n"
            f"Previous attempt that did NOT resolve the issue:\n{prior_attempt}\n\n"
            f"User feedback after trying it:\n{user_feedback}\n\n"
            f"Produce a refined plan that addresses the feedback."
        )
    else:
        user_prompt = (
            f"Ticket:\n{ticket_text}\n\nDiagnosis:\n{diagnosis}\n\n"
            f"Peer review:\n{review}\n\n"
            f"Produce the first remediation plan."
        )

    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=system_prompt,
        mcp_servers={"helpdesk": make_helpdesk_server()},
        allowed_tools=[TOOL_SEARCH_KB],
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
                    print(f"  [proposer] done (cost ${msg.total_cost_usd:.4f})")
    return "\n".join(chunks).strip()


async def run_resolve(ticket_text: str, diagnosis: str, review: str) -> dict:
    """Loop until the user confirms the fix works or MAX_ITERATIONS hit."""
    print("\n" + "=" * 72)
    print("STAGE 5: RESOLVE  [LOOP workflow + HITL]")
    print("=" * 72)

    prior_attempt: str | None = None
    user_feedback: str | None = None
    final_status: str = "unresolved"
    last_plan: str = ""

    for i in range(1, MAX_ITERATIONS + 1):
        plan = await _propose_fix(
            ticket_text, diagnosis, review, prior_attempt, user_feedback, i
        )
        last_plan = plan
        print("\n--- PROPOSED FIX ---")
        print(plan)

        answer = ask_user_question(
            "Try the steps above. Did this resolve your issue?",
            [
                "Yes - resolved",
                "No - same problem",
                "Partially - some progress",
            ],
        )
        choice = answer.get("answer", "")
        source = answer.get("source", "option")
        print(f"  user reply: {choice} (source={source})")

        if choice == "Yes - resolved":
            final_status = "resolved"
            break

        prior_attempt = plan
        user_feedback = choice if source == "other" else f"User said: {choice}"

        if i == MAX_ITERATIONS:
            final_status = "exhausted-max-iterations"
            break

    return {
        "status": final_status,
        "iterations_used": i,
        "final_plan": last_plan,
        "user_last_feedback": user_feedback or "n/a",
    }
