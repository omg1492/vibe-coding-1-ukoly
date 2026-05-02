# Tool-calling demo: weather + ask-the-user

A minimal Python script that shows the OpenAI Chat Completions tool-calling loop with **two complementary tools**:

| Tool | Direction | What it does |
|---|---|---|
| `get_current_weather(location)` | LLM → external service | Calls the public [wttr.in](https://wttr.in) API (no key needed) and returns a normalized JSON payload. |
| `ask_user_question(question, options)` | LLM → user (terminal) | Renders a numbered menu (with auto-appended "Other") on stdin, blocks for input, returns the chosen answer. Same pattern Claude Code's harness uses for its own `AskUserQuestion` tool. |

The default prompt is intentionally vague ("What is the weather like?"), so the model has to ask the user **where** before it can fetch weather. End-to-end you observe three round-trips: ask → fetch → summarize.

## Prerequisites

- Python >= 3.12
- [`uv`](https://docs.astral.sh/uv/) for env and dependency management
- An OpenAI API key

## Setup

```shell
cp .env.example .env          # then put your OPENAI_API_KEY into .env
rm -rf .venv && uv venv && uv sync
```

## Run

```shell
uv run main.py
```

You'll be prompted to pick a location, then the script fetches the weather and prints a natural-language summary.

## Expected output

```
Step 1 response: ChatCompletionMessage(... tool_calls=[... name='ask_user_question', arguments='{"question":"Which location ...","options":["Prostějov","Brno","Möglingen"]}' ...])

[ask_user_question] Which location would you like the weather for?
  1. Prostějov
  2. Brno
  3. Möglingen
  4. Other (type your own answer)
Select an option number: 2
  -> ask_user_question(...) = {'answer': 'Brno', 'source': 'option'}

Step 2 response: ChatCompletionMessage(... tool_calls=[... name='get_current_weather', arguments='{"location":"Brno"}' ...])
  -> get_current_weather({'location': 'Brno'}) = {'query': 'Brno', 'resolved_location': 'Brno, Jihomoravsky kraj, Czech Republic', 'temperature_c': 18.0, ...}

Step 3 response: ChatCompletionMessage(content='The current weather in Brno, Czech Republic is clear ...', tool_calls=None)
--- Response text: ---
The current weather in Brno, Czech Republic is clear with a temperature of 18°C ...
```

## How it works

`get_completion_from_messages()` runs a real loop (capped at `max_iterations=8`):

1. Send the conversation to OpenAI with both tool schemas and `tool_choice="auto"`.
2. If the response has no `tool_calls`, return it - we're done.
3. Otherwise, append the assistant `tool_calls` message, dispatch every call through the `available_functions` table, append one `role="tool"` reply per call, and loop.

This matches the contract OpenAI's Chat Completions API expects: every `tool_call` must be answered with a `role="tool"` message before the next round-trip.

## Try variations

- **Use the "Other" branch** - pick `4` at the menu to type any location wttr.in can resolve (e.g. `Plzeň`, `49.74,13.59`).
- **Skip the question** - edit the user message in `main.py` to `"What is the weather in Prague?"`. The model will skip `ask_user_question` and call `get_current_weather` directly.
- **Add a third tool** - implement the function, add its JSON schema to `tools`, and register it in `available_functions`. The loop handles any number of sequential calls.

## Project layout

```
.
├── main.py            # the whole demo - tools, loop, example messages
├── pyproject.toml     # deps: openai, requests, python-dotenv (curl-cffi/yfinance are unused leftovers)
├── .env.example       # template for OPENAI_API_KEY
└── README.md
```

## Notes

- Secrets live in `.env`, which is gitignored. Never commit your real key.
- `ask_user_question` returns `{"answer": ..., "source": "option" | "other"}`; the LLM treats both the same.
- The system prompt steers the model toward the seeded option set `['Prostějov', 'Brno', 'Möglingen']`. Edit it in `main.py` if you want different defaults.
