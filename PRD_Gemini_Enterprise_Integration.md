# Product Requirements Document (PRD): Gemini Enterprise Integration for ADK

## 1. Executive Summary
This project aims to integrate **Gemini Enterprise (StreamAssist)** as a supported model within the **Agent Development Kit (ADK)**. This integration enables ADK users to leverage their existing Gemini Enterprise infrastructure—including Data Stores, Engines, and the StreamAssist conversational API—as the underlying intelligence for ADK Agents. This facilitates "bring-your-own-infrastructure" scenarios where retrieval-augmented generation (RAG) and grounding are handled by the managed Gemini Enterprise service rather than manual orchestration within ADK.

## 2. Problem Statement
ADK currently relies on Vertex AI and Google AI Studio models (e.g., `gemini-pro`, `gemini-flash`) which require developers to manually implement retrieval (RAG) using ADK tools if they need access to private data. Enterprise customers often have pre-configured Gemini Enterprise engines (formerly Discovery Engine) that already index their corporate data and enforce security controls. There is currently no native way to point an ADK Agent at these existing engines, forcing redundant implementation or the use of raw, unabstracted API calls.

## 3. Goals & Objectives
*   **Native Integration:** Provide a seamless `GeminiEnterprise` class in `google.adk.models` that implements the standard `BaseLlm` interface.
*   **Conversational Continuity:** Support multi-turn conversations by correctly managing StreamAssist sessions (`session_id`) within the ADK agent loop.
*   **Streaming Support:** Enable real-time token streaming for a responsive user experience, mirroring the behavior of standard Gemini models.
*   **Zero-Config Authentication:** Automatically utilize Application Default Credentials (ADC) or ADK's native OAuth flow without manual token management.
*   **Environment-Based Configuration:** Support standard environment variables for configuration (`GOOGLE_CLOUD_PROJECT`, `GEMINI_ENTERPRISE_ENGINE_ID`) to simplify deployment.

## 4. Technical Specifications

### 4.1. Supported Model Class
*   **Class Name:** `GeminiEnterprise`
*   **Inheritance:** `google.adk.models.base_llm.BaseLlm`
*   **Registry Pattern:** `gemini-enterprise` (Regex match)

### 4.2. Configuration Parameters
The model must accept the following parameters in its constructor, with automatic fallbacks to environment variables:

| Parameter | Environment Variable | Description | Default |
| :--- | :--- | :--- | :--- |
| `project_id` | `GOOGLE_CLOUD_PROJECT` | Google Cloud Project ID | **Required** |
| `engine_id` | `GEMINI_ENTERPRISE_ENGINE_ID` | Gemini Enterprise App/Engine ID | **Required** |
| `location` | `GEMINI_ENTERPRISE_LOCATION` | Data store location (e.g., 'global', 'us') | `global` |
| `collection` | N/A | Resource collection ID | `default_collection` |
| `assistant` | N/A | Assistant ID | `default_assistant` |

### 4.3. API Integration
*   **Service:** `google.cloud.discoveryengine_v1.AssistantServiceClient`
*   **RPC Method:** `stream_assist`
*   **Request Mapping:**
    *   ADK `LlmRequest.contents` (last user message) → `StreamAssistRequest.query`.
    *   Internal state → `StreamAssistRequest.session` (to maintain context).
*   **Response Mapping:**
    *   `StreamAssistResponse` → ADK `LlmResponse`.
    *   Handling of `partial=True` for streaming chunks.
    *   Extraction of text content from `response.answer.replies[].grounded_content.content.text`.
    *   Filtering of `SKIPPED` or empty states (e.g., non-assist-seeking queries).

