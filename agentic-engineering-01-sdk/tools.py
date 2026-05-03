"""Helpdesk-domain MCP tools backed by the JSON files under data/.

Each tool is a thin search/lookup over a small in-memory backend. The point
is that specialist agents have something *real* to query so the demo shows
genuine tool use, not just stubbed constants.
"""

import json
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import tool

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output" / "kb_articles"


def _load(filename: str) -> Any:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def _terms(text: str) -> list[str]:
    """Extract searchable terms (>=3 chars) from free text."""
    return [t for t in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(t) >= 3]


@tool(
    "search_kb",
    "Search the internal knowledge base. Pass a free-text query; matches are "
    "scored by overlap with article title, body, and tags. Returns up to 5 "
    "articles with id, title, and a snippet.",
    {"query": str},
)
async def search_kb(args: dict[str, Any]) -> dict[str, Any]:
    query = args["query"]
    terms = set(_terms(query))
    if not terms:
        return {"content": [{"type": "text", "text": "Empty query; provide at least one keyword."}]}
    kb = _load("kb.json")
    scored = []
    for article in kb:
        haystack = " ".join([article["title"], article["body"], " ".join(article.get("tags", []))]).lower()
        hits = sum(1 for t in terms if t in haystack)
        if hits:
            scored.append((hits, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return {"content": [{"type": "text", "text": f"No KB articles match: {query}"}]}
    lines = [f"Found {len(scored)} KB article(s) matching '{query}':"]
    for _, a in scored[:5]:
        lines.append(f"- {a['id']}: {a['title']}")
        lines.append(f"  {a['body'][:240]}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "find_similar_tickets",
    "Find historical tickets similar to a free-text description. Useful for "
    "checking how analogous incidents were resolved. Returns up to 5 tickets "
    "with category, summary, and resolution.",
    {"description": str},
)
async def find_similar_tickets(args: dict[str, Any]) -> dict[str, Any]:
    desc = args["description"]
    terms = set(_terms(desc))
    if not terms:
        return {"content": [{"type": "text", "text": "Empty description."}]}
    tickets = _load("tickets.json")
    scored = []
    for t in tickets:
        haystack = (t["summary"] + " " + t.get("category", "")).lower()
        hits = sum(1 for term in terms if term in haystack)
        if hits:
            scored.append((hits, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return {"content": [{"type": "text", "text": f"No similar tickets for: {desc}"}]}
    lines = [f"Found {len(scored)} similar ticket(s):"]
    for _, t in scored[:5]:
        lines.append(f"- {t['id']} ({t['category']}, resolved {t['resolved_at']}): {t['summary']}")
        lines.append(f"  Resolution: {t['resolution']}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "check_system_status",
    "Look up the current health and recent-incident summary for an internal "
    "service. Known service names: VPN, Email, Intranet, Auth, Wiki, Print, "
    "FileShare. Use this before blaming the user's setup.",
    {"service": str},
)
async def check_system_status(args: dict[str, Any]) -> dict[str, Any]:
    service = args["service"].strip()
    status = _load("status.json")
    found = next((s for s in status if s["service"].lower() == service.lower()), None)
    if not found:
        names = ", ".join(s["service"] for s in status)
        return {"content": [{"type": "text", "text": f"Service '{service}' not found. Known: {names}"}]}
    text = (
        f"Service: {found['service']}\n"
        f"Status: {found['status']}\n"
        f"Uptime (24h): {found['uptime_24h']}%\n"
        f"Last incident: {found.get('last_incident', 'none')}"
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "lookup_user_history",
    "Look up a user's recent ticket history by user id (e.g. 'u-default'). "
    "Returns up to 5 of their most recent past tickets with summary and "
    "resolution.",
    {"user_id": str},
)
async def lookup_user_history(args: dict[str, Any]) -> dict[str, Any]:
    user_id = args["user_id"].strip()
    tickets = _load("tickets.json")
    user_tickets = [t for t in tickets if t.get("user_id") == user_id]
    if not user_tickets:
        return {"content": [{"type": "text", "text": f"No history for user '{user_id}'."}]}
    user_tickets.sort(key=lambda t: t["resolved_at"], reverse=True)
    lines = [f"User '{user_id}' history ({len(user_tickets)} ticket(s)):"]
    for t in user_tickets[:5]:
        lines.append(f"- {t['id']} ({t['category']}, {t['resolved_at']}): {t['summary']}")
        lines.append(f"  Resolution: {t['resolution']}")
    return {"content": [{"type": "text", "text": "\n".join(lines)}]}


@tool(
    "save_kb_article",
    "Persist a finished knowledge base article to disk under "
    "output/kb_articles/<slug>.md. The slug is derived from the title. "
    "Returns the saved path.",
    {"title": str, "body": str},
)
async def save_kb_article(args: dict[str, Any]) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    title = args["title"].strip()
    body = args["body"].strip()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "untitled"
    path = OUTPUT_DIR / f"{slug}.md"
    path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return {"content": [{"type": "text", "text": f"Saved KB article to {path.relative_to(ROOT)}"}]}
