"""Local Provider для SOP LLM Executor.

Использует llama-cpp-python для inference GGUF моделей на GPU.
"""

from collections.abc import AsyncIterator
from pathlib import Path

try:
    from llama_cpp import Llama, LlamaGrammar
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None  # type: ignore[misc,assignment]
    LlamaGrammar = None  # type: ignore[misc,assignment]

from src.config import settings
from src.engine.gpu_guard import get_gpu_guard
from src.engine.vram_monitor import get_vram_monitor
from src.providers.base import (
    GenerationParams,
    GenerationResult,
    ModelInfo,
    StreamChunk,
)
from src.utils.logging import get_logger

logger = get_logger()


class LocalProvider:
    """Local GGUF model provider через llama-cpp-python.

    Features:
    - GPU inference через CUDA
    - GBNF grammars для structured output
    - Hot path optimization (skip reloading)
    - Exclusive GPU access через GPUGuard
    - VRAM monitoring
    """

    def __init__(
        self,
        model_name: str,
        model_path: str | None = None,
        context_window: int | None = None,
        gpu_layers: int = -1,
    ) -> None:
        """Инициализировать Local Provider.

        Args:
            model_name: Название модели (для registry)
            model_path: Путь к GGUF файлу (если None, ищется в models_dir)
            context_window: Размер контекстного окна (если None, используется default)
            gpu_layers: Количество слоёв на GPU (-1 = все)

        """
        self.model_name = model_name
        self.context_window = context_window or settings.default_context_window
        self.gpu_layers = gpu_layers

        # Определить путь к модели
        if model_path is None:
            # Искать в models_dir
            models_dir = Path(settings.models_dir)
            possible_paths = [
                models_dir / f"{model_name}.gguf",
                models_dir / model_name / f"{model_name}.gguf",
                models_dir / model_name,
            ]

            for path in possible_paths:
                if path.exists() and path.is_file():
                    model_path = str(path)
                    break

            if model_path is None:
                msg = f"Модель '{model_name}' не найдена в {models_dir}"
                raise FileNotFoundError(msg)

        # Проверить существование
        elif not Path(model_path).exists():
            msg = f"Файл модели не найден: {model_path}"
            raise FileNotFoundError(msg)

        self.model_path = model_path

        # Llama instance (загружается lazy)
        self._llama: Llama | None = None
        self._is_loaded = False

        # GPU components
        self._gpu_guard = get_gpu_guard()
        self._vram_monitor = get_vram_monitor()

        logger.info(
            "LocalProvider инициализирован",
            model_name=model_name,
            model_path=model_path,
            context_window=self.context_window,
            gpu_layers=gpu_layers,
        )

    async def _load_model(self) -> None:
        """Загрузить модель в VRAM (если ещё не загружена).

        Hot Path Optimization: пропускает загрузку если модель уже в VRAM.
        """
        if self._is_loaded and self._llama is not None:
            logger.debug("Модель уже загружена (hot path)", model=self.model_name)
            return

        logger.info("Загрузка модели в VRAM", model=self.model_name)

        # Загрузить модель (blocking операция, но быстрая для GGUF)
        self._llama = Llama(
            model_path=self.model_path,
            n_ctx=self.context_window,
            n_gpu_layers=self.gpu_layers,
            verbose=False,
            # CUDA
            n_threads=1,  # GPU inference не требует CPU threads
            use_mlock=True,  # Lock memory для production
            use_mmap=True,  # Memory mapping для быстрой загрузки
        )

        self._is_loaded = True

        vram_usage = self._vram_monitor.get_vram_usage()

        logger.info(
            "Модель загружена в VRAM",
            model=self.model_name,
            vram_used_mb=vram_usage["used_mb"],
            vram_percent=vram_usage["used_percent"],
        )

    async def generate(
        self,
        prompt: str,
        params: GenerationParams,
    ) -> GenerationResult:
        """Сгенерировать текст (non-streaming).

        Args:
            prompt: Промпт для генерации
            params: Параметры генерации

        Returns:
            Результат генерации

        Raises:
            RuntimeError: Ошибка генерации

        """
        # Эксклюзивный доступ к GPU
        async with self._gpu_guard.acquire(task_id=f"generate-{self.model_name}"):
            # Загрузить модель если нужно
            await self._load_model()

            if self._llama is None:
                msg = "Модель не загружена"
                raise RuntimeError(msg)

            # Подготовить параметры
            stop_sequences = params.stop_sequences if params.stop_sequences else None
            grammar = None

            # GBNF grammar для structured output
            if params.grammar:
                grammar = LlamaGrammar.from_string(params.grammar)

            logger.debug(
                "Начало генерации",
                model=self.model_name,
                prompt_length=len(prompt),
                max_tokens=params.max_tokens,
                has_grammar=grammar is not None,
            )

            try:
                # Генерация (blocking, но в thread executor через llama-cpp-python)
                result = self._llama(
                    prompt=prompt,
                    max_tokens=params.max_tokens,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    top_k=params.top_k,
                    frequency_penalty=params.frequency_penalty,
                    presence_penalty=params.presence_penalty,
                    stop=stop_sequences,
                    seed=params.seed,
                    grammar=grammar,
                    # No streaming
                    stream=False,
                )

                # Извлечь результат
                text = result["choices"][0]["text"]
                finish_reason = result["choices"][0]["finish_reason"]

                # Token usage
                usage = {
                    "prompt_tokens": result["usage"]["prompt_tokens"],
                    "completion_tokens": result["usage"]["completion_tokens"],
                    "total_tokens": result["usage"]["total_tokens"],
                }

                logger.info(
                    "Генерация завершена",
                    model=self.model_name,
                    finish_reason=finish_reason,
                    completion_tokens=usage["completion_tokens"],
                )

                return GenerationResult(
                    text=text,
                    finish_reason=finish_reason if finish_reason in ("stop", "length") else "error",
                    usage=usage,
                    model=self.model_name,
                    extra={
                        "model_path": self.model_path,
                        "context_window": self.context_window,
                    },
                )

            except Exception as e:
                logger.exception(
                    "Ошибка генерации",
                    model=self.model_name,
                    error=str(e),
                )
                msg = f"Ошибка генерации: {e}"
                raise RuntimeError(msg) from e

    async def generate_stream(
        self,
        prompt: str,
        params: GenerationParams,
    ) -> AsyncIterator[StreamChunk]:
        """Сгенерировать текст (streaming).

        Args:
            prompt: Промпт для генерации
            params: Параметры генерации

        Yields:
            Stream chunks

        Raises:
            RuntimeError: Ошибка генерации

        """
        # Эксклюзивный доступ к GPU
        async with self._gpu_guard.acquire(task_id=f"stream-{self.model_name}"):
            # Загрузить модель если нужно
            await self._load_model()

            if self._llama is None:
                msg = "Модель не загружена"
                raise RuntimeError(msg)

            # Подготовить параметры
            stop_sequences = params.stop_sequences if params.stop_sequences else None
            grammar = None

            if params.grammar:
                grammar = LlamaGrammar.from_string(params.grammar)

            logger.debug(
                "Начало streaming генерации",
                model=self.model_name,
                prompt_length=len(prompt),
            )

            try:
                # Streaming generation
                stream = self._llama(
                    prompt=prompt,
                    max_tokens=params.max_tokens,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    top_k=params.top_k,
                    frequency_penalty=params.frequency_penalty,
                    presence_penalty=params.presence_penalty,
                    stop=stop_sequences,
                    seed=params.seed,
                    grammar=grammar,
                    stream=True,
                )

                # Yield chunks
                total_tokens = 0

                for chunk_data in stream:
                    choice = chunk_data["choices"][0]
                    text = choice.get("text", "")
                    finish_reason = choice.get("finish_reason")

                    total_tokens += 1

                    # Последний chunk
                    if finish_reason:
                        usage = {
                            "prompt_tokens": chunk_data["usage"]["prompt_tokens"],
                            "completion_tokens": chunk_data["usage"]["completion_tokens"],
                            "total_tokens": chunk_data["usage"]["total_tokens"],
                        }

                        logger.info(
                            "Streaming завершён",
                            model=self.model_name,
                            finish_reason=finish_reason,
                            total_tokens=usage["total_tokens"],
                        )

                        yield StreamChunk(
                            text=text,
                            finish_reason=finish_reason if finish_reason in ("stop", "length") else "error",
                            usage=usage,
                        )

                    else:
                        # Промежуточный chunk
                        yield StreamChunk(text=text)

            except Exception as e:
                logger.exception(
                    "Ошибка streaming генерации",
                    model=self.model_name,
                    error=str(e),
                )
                msg = f"Ошибка streaming: {e}"
                raise RuntimeError(msg) from e

    async def get_model_info(self) -> ModelInfo:
        """Получить метаданные модели.

        Returns:
            Информация о модели

        """
        # VRAM usage (если модель загружена)
        vram_usage = None
        if self._is_loaded:
            vram_data = self._vram_monitor.get_vram_usage()
            vram_usage = {
                "used_mb": vram_data["used_mb"],
                "used_percent": vram_data["used_percent"],
            }

        # Размер файла
        file_size_mb = Path(self.model_path).stat().st_size / (1024**2)

        return ModelInfo(
            name=self.model_name,
            provider="local",
            context_window=self.context_window,
            max_output_tokens=settings.default_max_tokens,
            supports_streaming=True,
            supports_structured_output=True,  # GBNF grammars
            loaded=self._is_loaded,
            extra={
                "model_path": self.model_path,
                "file_size_mb": file_size_mb,
                "gpu_layers": self.gpu_layers,
                "vram_usage": vram_usage,
            },
        )

    async def health_check(self) -> bool:
        """Проверить доступность provider'а.

        Returns:
            True если модель доступна

        """
        try:
            # Проверить существование файла
            if not Path(self.model_path).exists():
                return False

            # Проверить GPU
            gpu_info = self._vram_monitor.get_gpu_info()

            return gpu_info is not None

        except Exception as e:
            logger.exception("Health check failed", model=self.model_name, error=str(e))
            return False

    async def cleanup(self) -> None:
        """Очистить ресурсы (unload model).

        Вызывается при shutdown приложения.
        """
        if self._llama is not None:
            logger.info("Unload модели", model=self.model_name)

            # llama-cpp-python автоматически очищает ресурсы в деструкторе
            del self._llama
            self._llama = None
            self._is_loaded = False

            logger.info("Модель unloaded", model=self.model_name)


async def create_local_provider(
    model_name: str,
    model_path: str | None = None,
    context_window: int | None = None,
    gpu_layers: int = -1,
) -> LocalProvider:
    """Создать и зарегистрировать Local Provider.

    Args:
        model_name: Название модели
        model_path: Путь к GGUF файлу (опционально)
        context_window: Размер контекстного окна (опционально)
        gpu_layers: Количество слоёв на GPU (-1 = все)

    Returns:
        LocalProvider instance

    """
    provider = LocalProvider(
        model_name=model_name,
        model_path=model_path,
        context_window=context_window,
        gpu_layers=gpu_layers,
    )

    # Health check
    if not await provider.health_check():
        msg = f"Health check failed для модели {model_name}"
        raise RuntimeError(msg)

    logger.info(
        "LocalProvider создан",
        model_name=model_name,
        model_path=provider.model_path,
    )

    return provider
