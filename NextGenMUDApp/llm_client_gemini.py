"""
Google Gemini LLM Client

Concrete implementation of LLMClient for Google's Gemini API.
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
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    GenerationConfig = None


class GeminiModel(Enum):
    """Available Gemini model variants."""
    GEMINI_2_FLASH = "gemini-2.0-flash"
    GEMINI_2_FLASH_LITE = "gemini-2.0-flash-lite"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_8B = "gemini-1.5-flash-8b"


class GeminiClient(LLMClient):
    """
    Client for interacting with Google's Gemini LLM.
    
    Implements the LLMClient interface for the Gemini API.
    
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
                "google-generativeai package is not installed. "
                "Install with: pip install google-generativeai"
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
        
        # Configure the API
        genai.configure(api_key=self._api_key)
        
        # Initialize the model
        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=self._system_instruction,
        )
    
    def set_system_instruction(self, instruction: Optional[str]) -> None:
        """
        Update the system instruction and reinitialize the model.
        
        Args:
            instruction: New system instruction, or None to remove.
        """
        self._system_instruction = instruction
        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=self._system_instruction,
        )
    
    def _to_gemini_config(self, config: LLMConfig) -> 'GenerationConfig':
        """Convert LLMConfig to Gemini GenerationConfig."""
        return GenerationConfig(
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
            stop_sequences=config.stop_sequences,
        )
    
    def _message_to_gemini_format(self, message: LLMMessage) -> Dict[str, Any]:
        """Convert LLMMessage to Gemini's expected message format."""
        # Gemini uses "user" and "model" roles
        gemini_role = "model" if message.role == "assistant" else message.role
        return {"role": gemini_role, "parts": [message.content]}
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse a Gemini response into an LLMResponse object."""
        # Extract content
        content = ""
        finish_reason = None
        
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                content = "".join(
                    part.text for part in candidate.content.parts 
                    if hasattr(part, 'text')
                )
            if hasattr(candidate, 'finish_reason'):
                finish_reason = str(candidate.finish_reason)
        else:
            content = response.text if hasattr(response, 'text') else ""
        
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
            response = self._model.generate_content(
                prompt,
                generation_config=generation_config,
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
            response = await self._model.generate_content_async(
                prompt,
                generation_config=generation_config,
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
            history = [self._message_to_gemini_format(msg) for msg in messages[:-1]]
            
            # Start a new chat with history
            chat = self._model.start_chat(history=history)
            
            # Send the last message
            last_message = messages[-1].content if messages else ""
            response = chat.send_message(
                last_message,
                generation_config=generation_config,
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
            history = [self._message_to_gemini_format(msg) for msg in messages[:-1]]
            
            # Start a new chat with history
            chat = self._model.start_chat(history=history)
            
            # Send the last message asynchronously
            last_message = messages[-1].content if messages else ""
            response = await chat.send_message_async(
                last_message,
                generation_config=generation_config,
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
            response = self._model.generate_content(
                prompt,
                generation_config=generation_config,
                stream=True,
            )
            
            for chunk in response:
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
            response = await self._model.generate_content_async(
                prompt,
                generation_config=generation_config,
                stream=True,
            )
            
            async for chunk in response:
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
            history = [self._message_to_gemini_format(msg) for msg in messages[:-1]]
            
            # Start a new chat with history
            chat = self._model.start_chat(history=history)
            
            # Send the last message with streaming
            last_message = messages[-1].content if messages else ""
            response = chat.send_message(
                last_message,
                generation_config=generation_config,
                stream=True,
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            raise LLMAPIError(f"Streaming chat failed: {e}") from e
    
    # --- Token Counting ---
    
    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        try:
            result = self._model.count_tokens(text)
            return result.total_tokens
        except Exception as e:
            raise LLMAPIError(f"Token counting failed: {e}") from e
    
    def count_message_tokens(self, messages: List[LLMMessage]) -> int:
        """Count the number of tokens in a list of messages."""
        try:
            contents = [self._message_to_gemini_format(msg) for msg in messages]
            result = self._model.count_tokens(contents)
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
