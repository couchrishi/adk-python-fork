
import sys
try:
    from google.cloud import discoveryengine_v1beta as discoveryengine
    print("google.cloud.discoveryengine_v1beta found")
    
    # We are looking for the StreamAssist related methods.
    # Typically this is in the ConversationalSearchServiceClient or similar.
    client = discoveryengine.ConversationalSearchServiceClient()
    print("ConversationalSearchServiceClient found")
    print("Methods:", [m for m in dir(client) if not m.startswith('_')])

    # Also check for SessionsClient
    sessions_client = discoveryengine.SessionsClient()
    print("SessionsClient found")
    print("Methods:", [m for m in dir(sessions_client) if not m.startswith('_')])

except Exception as e:
    print(f"Error or Not found: {e}")
