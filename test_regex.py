
import re
import json

text = """**Deciding on Action**
{"tool": "get_current_weather", "parameters": {"location": "New York"}}"""

json_match = re.search(r'(\{.*"tool".*?\})', text, re.DOTALL)
print(f"Match: {json_match}")
if json_match:
    print(f"Group: {json_match.group(1)}")
    try:
        data = json.loads(json_match.group(1))
        print(f"Data: {data}")
    except Exception as e:
        print(f"Error: {e}")
