"""Human-in-the-loop primitive.

Exposes `ask_user_question(question, options) -> dict` exactly like the prior
01-python-skript-pro-llm-api project: numbered menu (1-indexed), auto-appended
"Other" entry, blocks on stdin, returns {"answer": str, "source": "option" | "other"}.

Two surfaces:
- the plain Python function for the orchestrator (main.py and stage files)
- the same function wrapped as a Claude Agent SDK tool, so specialist agents
  can call it themselves mid-conversation (matches the "tool the LLM calls"
  pattern from the prior project).
"""

from typing import Any

from claude_agent_sdk import tool


def ask_user_question(question: str, options: list[str]) -> dict:
    """Stdin-based analogue of Claude Code's AskUserQuestion tool.

    Renders a numbered menu of 2-4 options plus an auto-appended 'Other'
    entry, then blocks until the user picks a number (or types a custom
    answer for 'Other'). Returns the chosen answer.
    """
    if not (2 <= len(options) <= 4):
        return {"error": "invalid_options", "detail": "options must have 2-4 entries"}

    print(f"\n[ask_user_question] {question}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    other_idx = len(options) + 1
    print(f"  {other_idx}. Other (type your own answer)")

    while True:
        raw = input("Select an option number: ").strip()
        if not raw.isdigit():
            print("Please enter a number.")
            continue
        idx = int(raw)
        if 1 <= idx <= len(options):
            return {"answer": options[idx - 1], "source": "option"}
        if idx == other_idx:
            custom = input("Your answer: ").strip()
            if custom:
                return {"answer": custom, "source": "other"}
            print("Empty answer; please try again.")
            continue
        print(f"Out of range; pick 1-{other_idx}.")


@tool(
    "ask_user_question",
    "Ask the human user a clarifying question with 2-4 predefined options. "
    "The user picks a number from a numbered menu (an extra 'Other' entry is "
    "always appended automatically so they can also type a custom answer). "
    "Use this when you need information only the user can provide (e.g. to "
    "disambiguate a symptom, choose between alternative fixes, or confirm a "
    "category). Do not invent answers.",
    {
        "question": str,
        "options": list[str],
    },
)
async def ask_user_question_tool(args: dict[str, Any]) -> dict[str, Any]:
    """MCP tool wrapper around ask_user_question for agent use."""
    result = ask_user_question(args["question"], args["options"])
    if "error" in result:
        text = f"Error from ask_user_question: {result}"
    else:
        text = (
            f"User picked: {result['answer']} (source={result['source']})"
        )
    return {"content": [{"type": "text", "text": text}]}
