import logging
from typing import Optional
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.auth.auth_tool import AuthConfig
from google.adk.auth.auth_credential import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.auth.auth_schemes import AuthSchemeType, OAuth2
from fastapi.openapi.models import OAuthFlows, OAuthFlowAuthorizationCode
from google.adk.flows.llm_flows.functions import REQUEST_EUC_FUNCTION_CALL_NAME
from google.genai import types
from google.auth import identity_pool
import google.auth.transport.requests

logger = logging.getLogger(__name__)

class InteractiveAuthPlugin(BasePlugin):
    """
    Plugin that handles interactive authentication with Microsoft Entra ID
    and exchanges the token for Google Cloud credentials via WIF.
    """
    name = "InteractiveAuthPlugin"
    
    def __init__(self, project_number: str, pool_id: str, provider_id: str, tenant_id: str, client_id: str):
        self.project_number = project_number
        self.pool_id = pool_id
        self.provider_id = provider_id
        
        # Microsoft Entra ID Configuration
        auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        
        self.auth_config = AuthConfig(
            auth_scheme=OAuth2(
                type=AuthSchemeType.oauth2,
                flows=OAuthFlows(
                    authorizationCode=OAuthFlowAuthorizationCode(
                        authorizationUrl=auth_url,
                        tokenUrl=token_url,
                        # Request OIDC ID Token and Email
                        scopes={
                            "openid": "",
                            "email": "",
                            "profile": "",
                            "offline_access": "" # For Refresh Token
                        }
                    )
                )
            ),
            raw_auth_credential=AuthCredential(
                auth_type=AuthCredentialTypes.OAUTH2,
                oauth2=OAuth2Auth(
                    client_id=client_id,
                    # Use the WIF Callback URL that is already registered in Azure
                    redirect_uri=f"https://auth.cloud.google/signin-callback/locations/global/workforcePools/{pool_id}/providers/{provider_id}"
                )
            ),
            credential_key="microsoft_credentials"
        )

    async def before_model_callback(
        self,
        callback_context: CallbackContext,
        llm_request: LlmRequest
    ) -> Optional[LlmResponse]:
        """
        Check for MS credentials -> Exchange for Google -> Inject.
        """
        
        # 1. Try to load Microsoft credentials
        ms_credential = await callback_context.load_credential(self.auth_config)
        
        if not ms_credential:
            logger.info("Microsoft credentials not found. Triggering login.")
            fc_part = types.Part(
                function_call=types.FunctionCall(
                    name=REQUEST_EUC_FUNCTION_CALL_NAME,
                    args=self.auth_config.model_dump(mode='json', exclude_none=True)
                )
            )
            return LlmResponse(content=types.Content(role="model", parts=[fc_part]))
        
        else:
            logger.info("Microsoft credentials found! Exchanging for Google Token via WIF...")
            
            # 2. Perform WIF Exchange
            try:
                # We need the ID Token (preferred) or Access Token.
                # ADK's OAuth2 implementation might store the ID Token in 'id_token' field if customized,
                # but standard OAuth2Auth only has access_token.
                # HOWEVER, for Entra ID, the access_token is often a JWT that *might* work,
                # but WIF usually demands an OIDC ID Token.
                
                # Let's assume access_token holds the token we need to exchange.
                subject_token = ms_credential.oauth2.access_token
                
                # Construct Audience string for STS
                # Canonical format for WIF: //iam.googleapis.com/locations/global/workforcePools/{pool}/providers/{provider}
                audience = f"//iam.googleapis.com/locations/global/workforcePools/{self.pool_id}/providers/{self.provider_id}"
                
                # Use google-auth to exchange
                # Define a supplier class to return our token
                class TokenSupplier:
                    def get_subject_token(self, credentials, request):
                        return subject_token

                google_creds = identity_pool.Credentials(
                    audience=audience,
                    subject_token_type="urn:ietf:params:oauth:token-type:id_token", # Using ID Token
                    token_url="https://sts.googleapis.com/v1/token",
                    credential_source=None,
                    subject_token_supplier=TokenSupplier(),
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                
                # Force refresh to get the actual Google token
                request = google.auth.transport.requests.Request()
                google_creds.refresh(request)
                
                logger.info("Successfully exchanged for Google Token!")
                
                # 3. Inject the GOOGLE Credentials into the request
                # We wrap the google_creds (which is a google.auth.credentials.Credentials object)
                # into something GeminiEnterprise expects.
                # GeminiEnterprise expects 'llm_request.credentials' to be an ADK AuthCredential?
                # No, GeminiEnterprise uses 'llm_request.credentials' to call 'discoveryengine'.
                # 'discoveryengine' client accepts google.auth.credentials.Credentials!
                
                # So we can just overwrite it.
                llm_request.credentials = google_creds
                
                return None

            except Exception as e:
                logger.error(f"WIF Exchange Failed: {e}")
                # If exchange fails, maybe token expired? Trigger re-login?
                # For now, let it crash or return error to user.
                raise e
