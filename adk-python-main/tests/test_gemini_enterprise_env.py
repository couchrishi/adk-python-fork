
import pytest
import os
from unittest.mock import patch
from google.adk.models.gemini_enterprise_llm import GeminiEnterprise

@pytest.mark.asyncio
async def test_gemini_enterprise_env_vars():
    with patch.dict(os.environ, {
        "GOOGLE_CLOUD_PROJECT": "env-project",
        "GEMINI_ENTERPRISE_ENGINE_ID": "env-engine",
        "GEMINI_ENTERPRISE_LOCATION": "env-location"
    }):
        model = GeminiEnterprise()
        assert model.project_id == "env-project"
        assert model.engine_id == "env-engine"
        assert model.location == "env-location"

@pytest.mark.asyncio
async def test_gemini_enterprise_explicit_overrides_env():
    with patch.dict(os.environ, {
        "GOOGLE_CLOUD_PROJECT": "env-project",
        "GEMINI_ENTERPRISE_ENGINE_ID": "env-engine"
    }):
        model = GeminiEnterprise(project_id="explicit-project", engine_id="explicit-engine")
        assert model.project_id == "explicit-project"
        assert model.engine_id == "explicit-engine"
