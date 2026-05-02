Run a solution
```shell
# put your secrets in .env (not committed)
cp .env.example .env

rm -rf .venv && uv venv && uv sync
uv run main.py
```

Expected output
```
First response: ChatCompletionMessage(content=None, refusal=None, role='assistant', annotations=[], audio=None, function_call=None, tool_calls=[ChatCompletionMessageToolCall(id='call_kmYfenGKJmVRMmbLdsmKY2Q6', function=Function(arguments='{"location":"Prague"}', name='get_current_weather'), type='function')])
{'query': 'Prague', 'resolved_location': 'Prague, Hlavni mesto Praha, Czech Republic', 'temperature_c': 18.0, 'feels_like_c': 18.0, 'condition': 'Sunny', 'humidity_pct': 39, 'wind_kph': 10.0, 'observation_time_utc': '05:12 PM', 'source': 'wttr.in'}
Second response: ChatCompletionMessage(content="The current weather in Prague, Czech Republic, is sunny with a temperature of 18°C. It feels like 18°C as well. The humidity is 39%, and there's a wind speed of 10 km/h.", refusal=None, role='assistant', annotations=[], audio=None, function_call=None, tool_calls=None)
--- Full response: ---
ChatCompletionMessage(content="The current weather in Prague, Czech Republic, is sunny with a temperature of 18°C. It feels like 18°C as well. The humidity is 39%, and there's a wind speed of 10 km/h.", refusal=None, role='assistant', annotations=[], audio=None, function_call=None, tool_calls=None)
--- Response text: ---
The current weather in Prague, Czech Republic, is sunny with a temperature of 18°C. It feels like 18°C as well. The humidity is 39%, and there's a wind speed of 10 km/h.
```