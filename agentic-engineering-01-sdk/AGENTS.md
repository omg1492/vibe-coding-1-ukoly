# Agents inventory

All agents run on the Claude Agent SDK with `model="sonnet"`. They are spun up
on demand by each stage file - there is no globally shared state besides the
in-process MCP server defined in `mcp_server.py`.

## Stage 1 - Intake (parallel)

| Agent | Tool surface | Role |
|---|---|---|
| `kb-searcher` | `search_kb` | Pull up to 3 relevant KB articles for the ticket. |
| `similar-finder` | `find_similar_tickets` | Surface analogous historical tickets and their resolutions. |
| `status-checker` | `check_system_status` | Check internal services implicated by the ticket. |
| `history-fetcher` | `lookup_user_history` | Pull recent ticket history for the reporting user. |
| `aggregator` | (none) | Fan-in agent that synthesises a short intake dossier. |

## Stage 2 - Triage (conditional + HITL)

| Agent | Tool surface | Role |
|---|---|---|
| `classifier` | (none) | Labels the ticket: network / account / software / hardware / security / other. |
| `first-responder-{category}` | (none) | One of 5 templates - gives a one-paragraph first-line read for the confirmed category. |

HITL: `ask_user_question` is called between classifier and first-responder so
the user can override the suggested category.

## Stage 3 - Diagnose (supervisor)

| Agent | Tool surface | Role |
|---|---|---|
| `supervisor` (L2 lead) | (none, structured-output decisions only) | Loops `delegate -> finish`. |
| `network-specialist` | `search_kb`, `find_similar_tickets`, `check_system_status`, `lookup_user_history` | Network/VPN root-cause investigation. |
| `account-specialist` | same | Identity / 2FA root-cause investigation. |
| `software-specialist` | same | Endpoint / app root-cause investigation. |
| `hardware-specialist` | same | Hardware / device root-cause investigation. |
| `security-specialist` | same | Security-relevant indicator investigation. |

## Stage 4 - Review (swarm)

| Agent | Tool surface | Handoffs |
|---|---|---|
| `engineering-reviewer` | `search_kb`, `find_similar_tickets` | -> security-reviewer, impact-reviewer |
| `security-reviewer` | same | -> impact-reviewer, engineering-reviewer |
| `impact-reviewer` | same | -> engineering-reviewer (typically finishes) |

Initial agent: `engineering-reviewer`.

## Stage 5 - Resolve (loop + HITL)

| Agent | Tool surface | Role |
|---|---|---|
| `proposer` | `search_kb` | Drafts a step-by-step fix; each iteration is a fresh session. |

HITL: between iterations, `ask_user_question` is the evaluator that decides
whether to exit the loop.

## Stage 6 - Document (collaboration + HITL)

| Agent | Tool surface | Role |
|---|---|---|
| `kb-writer` | (none) | Drafts the article (TITLE line + sections). |
| `technical-reviewer` | (none) | Validates technical claims; revises inline. |
| `editor` | (none) | Polishes prose, sets `resolved=true` to end the chain. |

HITL: orchestrator gates publication via `ask_user_question`. If approved,
`save_kb_article` (a tool, called directly by the orchestrator) persists the
article to `output/kb_articles/<slug>.md`.

## Custom MCP tools

Implemented in `tools.py`, registered in `mcp_server.py` under server name
`helpdesk`:

| Tool | Backed by | Used in stages |
|---|---|---|
| `search_kb` | `data/kb.json` | 1, 3, 4, 5 |
| `find_similar_tickets` | `data/tickets.json` | 1, 3, 4 |
| `check_system_status` | `data/status.json` | 1, 3 |
| `lookup_user_history` | `data/tickets.json` (filtered by user_id) | 1, 3 |
| `save_kb_article` | writes `output/kb_articles/<slug>.md` | 6 (orchestrator only) |
| `ask_user_question` | stdin (numbered menu + "Other") | exposed; orchestrator calls direct |
