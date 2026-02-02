from google.cloud import discoveryengine_v1beta

# Try to find SessionsClient via different import paths
try:
    from google.cloud.discoveryengine_v1beta.services.sessions import client as sessions_client
    print("Found via services.sessions.client")
    c = sessions_client.SessionsClient
    print([m for m in dir(c) if 'stream' in m.lower()])
except ImportError:
    print("Not found in services.sessions.client")

# Check what IS available in discoveryengine_v1beta
print("\nTop level discoveryengine_v1beta members:")
for x in dir(discoveryengine_v1beta):
    if 'Session' in x:
        print(x)
