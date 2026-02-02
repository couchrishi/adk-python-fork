# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from functools import cached_property
import logging
from typing import AsyncGenerator, Optional, TYPE_CHECKING

from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine_v1 as discoveryengine
from google.genai import types
from typing_extensions import override

from .base_llm import BaseLlm
from .llm_response import LlmResponse

if TYPE_CHECKING:
    from .llm_request import LlmRequest

logger = logging.getLogger('google_adk.' + __name__)

class GeminiEnterprise(BaseLlm):
    """Integration for Gemini Enterprise (StreamAssist) models.

    Attributes:
        project_id: The Google Cloud project ID.
        location: The location of the data store (e.g., 'global', 'us', 'eu').
        engine_id: The unique identifier for the Gemini Enterprise app.
        collection: The collection ID (default is 'default_collection').
        assistant: The assistant ID (default is 'default_assistant').
    """

    model: str = 'gemini-enterprise'
    project_id: Optional[str] = None
    location: str = 'global'
    engine_id: Optional[str] = None
    collection: str = 'default_collection'
    assistant: str = 'default_assistant'

    # Session state to maintain conversation context
    _session_id: Optional[str] = None

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        engine_id: Optional[str] = None,
        collection: Optional[str] = None,
        assistant: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        import os
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.environ.get("GEMINI_ENTERPRISE_LOCATION", "global")
        self.engine_id = engine_id or os.environ.get("GEMINI_ENTERPRISE_ENGINE_ID")
        if collection:
            self.collection = collection
        if assistant:
            self.assistant = assistant

    @classmethod
    @override
    def supported_models(cls) -> list[str]:
        return [r'gemini-enterprise']

    @override
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Sends a request to the Gemini Enterprise StreamAssist API.

        Args:
            llm_request: LlmRequest, the request to send.
            stream: bool = False, whether to do streaming call.

        Yields:
            LlmResponse: The model response.
        """
        if not self.project_id or not self.engine_id:
            raise ValueError("project_id and engine_id must be provided for GeminiEnterprise.")

        # StreamAssist handles its own history via session_id.
        # We take the latest message from llm_request as the query.
        if not llm_request.contents:
            raise ValueError("No content provided in LlmRequest.")
        
        last_content = llm_request.contents[-1]
        query_text = ""
        for part in last_content.parts:
            if part.text:
                query_text += part.text

        # --- Tool Emulation Layer: Instruction Injection ---
        tool_instruction = ""
        if llm_request.config and llm_request.config.tools:
            tool_definitions = []
            for tool in llm_request.config.tools:
                if tool.function_declarations:
                    for func in tool.function_declarations:
                        # Simple schema description
                        params = func.parameters.properties if func.parameters else {}
                        param_str = ", ".join([f"{k}" for k in params.keys()])
                        tool_definitions.append(f"- `{func.name}({param_str})`: {func.description}")
            
            if tool_definitions:
                tool_instruction = (
                    "\n\nSYSTEM INSTRUCTION: You have access to the following tools:\n" +
                    "\n".join(tool_definitions) +
                    "\nTo use a tool, you MUST output a JSON object with this EXACT format:\n"
                    '```json\n{"tool": "function_name", "parameters": {"param_name": "value"}}\n```\n'
                    "If you use a tool, do not output any other text."
                )
                query_text += tool_instruction

        # Support native OAuth by passing credentials if available in LlmRequest
        # ADK's LlmAgent usually populates credentials in the llm_request.
        credentials = getattr(llm_request, 'credentials', None)

        client_options = (
            ClientOptions(api_endpoint=f"{self.location}-discoveryengine.googleapis.com")
            if self.location != "global"
            else None
        )
        client = discoveryengine.AssistantServiceClient(
            client_options=client_options,
            credentials=credentials
        )

        request = discoveryengine.StreamAssistRequest(
            name=client.assistant_path(
                project=self.project_id,
                location=self.location,
                collection=self.collection,
                engine=self.engine_id,
                assistant=self.assistant,
            ),
            query=discoveryengine.Query(text=query_text),
            session=self._session_id,
        )

        logger.info(
            'Sending request to Gemini Enterprise (StreamAssist), project: %s, engine: %s',
            self.project_id,
            self.engine_id,
        )

        # The discoveryengine Python SDK's stream_assist is a sync generator in v1.
        # To make it async-friendly in ADK, we can wrap the iteration.
        # Note: If there's an async version of AssistantServiceClient, we should use it.
        # Let's check if AssistantServiceAsyncClient exists.
        
        # For now, let's implement using the sync stream but yield as chunks.
        responses = client.stream_assist(request=request)

        full_answer = ""
        import json
        import re

        for response in responses:
            # Update session ID if provided in the response
            if response.session_info and response.session_info.session:
                self._session_id = response.session_info.session
            
            # Handle empty/skipped responses
            if not response.answer or not response.answer.replies:
                continue

            chunk_text = ""
            for reply in response.answer.replies:
                # Check for grounded_content.content.text
                # We need to access attributes safely as they might be optional
                if hasattr(reply, 'grounded_content') and hasattr(reply.grounded_content, 'content'):
                     content = reply.grounded_content.content
                     if content and content.text:
                         chunk_text += content.text

            if not chunk_text:
                continue

            full_answer += chunk_text
            
            if stream:
                # Yield partial response (text)
                yield LlmResponse(
                    content=types.Content(
                        role='model',
                        parts=[types.Part(text=chunk_text)]
                    ),
                    partial=True
                )

        # --- Tool Emulation Layer: Output Parsing ---
        # Check if the full response contains a JSON tool call
        # We look for the ```json ... ``` block or just a raw JSON object
        tool_call_part = None
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', full_answer, re.DOTALL)
        if not json_match:
             # Look for the first valid JSON object start/end (Greedy to capture nested braces)
             json_match = re.search(r'(\{.*"tool".*\})', full_answer, re.DOTALL)

        if json_match:
            try:
                tool_data = json.loads(json_match.group(1))
                if "tool" in tool_data and "parameters" in tool_data:
                    # It's a valid tool call!
                    tool_call_part = types.Part(
                        function_call=types.FunctionCall(
                            name=tool_data["tool"],
                            args=tool_data["parameters"]
                        )
                    )
            except json.JSONDecodeError:
                pass

        if tool_call_part:
            # Yield final response as a FunctionCall
            yield LlmResponse(
                content=types.Content(
                    role='model',
                    parts=[tool_call_part]
                ),
                partial=False
            )
        else:
            # Yield final consolidated response as Text
            yield LlmResponse(
                content=types.Content(
                    role='model',
                    parts=[types.Part(text=full_answer)]
                ),
                partial=False
            )

    def reset_session(self):
        """Resets the conversation session."""
        self._session_id = None
