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

1. `get_completion_from_messages(messages, model="gpt-4o")` sends the conversation to OpenAI with `tools=[…]` and `tool_choice="auto"`.
2. If the model returns `tool_calls`, the script handles **only the first** tool call: looks the function up in `available_functions`, executes it with the parsed JSON args, and appends both the assistant `tool_calls` message and a `role="tool"` reply to `messages`.
3. A second `chat.completions.create` call produces the user-facing answer.

The only registered tool is `get_current_weather(location)`, which calls `https://wttr.in/<loc>?format=j1` (no API key) and normalizes the response via the `_first_text` / `_to_float` / `_to_int` helpers; failures return a dict with an `error` key rather than raising.

### Things to know before editing

- The handler processes exactly one tool call and does not loop, so multi-tool / chained calls won't work without restructuring.
- Adding a new tool requires three coordinated edits: implement the function, add its JSON schema to `tools`, and register it in `available_functions`.
- `pyproject.toml` lists `curl-cffi` and `yfinance` as dependencies, but `main.py` does not import them - they are leftovers, not part of the current solution. Keep that in mind before assuming they're load-bearing.
- The project name in `pyproject.toml` is `3-function-calls`, which doesn't match the directory name; don't "fix" this without checking with the user.

## Repo conventions

- Secrets live in `.env` (gitignored); `.env.example` documents required keys.
- The `samples/` convention from the global CLAUDE.md does not currently exist in this project.
