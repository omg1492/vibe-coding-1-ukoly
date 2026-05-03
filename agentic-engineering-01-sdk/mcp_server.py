"""Centralised MCP server factory for the helpdesk demo.

Each stage spins up a fresh agent (or several) with `ClaudeAgentOptions`. To
let those agents call our custom tools we register them once on an in-process
SDK MCP server and reuse it everywhere.

The list of fully-qualified tool names (`mcp__helpdesk__<tool>`) is exported
as `ALL_TOOL_NAMES` so callers can pick subsets via `allowed_tools`.
"""

from claude_agent_sdk import create_sdk_mcp_server

from hitl import ask_user_question_tool
from tools import (
    check_system_status,
    find_similar_tickets,
    lookup_user_history,
    save_kb_article,
    search_kb,
)

SERVER_NAME = "helpdesk"


def make_helpdesk_server():
    """Build an in-process MCP server exposing every helpdesk tool plus HITL."""
    return create_sdk_mcp_server(
        name=SERVER_NAME,
        version="1.0.0",
        tools=[
            search_kb,
            find_similar_tickets,
            check_system_status,
            lookup_user_history,
            save_kb_article,
            ask_user_question_tool,
        ],
    )


def tool_name(local: str) -> str:
    return f"mcp__{SERVER_NAME}__{local}"


# Pre-built fully-qualified names so stages don't have to remember the prefix.
TOOL_SEARCH_KB = tool_name("search_kb")
TOOL_FIND_SIMILAR = tool_name("find_similar_tickets")
TOOL_CHECK_STATUS = tool_name("check_system_status")
TOOL_USER_HISTORY = tool_name("lookup_user_history")
TOOL_SAVE_KB = tool_name("save_kb_article")
TOOL_ASK_USER = tool_name("ask_user_question")

ALL_TOOL_NAMES = [
    TOOL_SEARCH_KB,
    TOOL_FIND_SIMILAR,
    TOOL_CHECK_STATUS,
    TOOL_USER_HISTORY,
    TOOL_SAVE_KB,
    TOOL_ASK_USER,
]
