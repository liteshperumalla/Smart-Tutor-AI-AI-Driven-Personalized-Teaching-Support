"""LlamaIndex-compatible wrapper for Bedrock LLM"""

from typing import Any, Callable, Optional, Sequence
from llama_index.core.llms import (
    LLM,
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
)
from llama_index.core.llms.callbacks import llm_completion_callback, llm_chat_callback
from backend.bedrock_llm import BedrockLLM as BedrockLLMCore
from backend.config import config


class BedrockLLM(LLM):
    """LlamaIndex-compatible wrapper for AWS Bedrock LLM"""

    _llm_type: str = "bedrock"

    model_id: str
    region: str

    def __init__(
        self,
        model_id: str = None,
        region: str = None,
        **kwargs: Any
    ):
        model_id = model_id or config.BEDROCK_MODEL_ID
        region = region or config.AWS_REGION
        super().__init__(model_id=model_id, region=region, **kwargs)
        self._bedrock = BedrockLLMCore(model_id=self.model_id, region=self.region)

    def _get_model_capabilities(self) -> tuple[int, int]:
        """Get context window and max output tokens based on model ID"""
        model_lower = self.model_id.lower()

        # Claude models
        if "claude-3-5-sonnet" in model_lower or "claude-3-sonnet" in model_lower:
            return (200000, 8192)  # Claude 3.5 Sonnet / Claude 3 Sonnet
        elif "claude-3-opus" in model_lower:
            return (200000, 4096)  # Claude 3 Opus
        elif "claude-3-haiku" in model_lower:
            return (200000, 4096)  # Claude 3 Haiku
        elif "claude-2" in model_lower:
            return (100000, 4096)  # Claude 2.x
        elif "claude" in model_lower:
            return (100000, 4096)  # Other Claude models

        # Llama models
        elif "llama3" in model_lower or "llama-3" in model_lower:
            if "70b" in model_lower or "405b" in model_lower:
                return (8192, 2048)  # Llama 3 larger models
            return (8192, 2048)  # Llama 3 default
        elif "llama2" in model_lower or "llama-2" in model_lower:
            return (4096, 2048)  # Llama 2

        # Mistral models
        elif "mistral" in model_lower:
            return (32000, 8192)  # Mistral models

        # Titan models
        elif "amazon.titan" in model_lower:
            return (32000, 4096)  # Titan Text models

        # Default fallback
        else:
            return (4096, 2048)  # Conservative default
    
    @classmethod
    def class_name(cls) -> str:
        return "BedrockLLM"
    
    @property
    def metadata(self) -> LLMMetadata:
        context_window, num_output = self._get_model_capabilities()
        return LLMMetadata(
            context_window=context_window,
            num_output=num_output,
            is_chat_model=True,
            model_name=self.model_id,
        )
    
    @llm_completion_callback()
    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        """Complete a prompt"""
        response = self._bedrock.generate(
            prompt=prompt,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
        )
        return CompletionResponse(text=response)
    
    @llm_completion_callback()
    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        """Stream complete a prompt"""
        text = ""
        for chunk in self._bedrock.stream_generate(
            prompt=prompt,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
        ):
            text += chunk
            yield CompletionResponse(text=text, delta=chunk)
    
    @llm_chat_callback()
    def chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponse:
        """Chat with messages"""
        # Convert chat messages to a single prompt
        prompt = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        response = self._bedrock.generate(
            prompt=prompt,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
        )
        return ChatResponse(message=ChatMessage(role="assistant", content=response))
    
    @llm_chat_callback()
    def stream_chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponseGen:
        """Stream chat with messages"""
        prompt = "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
        text = ""
        for chunk in self._bedrock.stream_generate(
            prompt=prompt,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
        ):
            text += chunk
            yield ChatResponse(
                message=ChatMessage(role="assistant", content=text),
                delta=chunk
            )

    # Async methods (required by LlamaIndex but can be simple wrappers)
    async def acomplete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        """Async complete - just wraps sync version"""
        return self.complete(prompt, formatted=formatted, **kwargs)

    async def astream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        """Async stream complete - just wraps sync version"""
        for response in self.stream_complete(prompt, formatted=formatted, **kwargs):
            yield response

    async def achat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponse:
        """Async chat - just wraps sync version"""
        return self.chat(messages, **kwargs)

    async def astream_chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> ChatResponseGen:
        """Async stream chat - just wraps sync version"""
        for response in self.stream_chat(messages, **kwargs):
            yield response
