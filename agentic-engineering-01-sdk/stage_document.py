"""Stage 6 - Document (COLLABORATION multi-agent).

Three equal peer authors run in a fixed sequence, each in its own isolated
ClaudeSDKClient session, output flowing forward:

  kb-writer  ->  technical-reviewer  ->  editor

Each emits structured output {resolved: bool, content: str}. The editor sets
resolved=true to end the chain. After the chain produces the final article
the orchestrator gates publication with a HITL ask_user_question, then calls
the save_kb_article MCP tool itself.

Pattern source: 5_Claude_Agent_SDK/python/2_multi_agent/1_collaboration_pattern.py.
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

from hitl import ask_user_question
from tools import save_kb_article

MODEL = "sonnet"
MAX_ITERATIONS = 6  # cycles through 3 agents up to 2 times if no one resolves

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "resolved": {"type": "boolean"},
        "content": {"type": "string"},
    },
    "required": ["resolved", "content"],
    "additionalProperties": False,
}


def _build_authors() -> list[tuple[str, AgentDefinition]]:
    """Three peer authors. Order matters: writer, reviewer, editor."""
    return [
        (
            "kb-writer",
            AgentDefinition(
                description="Drafts the KB article from the resolved ticket",
                prompt=(
                    "You are a KB writer. From the supplied ticket, diagnosis, "
                    "and resolution, draft a NEW KB article. Format: a one-line "
                    "title (start with 'TITLE: '), then a body with sections "
                    "'Symptoms', 'Root cause', 'Fix', 'Prevention'. Be concise. "
                    "Always set resolved=false - the reviewer must see your draft."
                ),
                tools=[],
                model=MODEL,
            ),
        ),
        (
            "technical-reviewer",
            AgentDefinition(
                description="Validates the technical content of the draft",
                prompt=(
                    "You are a technical reviewer. Read the draft and ensure each "
                    "claim is accurate and the steps are reproducible. Make "
                    "corrections inline; preserve the title line. Always set "
                    "resolved=false so the editor gets a final pass."
                ),
                tools=[],
                model=MODEL,
            ),
        ),
        (
            "editor",
            AgentDefinition(
                description="Final editor - polishes prose and signs off",
                prompt=(
                    "You are the editor. Tighten the prose, fix grammar, and "
                    "ensure the article reads well for a non-expert audience. "
                    "Keep the 'TITLE: ' line as the first line. When you are "
                    "satisfied, set resolved=true so the chain ends."
                ),
                tools=[],
                model=MODEL,
            ),
        ),
    ]


async def _run_author(
    name: str, defn: AgentDefinition, original_input: str, prior_output: str
) -> dict:
    print(f"\n--- author: {name} ---")
    options = ClaudeAgentOptions(
        model=defn.model,
        system_prompt=defn.prompt,
        output_format={"type": "json_schema", "schema": RESPONSE_SCHEMA},
    )
    prompt = (
        f"You are working as part of a 3-author collaboration group.\n"
        f"Your role: {defn.description}\n\n"
        f"Source material (resolved ticket package):\n{original_input}\n\n"
        f"Previous author's output:\n{prior_output}\n\n"
        f"Set 'content' to your contribution. Follow your role's "
        f"instructions on when to set resolved=true."
    )

    decision = None
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        print(f"  {name}: {block.text}")
            elif isinstance(msg, ResultMessage):
                if msg.structured_output:
                    decision = msg.structured_output
                if msg.total_cost_usd:
                    print(f"  [{name}] cost ${msg.total_cost_usd:.4f}")
    return decision or {"resolved": False, "content": prior_output}


def _split_title_body(article: str) -> tuple[str, str]:
    """Pull a 'TITLE: ...' line out, return (title, body)."""
    for line in article.splitlines():
        if line.strip().lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            body = "\n".join(l for l in article.splitlines() if l is not line).strip()
            if title:
                return title, body
    return "Untitled KB Article", article.strip()


async def run_document(
    ticket_text: str, diagnosis: str, review: str, resolution: dict
) -> dict:
    """Run the collaboration chain, then HITL-gate publication."""
    print("\n" + "=" * 72)
    print("STAGE 6: DOCUMENT  [COLLABORATION multi-agent]")
    print("=" * 72)

    original = (
        f"Ticket:\n{ticket_text}\n\n"
        f"Diagnosis:\n{diagnosis}\n\n"
        f"Peer review:\n{review}\n\n"
        f"Resolution status: {resolution.get('status')}, "
        f"iterations: {resolution.get('iterations_used')}\n"
        f"Final plan that was tried:\n{resolution.get('final_plan')}"
    )

    authors = _build_authors()
    names = [n for n, _ in authors]
    defs = {n: d for n, d in authors}

    prior_output = "(none - you are the first author)"
    iteration = 0
    while iteration < MAX_ITERATIONS:
        for name in names:
            iteration += 1
            if iteration > MAX_ITERATIONS:
                break
            decision = await _run_author(name, defs[name], original, prior_output)
            prior_output = decision["content"]
            if decision.get("resolved"):
                print(f"\n  '{name}' marked the article resolved.")
                break
        else:
            continue
        break

    final_article = prior_output
    print("\n--- FINAL ARTICLE (pre-publish) ---")
    print(final_article)

    publish = ask_user_question(
        "Publish this KB article to disk?",
        ["Yes - publish", "No - discard"],
    )
    if publish.get("answer") != "Yes - publish":
        print("  user declined to publish; article discarded.")
        return {"published": False, "title": None, "path": None, "article": final_article}

    title, body = _split_title_body(final_article)
    saved = await save_kb_article.handler({"title": title, "body": body})
    saved_msg = saved["content"][0]["text"]
    print(f"  {saved_msg}")
    return {"published": True, "title": title, "path": saved_msg, "article": final_article}


if __name__ == "__main__":
    async def _demo():
        await run_document(
            "VPN times out after 2FA",
            "Root cause: degraded auth gateway.",
            "Peer review confirms diagnosis.",
            {"status": "resolved", "iterations_used": 1, "final_plan": "Switch DNS, retry."},
        )
    anyio.run(_demo)
