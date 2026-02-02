import os
from google.cloud import discoveryengine_v1 as discoveryengine
from google.api_core.client_options import ClientOptions

project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
engine_id = os.environ.get("GEMINI_ENTERPRISE_ENGINE_ID")
location = os.environ.get("GEMINI_ENTERPRISE_LOCATION", "global")

client_options = (
    ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
    if location != "global"
    else None
)
client = discoveryengine.AssistantServiceClient(client_options=client_options)

request = discoveryengine.StreamAssistRequest(
    name=client.assistant_path(
        project=project_id,
        location=location,
        collection="default_collection",
        engine=engine_id,
        assistant="default_assistant",
    ),
    # Use a real question to avoid "SKIPPED" state
    query=discoveryengine.Query(text="What is this engine about?"),
)

print(f"Sending request to {project_id}...")
try:
    responses = client.stream_assist(request=request)
    for response in responses:
        print(response)
except Exception as e:
    print(f"Error: {e}")