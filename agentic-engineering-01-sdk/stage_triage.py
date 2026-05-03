"""Stage 2 - Triage (CONDITIONAL workflow + HITL).

Three steps, each in its own isolated session:
1. Classifier agent labels the ticket as one of:
   network | account | software | hardware | security | other
2. Human-in-the-loop confirmation via ask_user_question - the user can accept
   the proposed category or override (incl. typing 'Other').
3. Branching dispatch: a first-responder agent specialised for the confirmed
   category produces a quick first-line read.

This mirrors the conditional pattern from
5_Claude_Agent_SDK/python/3_workflows/3_conditional_workflow.py - extended
with a real HITL gate before the branch is taken.
"""

import re

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

from hitl import ask_user_question

MODEL = "sonnet"

CATEGORIES = ["network", "account", "software", "hardware", "security", "other"]

FIRST_RESPONDER_PROMPTS = {
    "network": (
        "You are an L1 network technician. Given the ticket and intake dossier, "
        "give a one-paragraph first-line read: most likely network cause, what "
        "you'd verify first. No fixes yet."
    ),
    "account": (
        "You are an L1 account/identity technician. Given the ticket and intake "
        "dossier, give a one-paragraph first-line read: most likely account or "
        "auth cause, what you'd verify first. No fixes yet."
    ),
    "software": (
        "You are an L1 endpoint/software technician. Given the ticket and intake "
        "dossier, give a one-paragraph first-line read: most likely "
        "software/endpoint cause, what you'd verify first. No fixes yet."
    ),
    "hardware": (
        "You are an L1 hardware technician. Given the ticket and intake dossier, "
        "give a one-paragraph first-line read: most likely hardware cause, "
        "what you'd verify first. No fixes yet."
    ),
    "security": (
        "You are an L1 security analyst. Given the ticket and intake dossier, "
        "flag any indicators that warrant SOC attention and give a one-paragraph "
        "first-line read. No fixes yet."
    ),
    "other": (
        "You are a generalist L1 technician. Give a one-paragraph first-line "
        "read of this ticket and what you'd verify first. No fixes yet."
    ),
}


async def _run_agent(name: str, system_prompt: str, prompt: str) -> str:
    options = ClaudeAgentOptions(model=MODEL, system_prompt=system_prompt)
    chunks: list[str] = []
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


async def _classify(ticket_text: str, dossier: str) -> str:
    """Classifier returns one CATEGORIES value parsed from the response."""
    raw = await _run_agent(
        name="classifier",
        system_prompt=(
            "You are a ticket classifier. Categorise the ticket as exactly one of: "
            f"{', '.join(CATEGORIES)}. Start your response with 'CATEGORY: <value>' "
            "on a single line, then a brief one-sentence justification. Do not "
            "invent categories."
        ),
        prompt=f"Ticket:\n{ticket_text}\n\nIntake dossier:\n{dossier}",
    )
    print("\n--- CLASSIFIER OUTPUT ---")
    print(raw)
    m = re.search(r"CATEGORY:\s*([A-Za-z]+)", raw)
    cat = (m.group(1).lower() if m else "other").strip()
    return cat if cat in CATEGORIES else "other"


def _confirmation_options(detected: str) -> list[str]:
    """Build a 4-item options list: detected first, then 3 alternatives."""
    rest = [c for c in CATEGORIES if c != detected and c != "other"]
    rest = rest[:3]
    return [detected, *rest]


async def run_triage(ticket_text: str, dossier: str) -> dict:
    """Classify -> HITL confirm -> conditional first-line response."""
    print("\n" + "=" * 72)
    print("STAGE 2: TRIAGE  [CONDITIONAL workflow + HITL]")
    print("=" * 72)

    detected = await _classify(ticket_text, dossier)
    print(f"\nDetected category: {detected}")

    answer = ask_user_question(
        f"I classified this ticket as '{detected}'. Confirm or override?",
        _confirmation_options(detected),
    )
    chosen_raw = answer.get("answer", detected)
    chosen = chosen_raw.lower().strip()
    if chosen not in CATEGORIES:
        print(f"  '{chosen_raw}' is not a known category; falling back to 'other'.")
        chosen = "other"
    print(f"  Confirmed category: {chosen}")

    print(f"\nDispatching to '{chosen}' first-responder...")
    first_response = await _run_agent(
        name=f"first-responder-{chosen}",
        system_prompt=FIRST_RESPONDER_PROMPTS[chosen],
        prompt=f"Ticket:\n{ticket_text}\n\nIntake dossier:\n{dossier}",
    )

    print("\n--- FIRST-RESPONDER READ ---")
    print(first_response)

    return {"category": chosen, "first_response": first_response}
