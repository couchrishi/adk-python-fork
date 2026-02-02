import os
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.models.gemini_enterprise_llm import GeminiEnterprise

# Load .env from the project root (4 levels up from this sample)
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../../.env"))

def get_current_weather(location: str) -> str:
    """Get the current weather for a location.
    
    Args:
        location: The city and state, e.g. San Francisco, CA
    """
    print(f"\n[Tool Execution] Querying weather for {location}...")
    return f"The weather in {location} is Sunny, 25°C."

def adk_request_credential(auth_config: dict) -> dict:
    """System tool to handle authentication requests."""
    return {"status": "success"}

root_agent = Agent(
    # Use our new GeminiEnterprise model!
    # It will automatically pick up project_id/engine_id from env vars.
    model=GeminiEnterprise(),
    name='weather_agent_ge',
    description='A weather agent using Gemini Enterprise StreamAssist.',
    instruction="""
      You are a helpful weather assistant. 
      You help users find the current weather in any location.
      Always use the get_current_weather tool when asked about the weather.
    """,
    tools=[get_current_weather, adk_request_credential],
)

