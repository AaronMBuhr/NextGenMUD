"""
Abstract LLM Client Base Class

Provides a common interface for LLM providers (Gemini, OpenAI, Claude, etc.)
Concrete implementations inherit from LLMClient and implement provider-specific logic.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Generator, AsyncGenerator, Union


@dataclass
class LLMMessage:
    """Represents a message in a conversation."""
    role: str  # "user", "assistant", or "system"
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to a basic dictionary format."""
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """Represents a response from the LLM."""
    content: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    raw_response: Optional[Any] = None
    
    @property
    def prompt_tokens(self) -> Optional[int]:
        """Get prompt token count if available."""
        if self.usage:
            return self.usage.get("prompt_tokens")
        return None
    
    @property
    def completion_tokens(self) -> Optional[int]:
        """Get completion token count if available."""
        if self.usage:
            return self.usage.get("completion_tokens")
        return None
    
    @property
    def total_tokens(self) -> Optional[int]:
        """Get total token count if available."""
        if self.usage:
            return self.usage.get("total_tokens")
        return None


@dataclass
class LLMConfig:
    """Configuration for LLM generation."""
    temperature: float = 0.7
    max_output_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "stop_sequences": self.stop_sequences,
        }.items() if v is not None}


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class LLMAPIError(LLMClientError):
    """Exception raised when the LLM API returns an error."""
    pass


class LLMConfigError(LLMClientError):
    """Exception raised for configuration errors."""
    pass


