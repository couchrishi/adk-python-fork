from google.cloud import discoveryengine_v1beta

try:
    c = discoveryengine_v1beta.SessionServiceClient
    print("Methods in SessionServiceClient:")
    methods = [m for m in dir(c) if not m.startswith('_')]
    print(methods)
    
    if 'stream_query' in methods:
        print("\nFound stream_query!")
    if 'stream_assist' in methods:
        print("\nFound stream_assist!")

except Exception as e:
    print(e)

