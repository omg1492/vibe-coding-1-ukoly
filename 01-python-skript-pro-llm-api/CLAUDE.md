## Commands

Setup and run (uses `uv`, Python >=3.12):

```shell
cp .env.example .env   # then put OPENAI_API_KEY into .env
rm -rf .venv && uv venv && uv sync
uv run main.py
```

There is no test suite, linter, or build step configured.

## Architecture

Single-file demo (`main.py`) of the OpenAI Chat Completions tool-calling loop:

1. `get_completion_from_messages(messages, model="gpt-4o", max_iterations=8)` runs a real loop: it calls the model, dispatches every `tool_call` in the response, appends the assistant `tool_calls` message and one `role="tool"` reply per call, and repeats until the model returns a message with no `tool_calls` (or hits the iteration cap, in which case it raises).
2. Two tools are registered:
   - `get_current_weather(location)` calls `https://wttr.in/<loc>?format=j1` (no API key) and normalizes the response via the `_first_text` / `_to_float` / `_to_int` helpers; failures return a dict with an `error` key rather than raising.
   - `ask_user_question(question, options)` is the in-script analogue of Claude Code's own `AskUserQuestion` tool: it prints a numbered menu of 2-4 options plus an auto-appended "Other" entry, blocks on stdin, and returns the chosen answer to the LLM. Used so the model can ask the user for missing info (e.g. a location) before calling another tool.

### Things to know before editing

- Adding a new tool requires three coordinated edits: implement the function, add its JSON schema to `tools`, and register it in `available_functions`.
- The system prompt in the example messages explicitly steers the model toward `ask_user_question` when no location is given, with the option list `['Prostějov', 'Brno', 'Möglingen']`. Editing one without the other will break the demo flow.
- `pyproject.toml` lists `curl-cffi` and `yfinance` as dependencies, but `main.py` does not import them - they are leftovers, not part of the current solution. Keep that in mind before assuming they're load-bearing.
- The project name in `pyproject.toml` is `3-function-calls`, which doesn't match the directory name; don't "fix" this without checking with the user.

## Repo conventions

- Secrets live in `.env` (gitignored); `.env.example` documents required keys.
- The `samples/` convention from the global CLAUDE.md does not currently exist in this project.
