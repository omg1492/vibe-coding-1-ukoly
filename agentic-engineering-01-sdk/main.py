"""End-to-end IT service-desk demo built on the Claude Agent SDK.

The outer pipeline IS the SEQUENTIAL workflow pattern. Each stage demonstrates
exactly one of the other six required orchestration patterns:

  Stage 1 - Intake   [PARALLEL]      stage_intake.py
  Stage 2 - Triage   [CONDITIONAL]   stage_triage.py    (+ HITL)
  Stage 3 - Diagnose [SUPERVISOR]    stage_diagnose.py
  Stage 4 - Review   [SWARM]         stage_review.py
  Stage 5 - Resolve  [LOOP]          stage_resolve.py   (+ HITL)
  Stage 6 - Document [COLLABORATION] stage_document.py  (+ HITL)

Run: `uv run main.py` for the default sample ticket, or
     `uv run main.py "your custom ticket text"` to drive your own scenario.

You can also pass an optional second argument with the user_id (default
'u-default', which has matching seed history under data/tickets.json).
"""

import sys

import anyio
from dotenv import load_dotenv

from stage_diagnose import run_diagnose
from stage_document import run_document
from stage_intake import run_intake
from stage_resolve import run_resolve
from stage_review import run_review
from stage_triage import run_triage

load_dotenv()

DEFAULT_TICKET = (
    "Hi, since this morning I cannot sign in to the corporate VPN. The password "
    "is correct and the 2FA code is accepted, but right after that I get "
    "'Connection timed out' and the client disconnects. I am working from home, "
    "the rest of my internet is fine."
)
DEFAULT_USER_ID = "u-default"


def _banner(title: str, ch: str = "#") -> None:
    bar = ch * 72
    print(f"\n{bar}\n{title}\n{bar}")


async def main(ticket_text: str, user_id: str) -> None:
    _banner("AI SERVICE DESK - End-to-end ticket lifecycle")
    print(f"Sequential outer pipeline driving 6 stages.")
    print(f"Ticket  : {ticket_text}")
    print(f"User    : {user_id}")

    # Stage 1 - PARALLEL fan-out / fan-in
    dossier = await run_intake(ticket_text, user_id)

    # Stage 2 - CONDITIONAL with HITL gate
    triage = await run_triage(ticket_text, dossier)

    # Stage 3 - SUPERVISOR multi-agent
    diagnosis = await run_diagnose(ticket_text, dossier, triage)

    # Stage 4 - SWARM peer review
    validated = await run_review(ticket_text, diagnosis)

    # Stage 5 - LOOP with HITL evaluator
    resolution = await run_resolve(ticket_text, diagnosis, validated)

    # Stage 6 - COLLABORATION authoring with HITL publish gate
    publication = await run_document(ticket_text, diagnosis, validated, resolution)

    _banner("PIPELINE SUMMARY")
    print(f"Category        : {triage['category']}")
    print(f"Resolution      : {resolution['status']} after {resolution['iterations_used']} iteration(s)")
    if publication["published"]:
        print(f"KB article      : {publication['title']}")
        print(f"Saved to        : {publication['path']}")
    else:
        print("KB article      : not published (user declined)")
    _banner("DONE", ch="=")


if __name__ == "__main__":
    args = sys.argv[1:]
    ticket = args[0] if len(args) >= 1 else DEFAULT_TICKET
    user_id_arg = args[1] if len(args) >= 2 else DEFAULT_USER_ID
    anyio.run(main, ticket, user_id_arg)
