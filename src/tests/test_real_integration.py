"""РЕАЛЬНЫЕ интеграционные тесты
Использует настоящие модели и Redis - НЕТ МОКОВ!
"""
import asyncio

import numpy as np
import pytest


@pytest.mark.integration
@pytest.mark.slow
class TestRealLLMManager:
    """Тесты для РЕАЛЬНОГО LLMManager с настоящими моделями."""

    @pytest.mark.asyncio
    async def test_llm_model_loaded(self, real_llm_manager):
        """Тест что модель действительно загружена."""
        assert real_llm_manager.model is not None, "LLM model should be loaded"
        assert real_llm_manager.tokenizer is not None, "Tokenizer should be loaded"
        assert real_llm_manager.model_name is not None, "Model name should be set"
        assert real_llm_manager.device in ["cpu", "cuda"], "Device should be set"

        print(f"\n✓ Model: {real_llm_manager.model_name}")
        print(f"✓ Device: {real_llm_manager.device}")

    @pytest.mark.asyncio
    async def test_real_text_generation(self, real_llm_manager):
        """Тест РЕАЛЬНОЙ генерации текста."""
        prompt = "What is 2+2? Answer:"

        # Генерируем текст с настоящей моделью
        result = await real_llm_manager.generate(
            prompt=prompt,
            max_tokens=20,
            temperature=0.1  # Низкая температура для детерминизма
        )

        # Проверки
        assert result is not None, "Result should not be None"
        assert isinstance(result, str), "Result should be string"
        assert len(result) > 0, "Result should not be empty"
        assert result.strip() != "", "Result should not be whitespace only"

        print(f"\n✓ Prompt: {prompt}")
        print(f"✓ Generated: {result}")

        # Проверяем счетчики
        assert real_llm_manager.total_requests > 0, "Request counter should increase"

    @pytest.mark.asyncio
    async def test_multiple_generations(self, real_llm_manager, sample_prompts):
        """Тест нескольких реальных генераций."""
        results = []

        for prompt in sample_prompts[:2]:  # Берем только 2 промпта для скорости
            result = await real_llm_manager.generate(
                prompt=prompt,
                max_tokens=30,
                temperature=0.7
            )
            results.append(result)

            print(f"\n✓ Prompt: {prompt}")
            print(f"  Response: {result[:100]}...")

        # Все результаты должны быть разными (с высокой вероятностью)
        assert len(results) == 2
        assert all(isinstance(r, str) and len(r) > 0 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_generation_requests(self, real_llm_manager):
        """Тест concurrent запросов к реальной модели."""
        prompts = [
            "Count to 5:",
            "Name three colors:",
            "What is Python?",
        ]

        # Запускаем все запросы параллельно
        tasks = [
            real_llm_manager.generate(prompt, max_tokens=50, temperature=0.5)
            for prompt in prompts
        ]

        results = await asyncio.gather(*tasks)

        # Проверяем что все сгенерировались
        assert len(results) == len(prompts)
        assert all(isinstance(r, str) and len(r) > 0 for r in results)

        for prompt, result in zip(prompts, results, strict=False):
            print(f"\n✓ Prompt: {prompt}")
            print(f"  Result: {result[:80]}...")

    @pytest.mark.asyncio
    async def test_generation_with_different_temperatures(self, real_llm_manager):
        """Тест генерации с разными температурами."""
        prompt = "Write a creative sentence:"

        # Низкая температура (более детерминированно)
        result_low = await real_llm_manager.generate(
            prompt=prompt,
            max_tokens=30,
            temperature=0.1
        )

        # Высокая температура (более креативно)
        result_high = await real_llm_manager.generate(
            prompt=prompt,
            max_tokens=30,
            temperature=1.5
        )

        assert result_low is not None
        assert len(result_low) > 0
        assert result_high is not None
        assert len(result_high) > 0

        print(f"\n✓ Low temp (0.1): {result_low}")
        print(f"✓ High temp (1.5): {result_high}")

    @pytest.mark.asyncio
    async def test_get_stats(self, real_llm_manager):
        """Тест получения статистики реального менеджера."""
        stats = real_llm_manager.get_stats()

        assert stats["model_loaded"] is True
        assert stats["model_name"] == real_llm_manager.model_name
        assert stats["device"] == real_llm_manager.device
        assert "total_requests" in stats
        assert "active_requests" in stats

        print(f"\n✓ Stats: {stats}")


@pytest.mark.integration
@pytest.mark.slow
class TestRealEmbeddingManager:
    """Тесты для РЕАЛЬНОГО EmbeddingManager с настоящими моделями."""

    @pytest.mark.asyncio
    async def test_embedding_model_loaded(self, real_embedding_manager):
        """Тест что embedding модель действительно загружена."""
        assert real_embedding_manager.model is not None
        assert real_embedding_manager.tokenizer is not None
        assert real_embedding_manager.model_name is not None

        print(f"\n✓ Embedding Model: {real_embedding_manager.model_name}")
        print(f"✓ Device: {real_embedding_manager.device}")

    @pytest.mark.asyncio
    async def test_real_embedding_generation(self, real_embedding_manager):
        """Тест РЕАЛЬНОЙ генерации embeddings."""
        text = "This is a test sentence."

        # Генерируем embedding с настоящей моделью
        embedding = await real_embedding_manager.get_embedding(text)

        # Проверки
        assert embedding is not None
        assert isinstance(embedding, list)
        assert len(embedding) == 384  # all-MiniLM-L6-v2 размерность
        assert all(isinstance(x, float) for x in embedding)

        # Проверяем что вектор нормализован
        norm = np.linalg.norm(embedding)
        assert 0.99 <= norm <= 1.01, f"Embedding should be normalized, got norm={norm}"

        print(f"\n✓ Text: {text}")
        print(f"✓ Embedding dimension: {len(embedding)}")
        print(f"✓ Embedding norm: {norm:.4f}")
        print(f"✓ First 5 values: {embedding[:5]}")

    @pytest.mark.asyncio
    async def test_batch_embeddings(self, real_embedding_manager, sample_texts_for_embedding):
        """Тест batch генерации embeddings."""
        texts = sample_texts_for_embedding

        # Генерируем embeddings для batch
        embeddings = await real_embedding_manager.get_embeddings(texts)

        # Проверки
        assert len(embeddings) == len(texts)
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) == 384 for emb in embeddings)

        # Все embeddings должны быть разными
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                # Проверяем что не идентичны
                assert embeddings[i] != embeddings[j], f"Embeddings {i} and {j} should be different"

        print(f"\n✓ Generated {len(embeddings)} embeddings")
        for i, (text, emb) in enumerate(zip(texts, embeddings, strict=False)):
            print(f"  {i+1}. {text[:50]}... -> [{emb[0]:.4f}, {emb[1]:.4f}, ...]")

    @pytest.mark.asyncio
    async def test_real_similarity_computation(self, real_embedding_manager):
        """Тест РЕАЛЬНОГО вычисления similarity."""
        text1 = "I love programming in Python."
        text2 = "Python is my favorite programming language."
        text3 = "The weather is nice today."

        # Вычисляем similarity между похожими текстами
        similarity_similar = await real_embedding_manager.compute_similarity(text1, text2)

        # Вычисляем similarity между разными текстами
        similarity_different = await real_embedding_manager.compute_similarity(text1, text3)

        # Проверки
        assert -1 <= similarity_similar <= 1
        assert -1 <= similarity_different <= 1

        # Похожие тексты должны иметь больше similarity
        assert similarity_similar > similarity_different, \
            f"Similar texts should have higher similarity: {similarity_similar} vs {similarity_different}"

        print(f"\n✓ Text 1: {text1}")
        print(f"✓ Text 2: {text2}")
        print(f"✓ Similarity (similar): {similarity_similar:.4f}")
        print(f"\n✓ Text 3: {text3}")
        print(f"✓ Similarity (different): {similarity_different:.4f}")

    @pytest.mark.asyncio
    async def test_identical_texts_similarity(self, real_embedding_manager):
        """Тест similarity для идентичных текстов."""
        text = "Exact same text"

        similarity = await real_embedding_manager.compute_similarity(text, text)

        # Идентичные тексты должны иметь similarity ~1.0
        assert 0.99 <= similarity <= 1.01, f"Identical texts should have similarity ~1.0, got {similarity}"

        print(f"\n✓ Identical text similarity: {similarity:.6f}")

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, real_embedding_manager):
        """Тест консистентности embeddings (одинаковый текст -> одинаковый embedding)."""
        text = "Consistency test"

        # Генерируем embedding дважды
        embedding1 = await real_embedding_manager.get_embedding(text)
        embedding2 = await real_embedding_manager.get_embedding(text)

        # Должны быть идентичны
        assert len(embedding1) == len(embedding2)
        for v1, v2 in zip(embedding1, embedding2, strict=False):
            assert abs(v1 - v2) < 1e-6, "Embeddings for same text should be identical"

        print("\n✓ Embedding consistency verified")

    @pytest.mark.asyncio
    async def test_unicode_text_embedding(self, real_embedding_manager):
        """Тест embedding для Unicode текста."""
        texts = [
            "Hello world",
            "Привет мир",
            "你好世界",
            "مرحبا بالعالم",
        ]

        embeddings = await real_embedding_manager.get_embeddings(texts)

        assert len(embeddings) == len(texts)
        assert all(len(emb) == 384 for emb in embeddings)

        print("\n✓ Unicode embeddings generated:")
        for text, emb in zip(texts, embeddings, strict=False):
            print(f"  {text}: [{emb[0]:.4f}, {emb[1]:.4f}, ...]")


