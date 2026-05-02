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
]

available_functions = {
    "get_current_weather": get_current_weather,
}

# Function to process messages and handle function calls
def get_completion_from_messages(messages, model="gpt-4o"):
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,  # Custom tools
        tool_choice="auto"  # Allow AI to decide if a tool should be called
    )

    response_message = response.choices[0].message

    print("First response:", response_message)

    if response_message.tool_calls:
        # Find the tool call content
        tool_call = response_message.tool_calls[0]

        # Extract tool name and arguments
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments) 
        tool_id = tool_call.id
        
        # Call the function
        function_to_call = available_functions[function_name]
        function_response = function_to_call(**function_args)

        print(function_response)

        messages.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tool_id,  
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": json.dumps(function_args),
                    }
                }
            ]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tool_id,  
            "name": function_name,
            "content": json.dumps(function_response),
        })

        # Second call to get final response based on function output
        second_response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,  
            tool_choice="auto"  
        )
        final_answer = second_response.choices[0].message

        print("Second response:", final_answer)
        return final_answer

    return "No relevant function call found."

# Example usage
messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    # Try any location: "Prague", "Brno, CZ", "49.74,13.59"
    {"role": "user", "content": "What is the current weather in Prague?"},
]

response = get_completion_from_messages(messages)
print("--- Full response: ---")
pprint(response)
print("--- Response text: ---")
print(response.content)
