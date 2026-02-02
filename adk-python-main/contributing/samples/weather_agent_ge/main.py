import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import webbrowser
from urllib.parse import urlparse, parse_qs
import urllib.parse
from dotenv import load_dotenv

from google.adk.apps.app import App
from google.adk.runners import Runner
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.flows.llm_flows.functions import REQUEST_EUC_FUNCTION_CALL_NAME
from google.genai import types
from google.adk.auth.auth_credential import AuthCredential, AuthCredentialTypes, OAuth2Auth

from agent import root_agent
from interactive_auth_plugin import InteractiveAuthPlugin

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../../.env"))

# Global variable to store the captured callback URL
captured_callback_url = None

class AuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global captured_callback_url
        captured_callback_url = self.path
        
        # Send a nice response to the user
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<h1>Login Successful!</h1><p>You can close this window and return to the terminal.</p>")
        
        # Stop the server in a separate thread to avoid deadlock
        threading.Thread(target=self.server.shutdown).start()

def start_callback_server():
    server = HTTPServer(('localhost', 8080), AuthCallbackHandler)
    server.serve_forever()

async def main():
    app_name = 'weather_app'
    user_id = 'user1'
    
    # Load WIF Config from env vars
    project_number = os.environ.get("GOOGLE_PROJECT_NUMBER")
    pool_id = os.environ.get("WIF_POOL_ID")
    provider_id = os.environ.get("WIF_PROVIDER_ID")
    
    # Azure Configuration
    azure_client_id = os.environ.get("AZURE_CLIENT_ID")
    azure_tenant_id = os.environ.get("AZURE_TENANT_ID")

    if not all([project_number, pool_id, provider_id, azure_client_id, azure_tenant_id]):
        print("Missing WIF/Azure configuration in .env")
        return

    # Configure the Auth Plugin for Microsoft -> WIF
    auth_plugin = InteractiveAuthPlugin(
        project_number=project_number,
        pool_id=pool_id,
        provider_id=provider_id,
        tenant_id=azure_tenant_id,
        client_id=azure_client_id
    )
    
    # Create an App to hold the agent and the plugin
    app = App(
        name=app_name,
        root_agent=root_agent,
        plugins=[auth_plugin]
    )
    
    # Use generic Runner with explicit in-memory services
    runner = Runner(
        app=app,
        session_service=InMemorySessionService(),
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
        credential_service=InMemoryCredentialService()
    )
    
    # Create session manually (required for InMemoryRunner with explicit app)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id
    )
    
    user_query = "What is the weather like in New York?"
    print(f"\nUser: {user_query}")
    
    content = types.Content(
        role='user', parts=[types.Part.from_text(text=user_query)]
    )

    # We need to manage the loop manually to handle Auth requests
    events_iterator = runner.run_async(
        user_id=user_id,
        session_id=session.id,
        new_message=content,
    )
    
    async for event in events_iterator:
        # 1. Check if the Agent is asking for Credentials
        if event.get_function_calls():
            for fc in event.get_function_calls():
                if fc.name == "adk_request_credential":
                    print("\n" + "="*60)
                    print("AUTHENTICATION REQUIRED")
                    print("="*60)
                    
                    try:
                        # Correct path based on debug output:
                        # auth_scheme (snake) -> flows -> authorizationCode (camel) -> authorizationUrl (camel)
                        base_auth_url = fc.args['auth_scheme']['flows']['authorizationCode']['authorizationUrl']
                        scopes_dict = fc.args['auth_scheme']['flows']['authorizationCode']['scopes']
                        client_id = fc.args['raw_auth_credential']['oauth2']['client_id']
                    except KeyError:
                         # Fallback to camelCase if snake_case fails
                         try:
                             base_auth_url = fc.args['authScheme']['flows']['authorizationCode']['authorizationUrl']
                             scopes_dict = fc.args['authScheme']['flows']['authorizationCode']['scopes']
                             client_id = fc.args['raw_auth_credential']['oauth2']['client_id']
                         except KeyError:
                             print("Could not find Auth params in args.")
                             return

                    # Construct full URL with query parameters
                    scopes_str = " ".join(scopes_dict.keys())
                    params = {
                        "client_id": client_id,
                        "redirect_uri": "http://localhost:8080/auth/callback",
                        "response_type": "code",
                        "scope": scopes_str,
                    }
                    auth_url = f"{base_auth_url}?{urllib.parse.urlencode(params)}"

                    print(f"\nOpening browser for login: {auth_url}")
                    
                    # Start local server to catch the callback
                    server_thread = threading.Thread(target=start_callback_server)
                    server_thread.start()
                    
                    # Open browser
                    webbrowser.open(auth_url)
                    
                    print("\nWaiting for callback on localhost:8080...")
                    server_thread.join() # Wait for the server to stop (which happens after callback) 
                    
                    print("\n[System] Callback received!")
                    full_callback_url = f"http://localhost:8080{captured_callback_url}"

                    # 1. Extract the code from the URL
                    parsed_url = urlparse(full_callback_url)
                    code = parse_qs(parsed_url.query).get('code', [None])[0]
                    
                    if code:
                         print(f"\n[System] Extracted Auth Code: {code[:10]}...")
                         
                         # 2. EXCHANGE CODE FOR MICROSOFT TOKEN
                         # Microsoft requires this exchange to happen via POST
                         print("[System] Exchanging code for Microsoft Token...")
                         import requests
                         token_url = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/token"
                         token_data = {
                             "client_id": azure_client_id,
                             "client_secret": os.environ.get("WIF_CLIENT_SECRET"),
                             "code": code,
                             "grant_type": "authorization_code",
                             "redirect_uri": "http://localhost:8080/auth/callback",
                             "scope": "openid email profile"
                         }
                         token_res = requests.post(token_url, data=token_data)
                         token_json = token_res.json()
                         
                         if "access_token" not in token_json:
                             print(f"FAILED to get MS Token: {token_json}")
                             return
                             
                         ms_token = token_json.get("id_token") or token_json.get("access_token")
                         print(f"[System] Got Microsoft Token! (Type: {'id_token' if 'id_token' in token_json else 'access_token'})")

                         # 3. CREATE AND SAVE CREDENTIAL TO SERVICE MANUALLY
                         new_cred = AuthCredential(
                            auth_type=AuthCredentialTypes.OAUTH2,
                            oauth2=OAuth2Auth(
                                access_token=ms_token, # Now it's a real token!
                                client_id=azure_client_id,
                                redirect_uri="http://localhost:8080/auth/callback"
                            )
                         )
                         
                         # Directly populate the internal dictionary of the in-memory service 
                         if app_name not in runner.credential_service._credentials:
                             runner.credential_service._credentials[app_name] = {}
                         if user_id not in runner.credential_service._credentials[app_name]:
                             runner.credential_service._credentials[app_name][user_id] = {}
                         
                         runner.credential_service._credentials[app_name][user_id]["microsoft_credentials"] = new_cred
                         print("[System] Credential saved to service!")

                    # Construct the response content to send back to ADK
                    # We need to update the auth_config with the response URI
                    auth_config_resp = fc.args.copy()
                    auth_config_resp['auth_response_uri'] = full_callback_url
                    auth_config_resp['redirect_uri'] = "http://localhost:8080/auth/callback"

                    # Create a FunctionResponse for 'adk_request_credential'
                    resp_part = types.Part(
                        function_response=types.FunctionResponse(
                            name=REQUEST_EUC_FUNCTION_CALL_NAME,
                            id=fc.id,
                            response=auth_config_resp
                        )
                    )
                    
                    print("\n[System] Sending credentials back to ADK for exchange...")
                    
                    # Run the agent again with the function response
                    # ADK's AuthPreProcessor will intercept this and perform the exchange!
                    events_iterator = runner.run_async(
                        user_id=user_id,
                        session_id=session.id,
                        new_message=types.Content(role='user', parts=[resp_part]),
                    )
                    # We continue the outer loop with the new iterator
                    continue 

        # 2. Print Agent Responses
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"Agent: {part.text}")
                if part.function_call:
                    print(f"[System] Tool Call: {part.function_call.name}")

if __name__ == "__main__":
    asyncio.run(main())