class LLMClient(ABC):
    """
    Abstract base class for LLM clients.
    
    Provides a common interface for different LLM providers.
    Subclasses must implement the abstract methods for their specific provider.
    
    Example usage with a concrete implementation:
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
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        system_instruction: Optional[str] = None,
        default_config: Optional[LLMConfig] = None,
    ):
        """
        Initialize the LLM client.
        
        Args:
            api_key: API key for the provider. Subclasses define fallback env vars.
            model: The model to use. Subclasses define defaults.
            system_instruction: Optional system instruction to set context.
            default_config: Default generation configuration.
        """
        self._api_key = api_key
        self._model_name = model
        self._system_instruction = system_instruction
        self._default_config = default_config or LLMConfig()
    
    @property
    def model_name(self) -> str:
        """Get the current model name."""
        return self._model_name
    
    @property
    def system_instruction(self) -> Optional[str]:
        """Get the current system instruction."""
        return self._system_instruction
    
    @property
    def default_config(self) -> LLMConfig:
        """Get the default configuration."""
        return self._default_config
    
    @abstractmethod
    def set_system_instruction(self, instruction: Optional[str]) -> None:
        """
        Update the system instruction.
        
        Args:
            instruction: New system instruction, or None to remove.
        """
        raise NotImplementedError
    
    # --- Core Generation Methods ---
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Generate a response for a single prompt.
        
        Args:
            prompt: The input prompt/question.
            config: Optional generation config (uses default if not provided).
            
        Returns:
            LLMResponse containing the generated text and metadata.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    @abstractmethod
    async def generate_async(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Asynchronously generate a response for a single prompt.
        
        Args:
            prompt: The input prompt/question.
            config: Optional generation config (uses default if not provided).
            
        Returns:
            LLMResponse containing the generated text and metadata.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    # --- Chat Methods ---
    
    @abstractmethod
    def chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Generate a response given a conversation history.
        
        Args:
            messages: List of messages in the conversation.
            config: Optional generation config (uses default if not provided).
            
        Returns:
            LLMResponse containing the generated text and metadata.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    @abstractmethod
    async def chat_async(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Asynchronously generate a response given a conversation history.
        
        Args:
            messages: List of messages in the conversation.
            config: Optional generation config (uses default if not provided).
            
        Returns:
            LLMResponse containing the generated text and metadata.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    # --- Streaming Methods ---
    
    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response for a single prompt.
        
        Args:
            prompt: The input prompt/question.
            config: Optional generation config (uses default if not provided).
            
        Yields:
            String chunks as they are generated.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    @abstractmethod
    async def generate_stream_async(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Asynchronously generate a streaming response for a single prompt.
        
        Args:
            prompt: The input prompt/question.
            config: Optional generation config (uses default if not provided).
            
        Yields:
            String chunks as they are generated.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    @abstractmethod
    def chat_stream(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response given a conversation history.
        
        Args:
            messages: List of messages in the conversation.
            config: Optional generation config (uses default if not provided).
            
        Yields:
            String chunks as they are generated.
            
        Raises:
            LLMAPIError: If the API request fails.
        """
        raise NotImplementedError
    
    # --- Token Counting ---
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text: The text to count tokens for.
            
        Returns:
            Number of tokens.
            
        Raises:
            LLMAPIError: If token counting fails.
        """
        raise NotImplementedError
    
    @abstractmethod
    def count_message_tokens(self, messages: List[LLMMessage]) -> int:
        """
        Count the number of tokens in a list of messages.
        
        Args:
            messages: The messages to count tokens for.
            
        Returns:
            Total number of tokens across all messages.
            
        Raises:
            LLMAPIError: If token counting fails.
        """
        raise NotImplementedError
    
    # --- Convenience Methods (with default implementations) ---
    
    def ask(self, question: str, context: Optional[str] = None) -> str:
        """
        Simple question-answering interface.
        
        Args:
            question: The question to ask.
            context: Optional context to include with the question.
            
        Returns:
            The response text.
        """
        if context:
            prompt = f"Context:\n{context}\n\nQuestion: {question}"
        else:
            prompt = question
        
        response = self.generate(prompt)
        return response.content
    
    async def ask_async(self, question: str, context: Optional[str] = None) -> str:
        """
        Asynchronous simple question-answering interface.
        
        Args:
            question: The question to ask.
            context: Optional context to include with the question.
            
        Returns:
            The response text.
        """
        if context:
            prompt = f"Context:\n{context}\n\nQuestion: {question}"
        else:
            prompt = question
        
        response = await self.generate_async(prompt)
        return response.content
    
    def summarize(self, text: str, max_length: Optional[int] = None) -> str:
        """
        Summarize a piece of text.
        
        Args:
            text: The text to summarize.
            max_length: Optional maximum length hint for the summary.
            
        Returns:
            The summary.
        """
        if max_length:
            prompt = f"Please summarize the following text in approximately {max_length} words or less:\n\n{text}"
        else:
            prompt = f"Please summarize the following text concisely:\n\n{text}"
        
        response = self.generate(prompt)
        return response.content
    
    def extract_json(self, text: str, schema_hint: Optional[str] = None) -> str:
        """
        Extract structured JSON from text.
        
        Args:
            text: The text to extract data from.
            schema_hint: Optional hint about expected JSON structure.
            
        Returns:
            JSON string extracted from the text.
        """
        if schema_hint:
            prompt = f"Extract the following information as valid JSON. Expected format: {schema_hint}\n\nText:\n{text}\n\nRespond with only the JSON, no explanation."
        else:
            prompt = f"Extract the key information from the following text as valid JSON:\n\n{text}\n\nRespond with only the JSON, no explanation."
        
        response = self.generate(prompt, config=LLMConfig(temperature=0.1))
        return response.content.strip()


# Provider registry for factory function
_provider_registry: Dict[str, type] = {}


def register_provider(name: str, client_class: type) -> None:
    """Register an LLM provider class."""
    _provider_registry[name.lower()] = client_class


def get_provider(name: str) -> Optional[type]:
    """Get a registered provider class by name."""
    return _provider_registry.get(name.lower())


def list_providers() -> List[str]:
    """List all registered provider names."""
    return list(_provider_registry.keys())


def create_client(
    provider: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    **kwargs
) -> LLMClient:
    """
    Factory function to create an LLM client by provider name.
    
    Args:
        provider: Provider name (e.g., "gemini", "openai", "claude")
        api_key: Optional API key
        model: Optional model name
        **kwargs: Additional arguments passed to the client
        
    Returns:
        Configured LLMClient instance
        
    Raises:
        LLMConfigError: If provider is not registered
    """
    client_class = get_provider(provider)
    if client_class is None:
        available = ", ".join(list_providers()) or "none"
        raise LLMConfigError(
            f"Unknown provider '{provider}'. Available providers: {available}"
        )
    
    return client_class(api_key=api_key, model=model, **kwargs)
