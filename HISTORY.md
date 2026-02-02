
## Phase 7: Workforce Identity Federation (WIF) Integration
*   **Requirement:** Enable users to authenticate using their corporate Microsoft Entra ID credentials via Google Workforce Identity Federation, mirroring the behavior of the Gemini Enterprise web console.
*   **Challenge:** The standard ADK authentication flow (`OAuth2CredentialExchanger`) is built for Google OAuth2 and does not natively support the "External Identity -> Google STS Exchange" flow required for WIF.
*   **Solution: The `InteractiveAuthPlugin`:**
    *   Developed a custom ADK Plugin that implements `before_model_callback`.
    *   **Logic:** 
        1.  Checks if a valid credential exists in the session.
        2.  If not, emits an `adk_request_credential` tool call configured for the **Microsoft OIDC endpoint**.
        3.  Upon receiving the Microsoft ID Token, uses the `google-auth` library's `identity_pool.Credentials` to perform a token exchange with **Google STS**.
        4.  Injects the resulting Google Access Token into `LlmRequest.credentials`.
*   **Integration Challenges:**
    *   **Localhost Redirects:** Azure AD rejected `localhost` redirects from the test script.
    *   **Resolution:** Created a dedicated "ADK Agent Dev" App Registration in Azure and a corresponding WIF Provider in GCP to isolate the development environment from production.
    *   **Missing Fields:** `LlmRequest` in ADK lacked a `credentials` field. Added it to `src/google/adk/models/llm_request.py` to allow credential propagation.
    *   **STS Scopes:** The STS exchange initially failed with "Scope(s) must be provided." Fixed by explicitly requesting `https://www.googleapis.com/auth/cloud-platform`.
*   **Verification:** Successfully ran an end-to-end test where the user logged in via Microsoft, the plugin swapped the token, and Gemini Enterprise answered a query ("Weather in NY") using the federated identity.
