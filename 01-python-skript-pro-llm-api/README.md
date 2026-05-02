Run a solution
```shell
# put your secrets in .env (not committed)
cp .env.example .env

rm -rf .venv && uv venv && uv sync
uv run main.py
```

The default user prompt is intentionally vague ("What is the weather like?") so the model first calls the `ask_user_question` tool, blocks on stdin for your selection, and only then calls `get_current_weather` with the chosen location.

Expected output (interactive - you'll be asked to pick an option)
```
Step 1 response: ChatCompletionMessage(content=None, ..., tool_calls=[ChatCompletionMessageToolCall(id='call_...', function=Function(arguments='{"question":"Which location would you like the weather for?","options":["Prostějov","Brno","Möglingen"]}', name='ask_user_question'), type='function')])

[ask_user_question] Which location would you like the weather for?
  1. Prostějov
  2. Brno
  3. Möglingen
  4. Other (type your own answer)
Select an option number: 2
  -> ask_user_question({'question': '...', 'options': [...]}) = {'answer': 'Brno', 'source': 'option'}

Step 2 response: ChatCompletionMessage(content=None, ..., tool_calls=[ChatCompletionMessageToolCall(id='call_...', function=Function(arguments='{"location":"Brno"}', name='get_current_weather'), type='function')])
  -> get_current_weather({'location': 'Brno'}) = {'query': 'Brno', 'resolved_location': 'Brno, Jihomoravsky, Czech Republic', 'temperature_c': 18.0, ...}

Step 3 response: ChatCompletionMessage(content="The current weather in Brno, Czech Republic is ...", ..., tool_calls=None)
--- Full response: ---
ChatCompletionMessage(content="The current weather in Brno, Czech Republic is ...", ..., tool_calls=None)
--- Response text: ---
The current weather in Brno, Czech Republic is ...
```

Pick `4` at the prompt to type a custom location via the "Other" branch. To skip the question entirely, edit the user message in `main.py` to include a location (e.g. "What is the weather in Prague?").