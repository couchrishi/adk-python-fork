
import asyncio
import os
from google.adk.models.gemini_enterprise_llm import GeminiEnterprise
from google.adk.models.llm_request import LlmRequest
from google.genai import types

async def main():
    # Load from environment variables (matching the model's defaults)
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    engine_id = os.environ.get("GEMINI_ENTERPRISE_ENGINE_ID")
    location = os.environ.get("GEMINI_ENTERPRISE_LOCATION", "global")
    
    if not project_id or not engine_id:
        print("Please set PROJECT_ID and ENGINE_ID environment variables.")
        return

    model = GeminiEnterprise(
        project_id=project_id,
        engine_id=engine_id,
        location=location
    )

    request = LlmRequest(
        contents=[types.Content(parts=[types.Part(text="What is Gemini Enterprise?")])]
    )

    print(f"--- Querying Gemini Enterprise (Project: {project_id}, Engine: {engine_id}) ---")
    
    async for response in model.generate_content_async(request, stream=True):
        if response.partial:
            print(response.content.parts[0].text, end="", flush=True)
        else:
            print("\n\n--- Final Response ---")
            print(response.content.parts[0].text)
            print("--- End ---")

if __name__ == "__main__":
    asyncio.run(main())
