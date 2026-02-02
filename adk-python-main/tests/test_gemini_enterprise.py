import pytest
from unittest.mock import MagicMock, patch
from google.adk.models.gemini_enterprise_llm import GeminiEnterprise
from google.adk.models.llm_request import LlmRequest
from google.genai import types

@pytest.mark.asyncio
async def test_gemini_enterprise_initialization():
    model = GeminiEnterprise(project_id="test-project", engine_id="test-engine")
    assert model.project_id == "test-project"
    assert model.engine_id == "test-engine"
    assert model.model == "gemini-enterprise"

@pytest.mark.asyncio
async def test_gemini_enterprise_generate_content_no_project():
    model = GeminiEnterprise()
    request = LlmRequest(contents=[types.Content(parts=[types.Part(text="hello")])])
    with pytest.raises(ValueError, match="project_id and engine_id must be provided"):
        async for _ in model.generate_content_async(request):
            pass

@pytest.mark.asyncio
async def test_gemini_enterprise_generate_content_success():
    model = GeminiEnterprise(project_id="p", engine_id="e")
    request = LlmRequest(contents=[types.Content(parts=[types.Part(text="hello")])])
    
    # Mock the AssistantServiceClient
    with patch("google.cloud.discoveryengine_v1.AssistantServiceClient") as MockClient:
        mock_client = MockClient.return_value
        mock_client.assistant_path.return_value = "projects/p/locations/l/collections/c/engines/e/assistants/a"
        
        # Mock the stream_assist response
        mock_response = MagicMock()
        mock_response.answer.replies = [
            MagicMock(grounded_content=MagicMock(content=MagicMock(text="Mocked answer")))
        ]
        mock_response.session_info.session = "mock-session-id"

        mock_client.stream_assist.return_value = [mock_response]
        
        responses = []
        async for resp in model.generate_content_async(request, stream=True):
            responses.append(resp)
            
        assert len(responses) == 2 # 1 partial, 1 final
        assert responses[0].content.parts[0].text == "Mocked answer"
        assert responses[0].partial is True
        assert responses[1].content.parts[0].text == "Mocked answer"
        assert responses[1].partial is False
        assert model._session_id == "mock-session-id"