### 4.4. Authentication
The solution must use the `CredentialManager` and `credentials` object passed via the `LlmRequest` context to support:
1.  **Service Accounts:** Standard server-side execution (using ADC).
2.  **User Credentials (OAuth):** Client-side execution where the agent acts on behalf of a logged-in user.
3.  **Workforce Identity Federation (WIF):** Support for external Identity Providers (Microsoft Entra ID, Okta).
    *   **Architecture:** Implemented via an ADK Plugin (`InteractiveAuthPlugin`) that intercepts model requests.
    *   **Flow:**
        1.  Plugin detects missing/invalid credentials.
        2.  Triggers client-side login via standard OIDC (e.g., Microsoft Login).
        3.  Receives External ID Token (OIDC).
        4.  Exchanges External Token for Google Access Token via Google Security Token Service (STS).
        5.  Injects Google Token into `LlmRequest`.

## 5. Due Diligence & Compliance Matrix
Since `GeminiEnterprise` wraps a high-level SaaS API (`StreamAssist`) rather than a raw LLM API, several standard ADK assumptions must be adapted.

| ADK Feature | Support Status | Notes / Limitations |
| :--- | :--- | :--- |
| **Text Generation** | ✅ Supported | Full streaming support implemented. |
| **Tool Calling** | ⚠️ Emulated | **Critical:** StreamAssist does not support client-side tool definitions. We utilize a "Tool Emulation Layer" that injects system instructions and parses JSON output to simulate native behavior. |
| **System Instructions** | ⚠️ Injected | No native `system_instruction` field in request. Instructions are prepended to the user prompt. Long conversations might suffer from context window loss. |
| **Multimodal (Images)** | ❌ Unsupported | StreamAssist API expects `file_ids` (pre-uploaded files) rather than inline byte blobs. Standard ADK image parts will currently be ignored or cause errors. |
| **Session History** | ⚠️ Stateful | StreamAssist maintains state server-side. ADK's `LlmRequest` history is ignored in favor of `session_id`. **Risk:** "Rewinding" an ADK session does not rewind the server-side state. |
| **Grounding/Citations** | ⚠️ Partial | The model returns rich grounding metadata, but the current implementation extracts only text. **Future Work:** Map `grounding_metadata` to `LlmResponse` to show sources. |
| **JSON Mode** | ❌ Unsupported | No native `response_mime_type` support. Relies on prompt engineering. |
| **Safety Settings** | ✅ Managed | Safety is enforced by the Enterprise policy on the engine, not per-request config. |

### 5.1. State Management Deep Dive
The integration of a stateful SaaS API (StreamAssist) into a stateless LLM abstraction (ADK) introduces specific architectural behaviors that developers must understand:

#### The "Double History" & Rewind Paradox
*   **ADK Behavior:** ADK operates on a "stateless model" assumption. For every turn, it constructs the *entire* conversation history (User -> Model -> User) and sends it to the model. Features like "Rewind" work by simply truncating this list locally and sending the shorter list on the next turn.
*   **StreamAssist Behavior:** StreamAssist is **stateful**. It maintains a server-side session (`session_id`) that stores all previous turns. It expects only the *newest* query in each request.
*   **The Conflict:** Our implementation resolves this by ignoring ADK's history list and sending only the last message + `session_id`.
*   **Implication (Rewind Failure):** If a user triggers a "Rewind" in ADK, the local history is truncated, but the **server-side session remains unchanged**.
    *   *Example:* User says "My name is Bob". User rewinds. User asks "What is my name?". ADK thinks the context is empty, but StreamAssist (using the same `session_id`) remembers "Bob".
*   **Mitigation:** Developers using `GeminiEnterprise` should act with caution when using flow control features like rewinding or branching. To "forget" context, one must explicitly trigger a new session (e.g., by re-instantiating the model or manually clearing `model._session_id`).

## 6. Success Metrics
*   Successful instantiation of an Agent using `model=GeminiEnterprise()`.
*   End-to-end execution of a multi-turn conversation against a live Gemini Enterprise engine.
*   Correct rendering of streamed responses in the ADK CLI or UI.
*   Passing unit tests with >90% code coverage for the new model class.

## 7. Assumptions & Dependencies
*   The `google-cloud-discoveryengine` Python library is available and installed.
*   The target GCP project has the Discovery Engine API enabled.
*   The execution environment has valid credentials (ADC or OAuth).