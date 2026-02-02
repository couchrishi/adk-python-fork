
import sys
from google.cloud import discoveryengine_v1beta as discoveryengine

try:
    client = discoveryengine.ConversationalSearchServiceClient()
    print("Help for converse_conversation:")
    help(client.converse_conversation)
except Exception as e:
    print(e)
