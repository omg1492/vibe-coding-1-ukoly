import os
import json
import requests
from urllib.parse import quote
from openai import OpenAI
from pprint import pprint
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
)

# Function Implementations
def get_current_weather(location: str):
    """
    Fetch current weather using wttr.in (public, no API key).
    Docs: https://wttr.in/:help
    """
    try:
        url = f"https://wttr.in/{quote(location)}?format=j1"
        resp = requests.get(
            url,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        cur = (data.get("current_condition") or [{}])[0]
        nearest = (data.get("nearest_area") or [{}])[0]

        resolved_location = None
        try:
            name = (nearest.get("areaName") or [{}])[0].get("value")
            region = (nearest.get("region") or [{}])[0].get("value")
            country = (nearest.get("country") or [{}])[0].get("value")
            parts = [p for p in [name, region, country] if p]
            resolved_location = ", ".join(parts) if parts else None
        except Exception:
            pass

        result = {
            "query": location,
            "resolved_location": resolved_location,
            "temperature_c": _to_float(cur.get("temp_C")),
            "feels_like_c": _to_float(cur.get("FeelsLikeC")),
            "condition": _first_text(cur.get("weatherDesc")),
            "humidity_pct": _to_int(cur.get("humidity")),
            "wind_kph": _to_float(cur.get("windspeedKmph")),
            "observation_time_utc": cur.get("observation_time"),
            "source": "wttr.in",
        }
        return result
    except requests.HTTPError as e:
        return {"query": location, "error": "http_error", "status": e.response.status_code, "detail": str(e)}
    except requests.RequestException as e:
        return {"query": location, "error": "network_error", "detail": str(e)}
    except Exception as e:
        return {"query": location, "error": "parse_error", "detail": str(e)}

def _first_text(arr):
    if isinstance(arr, list) and arr:
        v = arr[0]
        if isinstance(v, dict):
            return v.get("value")
        return v
    return None

def _to_float(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def _to_int(v):
    try:
        return int(v) if v is not None else None
    except Exception:
        return None

def ask_user_question(question: str, options: list[str]) -> dict:
    """
    Stdin-based analogue of Claude Code's AskUserQuestion tool: shows the user
    a numbered list of 2-4 options plus an auto-appended "Other" entry, and
    returns the chosen answer to the LLM.
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

# Define custom tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather for a given location (city name or 'lat,lon').",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or place name (e.g., 'Prague' or '49.283,14.153')."
                    }
                },
                "required": ["location"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "description": (
                "Ask the user a clarifying question with 2-4 predefined options. "
                "Use this when you need information from the user (e.g., a location) "
                "before another tool can be called. The user may also choose 'Other' "
                "and type a custom answer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to display to the user.",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 4,
                        "description": "2-4 short option labels to choose from.",
                    },
                },
                "required": ["question", "options"],
            },
        }
    },
]

available_functions = {
    "get_current_weather": get_current_weather,
    "ask_user_question": ask_user_question,
}

# Function to process messages and handle function calls
def get_completion_from_messages(messages, model="gpt-4o", max_iterations=8):
    """
    Drive a tool-calling loop: keep calling the model until it returns an
    assistant message with no tool_calls, dispatching every tool call in each
    intermediate response. Caps at max_iterations to prevent runaway loops.
    """
    for step in range(1, max_iterations + 1):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        print(f"Step {step} response:", msg)

        if not msg.tool_calls:
            return msg

        messages.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        # Re-emit verbatim to avoid key-ordering / whitespace diffs.
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            fn = available_functions[fn_name]
            result = fn(**fn_args)
            print(f"  -> {fn_name}({fn_args}) =", result)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": fn_name,
                "content": json.dumps(result),
            })

    raise RuntimeError(
        f"Exceeded {max_iterations} tool-calling iterations without a final answer."
    )

# Example usage
messages = [
    {
        "role": "system",
        "content": (
            "You are a helpful AI assistant. If the user asks about weather but does "
            "not specify a location, call the ask_user_question tool first with the "
            "options ['Prostějov', 'Brno', 'Möglingen'] before calling get_current_weather. "
            "Do not assume a location."
        ),
    },
    # Try also: "What is the current weather in Prague?" to skip ask_user_question.
    {"role": "user", "content": "What is the weather like?"},
]

response = get_completion_from_messages(messages)
print("--- Full response: ---")
pprint(response)
print("--- Response text: ---")
print(response.content)
