# ADK Python Fork: Gemini Enterprise & WIF Authentication

This is an extended fork of the [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/) for Python. It adds first-class support for **Gemini Enterprise (StreamAssist)** and **Workforce Identity Federation (WIF)** for secure, identity-aware agentic workflows.

## 🚀 Key Features

- **Gemini Enterprise Model:** Native `GeminiEnterprise` class in `google.adk.models` that connects to the StreamAssist API (Grounded Search/Discovery Engine).
- **Tool Emulation Layer:** Support for standard ADK tools within Gemini Enterprise, featuring automatic JSON instruction injection and greedy regex-based response parsing.
- **WIF Authentication Plugin:** A robust `InteractiveAuthPlugin` that handles Microsoft Entra ID (Azure AD) login and performs server-side exchange for Google Access Tokens via STS.
- **Stateful Conversational Continuity:** Automatic management of StreamAssist `session_id` for multi-turn grounded conversations.

## 📁 Project Structure

- `src/google/adk/models/gemini_enterprise_llm.py`: Core model implementation.
- `contributing/samples/weather_agent_ge/`: A complete sample agent demonstrating the grounded weather tool and WIF authentication.
- `PRD_Gemini_Enterprise_Integration.md`: Detailed product requirements and technical architecture.
- `HISTORY.md`: Chronological implementation and technical decision log.

## 🛠 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- A Google Cloud Project with **Discovery Engine API** enabled.
- A **Workforce Identity Pool** and **Provider** (OIDC) configured in GCP.
- An **Azure App Registration** (Microsoft Entra ID) for authentication.

### 2. Environment Configuration
Copy the template and fill in your credentials:
```bash
cp .env.example .env
```

Ensure your `.env` contains:
- `GOOGLE_CLOUD_PROJECT` & `GOOGLE_PROJECT_NUMBER`
- `GEMINI_ENTERPRISE_ENGINE_ID`
- `WIF_POOL_ID` & `WIF_PROVIDER_ID`
- `AZURE_CLIENT_ID` & `AZURE_TENANT_ID`
- `WIF_CLIENT_SECRET` (Azure App Secret)

### 3. Local Development
1. Navigate to the sample directory:
   ```bash
   cd adk-python-main/contributing/samples/weather_agent_ge
   ```
2. Activate your virtual environment and run the test:
   ```bash
   python3 main.py
   ```

## 🔐 Authentication Flow (WIF)
The integration follows a secure 6-step identity federation flow:
1. **User Login:** Interactive redirection to Microsoft Entra ID.
2. **Token Issuance:** App receives a Microsoft OIDC ID Token.
3. **STS Exchange:** The `InteractiveAuthPlugin` sends the MS token to Google Security Token Service.
4. **Validation:** Google validates the token against the Workforce Pool.
5. **Google Token Issuance:** STS returns a short-lived Google Access Token.
6. **API Execution:** The agent calls Gemini Enterprise using the federated user identity.

---
*Note: This is an independent fork and not an official Google product.*
