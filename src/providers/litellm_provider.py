"""LiteLLM Provider - Unified interface for 100+ cloud LLM providers.

Replaces all custom cloud provider implementations (Anthropic, OpenAI, etc.)
with a single provider backed by LiteLLM.

Supports: Anthropic, OpenAI, Google Gemini, Mistral, Cohere, Azure, and many more.
"""

from collections.abc import AsyncIterator
from typing import Any

import litellm
from litellm import ModelResponse, acompletion
from loguru import logger

from src.providers.base import ChatMessage, GenerationParams, GenerationResult, ModelInfo, StreamChunk


class LiteLLMProvider:
    """Unified cloud LLM provider using LiteLLM.

    Automatically handles parameter translation, retries, and error mapping
    for all supported providers.

    Examples:
        # Anthropic Claude
        provider = LiteLLMProvider(model_name="claude-3-opus-20240229")

        # OpenAI GPT
        provider = LiteLLMProvider(model_name="gpt-4-turbo")

        # Google Gemini
        provider = LiteLLMProvider(model_name="gemini/gemini-pro")

        # Mistral
        provider = LiteLLMProvider(model_name="mistral/mistral-large-latest")
    """

    def __init__(
        self,
        model_name: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = 600,
        max_retries: int = 3,
        drop_params: bool = True,
        **extra_params: Any,
    ) -> None:
        """Initialize LiteLLM provider.

        Args:
            model_name: Model identifier (e.g., "claude-3-opus-20240229", "gpt-4")
            api_key: API key for the provider (optional if set via env var)
            base_url: Custom base URL for API (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries on failure
            drop_params: Automatically drop unsupported parameters
            **extra_params: Additional provider-specific parameters
        """
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.extra_params = extra_params

        # Configure LiteLLM
        litellm.drop_params = drop_params
        litellm.num_retries = max_retries

        logger.info(
            f"LiteLLMProvider initialized: model={model_name}, "
            f"timeout={timeout}s, retries={max_retries}"
        )

    def _prepare_messages(
        self,
        prompt: str | None = None,
        messages: list[ChatMessage] | None = None,
    ) -> list[dict[str, str]]:
        """Convert prompt or messages to LiteLLM messages format.

        Args:
            prompt: Simple text prompt
            messages: Chat messages in OpenAI format

        Returns:
            List of message dicts for LiteLLM

        Raises:
            ValueError: If neither prompt nor messages provided
        """
        if messages:
            return [{"role": msg.role, "content": msg.content} for msg in messages]

        if prompt:
            return [{"role": "user", "content": prompt}]

        raise ValueError("Either 'prompt' or 'messages' must be provided")

    def _prepare_params(self, params: GenerationParams | None) -> dict[str, Any]:
        """Convert GenerationParams to LiteLLM parameters.

        Args:
            params: Generation parameters

        Returns:
            Dictionary of parameters for LiteLLM
        """
        if params is None:
            params = GenerationParams()

        litellm_params: dict[str, Any] = {
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "top_p": params.top_p,
        }

        # Add optional parameters
        if params.frequency_penalty != 0.0:
            litellm_params["frequency_penalty"] = params.frequency_penalty

        if params.presence_penalty != 0.0:
            litellm_params["presence_penalty"] = params.presence_penalty

        if params.stop_sequences:
            litellm_params["stop"] = params.stop_sequences

        if params.seed is not None:
            litellm_params["seed"] = params.seed

        # Response format for structured output
        if params.response_format:
            litellm_params["response_format"] = params.response_format

        # Top-K (not all providers support this)
        if params.top_k > 0 and params.top_k != 40:
            litellm_params["top_k"] = params.top_k

        # Merge extra provider-specific params
        if params.extra:
            litellm_params.update(params.extra)

        return litellm_params

    def _extract_usage(self, response: ModelResponse) -> dict[str, int]:
        """Extract token usage from LiteLLM response.

        Args:
            response: LiteLLM response object

        Returns:
            Usage dict with prompt_tokens, completion_tokens, total_tokens
        """
        usage = getattr(response, "usage", None)

        if usage:
            return {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
            }

        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def _map_finish_reason(self, reason: str | None) -> str:
        """Map LiteLLM finish_reason to our standard format.

        Args:
            reason: LiteLLM finish reason

        Returns:
            Standardized finish reason
        """
        if reason == "stop":
            return "stop"
        if reason in ("length", "max_tokens"):
            return "length"
        return "error"

    async def generate(
        self,
        prompt: str | None = None,
        messages: list[ChatMessage] | None = None,
        params: GenerationParams | None = None,
    ) -> GenerationResult:
        """Generate text using LiteLLM (non-streaming).

        Args:
            prompt: Simple text prompt
            messages: Chat messages in OpenAI format
            params: Generation parameters

        Returns:
            Generation result with text and metadata

        Raises:
            RuntimeError: If generation fails
            ValueError: If neither prompt nor messages provided
        """
        try:
            messages_list = self._prepare_messages(prompt, messages)
            litellm_params = self._prepare_params(params)

            logger.debug(f"LiteLLM generate: model={self.model_name}, messages={len(messages_list)}")

            response: ModelResponse = await acompletion(
                model=self.model_name,
                messages=messages_list,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                stream=False,
                **litellm_params,
                **self.extra_params,
            )

            # Extract response content
            choice = response.choices[0]
            text = choice.message.content or ""
            finish_reason = self._map_finish_reason(choice.finish_reason)
            usage = self._extract_usage(response)

            logger.debug(
                f"LiteLLM generation complete: tokens={usage['total_tokens']}, "
                f"finish={finish_reason}"
            )

            return GenerationResult(
                text=text,
                finish_reason=finish_reason,
                usage=usage,
                model=response.model or self.model_name,
                extra={"provider": getattr(response, "_hidden_params", {}).get("custom_llm_provider", "unknown")},
            )

        except Exception as e:
            logger.error(f"LiteLLM generation failed: {e}")
            raise RuntimeError(f"LiteLLM generation failed: {e}") from e

    async def generate_stream(
        self,
        prompt: str | None = None,
        messages: list[ChatMessage] | None = None,
        params: GenerationParams | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Generate text using LiteLLM (streaming).

        Args:
            prompt: Simple text prompt
            messages: Chat messages in OpenAI format
            params: Generation parameters

        Yields:
            Stream chunks with incremental text

        Raises:
            RuntimeError: If generation fails
            ValueError: If neither prompt nor messages provided
        """
        try:
            messages_list = self._prepare_messages(prompt, messages)
            litellm_params = self._prepare_params(params)

            logger.debug(f"LiteLLM stream: model={self.model_name}, messages={len(messages_list)}")

            response = await acompletion(
                model=self.model_name,
                messages=messages_list,
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                stream=True,
                **litellm_params,
                **self.extra_params,
            )

            accumulated_tokens = 0

            async for chunk in response:
                delta = chunk.choices[0].delta

                # Extract text from delta
                text = getattr(delta, "content", "") or ""

                # Check if this is the final chunk
                finish_reason = chunk.choices[0].finish_reason
                is_final = finish_reason is not None

                if text:
                    accumulated_tokens += len(text.split())

                yield StreamChunk(
                    text=text,
                    finish_reason=self._map_finish_reason(finish_reason) if is_final else None,
                    usage=(
                        {
                            "prompt_tokens": 0,
                            "completion_tokens": accumulated_tokens,
                            "total_tokens": accumulated_tokens,
                        }
                        if is_final
                        else None
                    ),
                )

            logger.debug(f"LiteLLM stream complete: tokens≈{accumulated_tokens}")

        except Exception as e:
            logger.error(f"LiteLLM stream failed: {e}")
            raise RuntimeError(f"LiteLLM stream failed: {e}") from e

    async def get_model_info(self) -> ModelInfo:
        """Get model metadata.

        Returns:
            Model information with capabilities and limits

        Note:
            LiteLLM doesn't provide a direct API for model metadata,
            so we return reasonable defaults based on model name.
        """
        # Try to infer context window from model name
        context_window = 4096  # Default
        max_output = 2048  # Default

        model_lower = self.model_name.lower()

        if "claude-3" in model_lower:
            context_window = 200000
            max_output = 4096
        elif "claude-2" in model_lower:
            context_window = 100000
            max_output = 4096
        elif "gpt-4" in model_lower:
            if "turbo" in model_lower or "1106" in model_lower or "0125" in model_lower:
                context_window = 128000
                max_output = 4096
            else:
                context_window = 8192
                max_output = 4096
        elif "gpt-3.5" in model_lower:
            if "16k" in model_lower:
                context_window = 16384
            else:
                context_window = 4096
            max_output = 4096
        elif "gemini" in model_lower:
            context_window = 32000
            max_output = 8192
        elif "mistral" in model_lower:
            context_window = 32000
            max_output = 8192

        return ModelInfo(
            name=self.model_name,
            provider="litellm",
            context_window=context_window,
            max_output_tokens=max_output,
            supports_streaming=True,
            supports_structured_output="gpt" in model_lower or "gemini" in model_lower,
            loaded=True,  # Cloud models are always "loaded"
            extra={
                "base_url": self.base_url,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            },
        )

    async def health_check(self) -> bool:
        """Check if the model/provider is accessible.

        Returns:
            True if provider is healthy

        Note:
            Makes a minimal test request to verify connectivity.
        """
        try:
            await self.generate(
                messages=[ChatMessage(role="user", content="Hi")],
                params=GenerationParams(max_tokens=1, temperature=0.0),
            )
            return True
        except Exception as e:
            logger.warning(f"LiteLLM health check failed for {self.model_name}: {e}")
            return False

    async def cleanup(self) -> None:
        """Cleanup resources.

        Note:
            LiteLLM is stateless, so no cleanup needed.
        """
        logger.debug(f"LiteLLM provider cleanup: {self.model_name}")