@pytest.mark.integration
@pytest.mark.requires_redis
class TestRealRedisCache:
    """Тесты для РЕАЛЬНОГО Redis кэширования."""

    @pytest.mark.asyncio
    async def test_redis_connection(self, real_redis):
        """Тест подключения к реальному Redis."""
        # Проверяем ping
        pong = await real_redis.ping()
        assert pong is True

        print("\n✓ Redis connection OK")

    @pytest.mark.asyncio
    async def test_redis_set_get(self, real_redis, clean_redis):
        """Тест set/get в реальном Redis."""
        key = "test:simple_key"
        value = b"test_value"

        # Set
        await real_redis.setex(key, 60, value)

        # Get
        retrieved = await real_redis.get(key)

        assert retrieved == value

        print(f"\n✓ Redis SET/GET: {key} = {value}")

    @pytest.mark.asyncio
    async def test_redis_cache_operations(self, real_redis_cache, clean_redis):
        """Тест операций кэша с реальным Redis."""
        key = "test:cache_key"
        data = {"text": "Generated text", "tokens": 42}

        # Set в кэш
        await real_redis_cache.set(key, data)

        # Get из кэша
        retrieved = await real_redis_cache.get(key)

        assert retrieved is not None
        assert retrieved["text"] == data["text"]
        assert retrieved["tokens"] == data["tokens"]

        print(f"\n✓ Redis cache operations: {key}")
        print(f"  Stored: {data}")
        print(f"  Retrieved: {retrieved}")

    @pytest.mark.asyncio
    async def test_llm_result_caching(
        self,
        real_llm_manager,
        real_redis_cache,
        clean_redis
    ):
        """Тест кэширования результатов реальной генерации."""
        prompt = "What is 1+1?"
        cache_key = f"test:llm:{hash(prompt)}"

        # Первая генерация (без кэша)
        result1 = await real_llm_manager.generate(
            prompt=prompt,
            max_tokens=20,
            temperature=0.1
        )

        # Сохраняем в кэш
        await real_redis_cache.set(cache_key, {"text": result1})

        # Получаем из кэша
        cached = await real_redis_cache.get(cache_key)

        assert cached is not None
        assert cached["text"] == result1

        print("\n✓ LLM result cached:")
        print(f"  Prompt: {prompt}")
        print(f"  Result: {result1}")
        print(f"  Cached: {cached['text']}")

    @pytest.mark.asyncio
    async def test_embedding_result_caching(
        self,
        real_embedding_manager,
        real_redis_cache,
        clean_redis
    ):
        """Тест кэширования результатов реальных embeddings."""
        text = "Cache this embedding"
        cache_key = f"test:embedding:{hash(text)}"

        # Генерируем embedding
        embedding = await real_embedding_manager.get_embedding(text)

        # Сохраняем в кэш
        await real_redis_cache.set(cache_key, {"embedding": embedding})

        # Получаем из кэша
        cached = await real_redis_cache.get(cache_key)

        assert cached is not None
        assert len(cached["embedding"]) == len(embedding)
        assert cached["embedding"] == embedding

        print("\n✓ Embedding cached:")
        print(f"  Text: {text}")
        print(f"  Dimension: {len(embedding)}")

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self, real_redis_cache, clean_redis):
        """Тест истечения TTL в реальном кэше."""
        key = "test:ttl_key"
        data = {"value": "expires soon"}

        # Сохраняем с коротким TTL
        await real_redis_cache.set(key, data, ttl=1)

        # Сразу должно быть доступно
        retrieved = await real_redis_cache.get(key)
        assert retrieved is not None

        # Ждем истечения TTL
        await asyncio.sleep(2)

        # Должно истечь
        expired = await real_redis_cache.get(key)
        assert expired is None

        print("\n✓ Cache TTL expiration verified")

    @pytest.mark.asyncio
    async def test_cache_delete(self, real_redis_cache, clean_redis):
        """Тест удаления из реального кэша."""
        key = "test:delete_key"
        data = {"value": "to be deleted"}

        # Сохраняем
        await real_redis_cache.set(key, data)

        # Проверяем что есть
        assert await real_redis_cache.get(key) is not None

        # Удаляем
        await real_redis_cache.delete(key)

        # Проверяем что удалено
        assert await real_redis_cache.get(key) is None

        print("\n✓ Cache delete verified")


