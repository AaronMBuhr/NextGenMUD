"""
Google Gemini LLM Client

Concrete implementation of LLMClient for Google's Gemini API.
Uses the new google-genai SDK.
"""

import os
from typing import Optional, List, Dict, Any, Generator, AsyncGenerator, Union
from enum import Enum

from .llm_client import (
    LLMClient, LLMMessage, LLMResponse, LLMConfig,
    LLMClientError, LLMAPIError, LLMConfigError,
    register_provider
)


try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    types = None


class GeminiModel(Enum):
    """Available Gemini model variants."""
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_FLASH = "gemini-2.0-flash"
    GEMINI_2_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_8B = "gemini-1.5-flash-8b"


class GeminiClient(LLMClient):
    """
    Client for interacting with Google's Gemini LLM.
    
    Implements the LLMClient interface for the Gemini API using the new google-genai SDK.
    
    Example usage:
        client = GeminiClient(api_key="your-api-key")
        
        # Simple text generation
        response = client.generate("Tell me a joke")
        print(response.content)
        
        # Chat with history
        messages = [
            LLMMessage(role="user", content="Hello!"),
            LLMMessage(role="assistant", content="Hi there! How can I help?"),
            LLMMessage(role="user", content="What's the weather like?"),
        ]
        response = client.chat(messages)
        
        # Streaming
        for chunk in client.generate_stream("Write a story"):
            print(chunk, end="", flush=True)
    """
    
    DEFAULT_MODEL = GeminiModel.GEMINI_2_FLASH
    
    # Environment variable names for API key
    ENV_VAR_NAMES = ["GOOGLE_API_KEY", "GEMINI_API_KEY"]
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Union[str, GeminiModel, None] = None,
        system_instruction: Optional[str] = None,
        default_config: Optional[LLMConfig] = None,
    ):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Google API key. If not provided, will look for
                     GOOGLE_API_KEY or GEMINI_API_KEY environment variables.
            model: The Gemini model to use. Can be a GeminiModel enum or string.
                   Defaults to GEMINI_2_FLASH.
            system_instruction: Optional system instruction to set context.
            default_config: Default generation configuration.
        """
        if not GEMINI_AVAILABLE:
            raise LLMConfigError(
                "google-genai package is not installed. "
                "Install with: pip install google-genai"
            )
        
        # Resolve API key
        resolved_api_key = api_key
        if not resolved_api_key:
            for env_var in self.ENV_VAR_NAMES:
                resolved_api_key = os.environ.get(env_var)
                if resolved_api_key:
                    break
        
        if not resolved_api_key:
            raise LLMConfigError(
                "API key is required. Provide it directly or set "
                f"{' or '.join(self.ENV_VAR_NAMES)} environment variable."
            )
        
        # Resolve model name
        if model is None:
            model_name = self.DEFAULT_MODEL.value
        elif isinstance(model, GeminiModel):
            model_name = model.value
        else:
            model_name = model
        
        # Initialize base class
        super().__init__(
            api_key=resolved_api_key,
            model=model_name,
            system_instruction=system_instruction,
            default_config=default_config or LLMConfig(),
        )
        
        # Create the client
        self._client = genai.Client(api_key=self._api_key)
    
    def close(self) -> None:
        """
        Close the client and release resources.
        
        This should be called when the client is no longer needed to properly
        shut down the underlying httpx client and its ThreadPoolExecutor.
        """
        if self._client is not None:
            # The genai.Client may have an httpx client that needs closing
            if hasattr(self._client, '_http_client') and self._client._http_client is not None:
                try:
                    self._client._http_client.close()
                except Exception:
                    pass
            # Also try closing any async client
            if hasattr(self._client, '_async_http_client') and self._client._async_http_client is not None:
                try:
                    # Note: For async client, you'd need to await aclose() in an async context
                    pass
                except Exception:
                    pass
            self._client = None
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.close()
    
    def set_system_instruction(self, instruction: Optional[str]) -> None:
        """
        Update the system instruction.
        
        Args:
            instruction: New system instruction, or None to remove.
        """
        self._system_instruction = instruction
    
    def _to_gemini_config(self, config: LLMConfig) -> 'types.GenerateContentConfig':
        """Convert LLMConfig to Gemini GenerateContentConfig."""
        return types.GenerateContentConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
            stop_sequences=config.stop_sequences if config.stop_sequences else None,
            system_instruction=self._system_instruction,
        )
    
    def _message_to_gemini_content(self, message: LLMMessage) -> 'types.Content':
        """Convert LLMMessage to Gemini Content format."""
        # Gemini uses "user" and "model" roles
        gemini_role = "model" if message.role == "assistant" else message.role
        return types.Content(
            role=gemini_role,
            parts=[types.Part.from_text(text=message.content)]
        )
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse a Gemini response into an LLMResponse object."""
        # Extract content using the simple .text accessor
        content = ""
        finish_reason = None
        
        try:
            content = response.text or ""
        except Exception:
            # Fallback to parsing candidates
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        content = "".join(
                            part.text for part in candidate.content.parts 
                            if hasattr(part, 'text') and part.text
                        )
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = str(candidate.finish_reason)
        
        # Extract usage metadata if available
        usage = None
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
            }
        
        return LLMResponse(
            content=content,
            model=self._model_name,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=response,
        )
    
    # --- Core Generation Methods ---
    
    def generate(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Generate a response for a single prompt."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=generation_config,
            )
            return self._parse_response(response)
        except Exception as e:
            raise LLMAPIError(f"Generation failed: {e}") from e
    
    async def generate_async(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Asynchronously generate a response for a single prompt."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=generation_config,
            )
            return self._parse_response(response)
        except Exception as e:
            raise LLMAPIError(f"Async generation failed: {e}") from e
    
    # --- Chat Methods ---
    
    def chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Generate a response given a conversation history."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            
            # Convert messages to Gemini format
            contents = [self._message_to_gemini_content(msg) for msg in messages]
            
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=generation_config,
            )
            
            return self._parse_response(response)
        except Exception as e:
            raise LLMAPIError(f"Chat failed: {e}") from e
    
    async def chat_async(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Asynchronously generate a response given a conversation history."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            
            # Convert messages to Gemini format
            contents = [self._message_to_gemini_content(msg) for msg in messages]
            
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=generation_config,
            )
            
            return self._parse_response(response)
        except Exception as e:
            raise LLMAPIError(f"Async chat failed: {e}") from e
    
    # --- Streaming Methods ---
    
    def generate_stream(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> Generator[str, None, None]:
        """Generate a streaming response for a single prompt."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            
            for chunk in self._client.models.generate_content_stream(
                model=self._model_name,
                contents=prompt,
                config=generation_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise LLMAPIError(f"Streaming generation failed: {e}") from e
    
    async def generate_stream_async(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> AsyncGenerator[str, None]:
        """Asynchronously generate a streaming response for a single prompt."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            
            async for chunk in self._client.aio.models.generate_content_stream(
                model=self._model_name,
                contents=prompt,
                config=generation_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise LLMAPIError(f"Async streaming generation failed: {e}") from e
    
    def chat_stream(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> Generator[str, None, None]:
        """Generate a streaming response given a conversation history."""
        try:
            generation_config = self._to_gemini_config(config or self._default_config)
            
            # Convert messages to Gemini format
            contents = [self._message_to_gemini_content(msg) for msg in messages]
            
            for chunk in self._client.models.generate_content_stream(
                model=self._model_name,
                contents=contents,
                config=generation_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise LLMAPIError(f"Streaming chat failed: {e}") from e
    
    # --- Token Counting ---
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        try:
            result = self._client.models.count_tokens(
                model=self._model_name,
                contents=text,
            )
            return result.total_tokens
        except Exception as e:
            raise LLMAPIError(f"Token counting failed: {e}") from e
    
    def count_message_tokens(self, messages: List[LLMMessage]) -> int:
        """Count the number of tokens in a list of messages."""
        try:
            contents = [self._message_to_gemini_content(msg) for msg in messages]
            result = self._client.models.count_tokens(
                model=self._model_name,
                contents=contents,
            )
            return result.total_tokens
        except Exception as e:
            raise LLMAPIError(f"Message token counting failed: {e}") from e


# Register this provider
register_provider("gemini", GeminiClient)


# Factory function for easy instantiation (backwards compatibility)
def create_gemini_client(
    api_key: Optional[str] = None,
    model: Union[str, GeminiModel] = GeminiModel.GEMINI_2_FLASH,
    **kwargs
) -> GeminiClient:
    """
    Create a GeminiClient instance.
    
    Args:
        api_key: Google API key (optional, will use env var if not provided).
        model: Model to use.
        **kwargs: Additional arguments passed to GeminiClient.
        
    Returns:
        Configured GeminiClient instance.
    """
    return GeminiClient(api_key=api_key, model=model, **kwargs)
