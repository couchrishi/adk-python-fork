import asyncio
import os
from google.adk.models.gemini_enterprise_llm import GeminiEnterprise
from google.adk.models.llm_request import LlmRequest
from google.genai import types

# --- 1. Define the Tool using Standard ADK Types ---
def get_current_weather(location: str) -> str:
    """Get the current weather for a location."""
    print(f"\n[Tool Execution] Querying weather for {location}...")
    return f"The weather in {location} is Sunny, 25°C."

# Define the function declaration
weather_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_current_weather",
            description="Get the current weather for a location.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "location": types.Schema(
                        type="STRING",
                        description="The city and state, e.g. San Francisco, CA"
                    )
                },
                required=["location"]
            )
        )
    ]
)

# --- 2. Clean Agent Logic (No manual prompting!) ---
async def run_weather_agent():
    # Configuration
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    engine_id = os.environ.get("GEMINI_ENTERPRISE_ENGINE_ID")
    location = os.environ.get("GEMINI_ENTERPRISE_LOCATION", "global")

    if not project_id or not engine_id:
        print("Please set GOOGLE_CLOUD_PROJECT and GEMINI_ENTERPRISE_ENGINE_ID environment variables.")
        return

    # Instantiate our new model
    model = GeminiEnterprise(
        project_id=project_id,
        engine_id=engine_id,
        location=location
    )

    # Initial User Query
    user_query = "What is the weather like in New York?"
    print(f"\nUser: {user_query}")

    # Create request with the tool configuration!
    # The GeminiEnterprise model will now automatically inject the instructions.
    request = LlmRequest(
        contents=[types.Content(parts=[types.Part(text=user_query)])],
        config=types.GenerateContentConfig(tools=[weather_tool])
    )

    # --- Turn 1: Model generates tool call ---
    print("\nModel (Thinking)...")
    final_response = None
    async for response in model.generate_content_async(request, stream=True):
        if response.partial and response.content and response.content.parts:
            # We might still see text streaming before the JSON block
            if response.content.parts[0].text:
                print(response.content.parts[0].text, end="", flush=True)
        
        if not response.partial:
            final_response = response

    print() # Newline

    # Check for Function Call (Standard ADK way!)
    tool_call = None
    if final_response and final_response.content and final_response.content.parts:
        for part in final_response.content.parts:
            if part.function_call:
                print(f"\n[System] Native Function Call Detected: {part.function_call.name}({part.function_call.args})")
                tool_call = part.function_call
                break

    # --- Turn 2: Pass result back to Model ---
    if tool_call:
        if tool_call.name == "get_current_weather":
            # Execute tool
            location_arg = tool_call.args.get("location")
            result = get_current_weather(location_arg)
            
            # Feed result back (simulating FunctionResponse)
            # Since StreamAssist is chatty, we just tell it the result in text.
            # Ideally, we'd map FunctionResponse to text for StreamAssist.
            follow_up_text = f"Tool '{tool_call.name}' returned: {result}"
            
            follow_up_request = LlmRequest(
                contents=[types.Content(parts=[types.Part(text=follow_up_text)])],
                config=types.GenerateContentConfig(tools=[weather_tool]) # Keep tools available
            )
            
            print("\nModel (Final Answer)...")
            async for response in model.generate_content_async(follow_up_request, stream=True):
                 if response.partial and response.content and response.content.parts:
                    if response.content.parts[0].text:
                        print(response.content.parts[0].text, end="", flush=True)
            print()

if __name__ == "__main__":
    asyncio.run(run_weather_agent())