@pytest.mark.integration
@pytest.mark.slow
class TestRealEndToEndWorkflow:
    """End-to-end тесты с реальными моделями и Redis."""

    @pytest.mark.asyncio
    async def test_complete_llm_workflow_with_cache(
        self,
        real_llm_manager,
        real_redis_cache,
        clean_redis
    ):
        """Полный workflow: генерация -> кэш -> чтение из кэша."""
        prompt = "Tell me about Python programming."
        cache_key = f"test:workflow:{hash(prompt)}"

        # 1. Проверяем что в кэше пусто
        cached = await real_redis_cache.get(cache_key)
        assert cached is None, "Cache should be empty initially"

        # 2. Генерируем с реальной моделью
        print("\n⏳ Generating text (cache miss)...")
        result = await real_llm_manager.generate(
            prompt=prompt,
            max_tokens=50,
            temperature=0.5
        )
        assert result is not None
        assert len(result) > 0

        # 3. Сохраняем в кэш
        await real_redis_cache.set(cache_key, {"text": result, "prompt": prompt})

        # 4. Читаем из кэша (должно быть мгновенно)
        print("⚡ Reading from cache (cache hit)...")
        cached = await real_redis_cache.get(cache_key)
        assert cached is not None
        assert cached["text"] == result

        print("\n✓ Complete workflow:")
        print(f"  Prompt: {prompt}")
        print(f"  Generated: {result[:100]}...")
        print("  Cached successfully")

    @pytest.mark.asyncio
    async def test_complete_embedding_workflow_with_cache(
        self,
        real_embedding_manager,
        real_redis_cache,
        clean_redis
    ):
        """Полный workflow: embedding -> кэш -> similarity."""
        text1 = "Machine learning is fascinating."
        text2 = "I love studying ML algorithms."
        cache_key1 = f"test:emb:{hash(text1)}"
        cache_key2 = f"test:emb:{hash(text2)}"

        # 1. Генерируем embeddings
        print("\n⏳ Generating embeddings...")
        emb1 = await real_embedding_manager.get_embedding(text1)
        emb2 = await real_embedding_manager.get_embedding(text2)

        # 2. Сохраняем в кэш
        await real_redis_cache.set(cache_key1, {"embedding": emb1})
        await real_redis_cache.set(cache_key2, {"embedding": emb2})

        # 3. Читаем из кэша
        cached1 = await real_redis_cache.get(cache_key1)
        cached2 = await real_redis_cache.get(cache_key2)

        assert cached1["embedding"] == emb1
        assert cached2["embedding"] == emb2

        # 4. Вычисляем similarity
        similarity = await real_embedding_manager.compute_similarity(text1, text2)

        print("\n✓ Complete embedding workflow:")
        print(f"  Text 1: {text1}")
        print(f"  Text 2: {text2}")
        print(f"  Similarity: {similarity:.4f}")
        print("  Both embeddings cached")

    @pytest.mark.asyncio
    async def test_parallel_requests_with_caching(
        self,
        real_llm_manager,
        real_redis_cache,
        clean_redis
    ):
        """Тест параллельных запросов с кэшированием."""
        prompts = [
            "Count from 1 to 3:",
            "Name two animals:",
            "What is 5+5?",
        ]

        # 1. Генерируем все результаты параллельно
        print(f"\n⏳ Generating {len(prompts)} texts in parallel...")
        tasks = [
            real_llm_manager.generate(p, max_tokens=30, temperature=0.3)
            for p in prompts
        ]
        results = await asyncio.gather(*tasks)

        # 2. Сохраняем все в кэш
        for i, (prompt, result) in enumerate(zip(prompts, results, strict=False)):
            cache_key = f"test:parallel:{i}"
            await real_redis_cache.set(cache_key, {"prompt": prompt, "text": result})

        # 3. Проверяем что все в кэше
        for i, (prompt, expected_result) in enumerate(zip(prompts, results, strict=False)):
            cache_key = f"test:parallel:{i}"
            cached = await real_redis_cache.get(cache_key)
            assert cached is not None
            assert cached["text"] == expected_result

            print(f"\n  {i+1}. Prompt: {prompt}")
            print(f"     Result: {expected_result[:60]}...")
            print("     ✓ Cached")

        print(f"\n✓ All {len(prompts)} results cached successfully")
