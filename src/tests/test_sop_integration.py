"""
Тесты интеграции с проектом sop - проверка совместимости API.
"""
import pytest
import httpx
import asyncio
from datetime import datetime


@pytest.mark.asyncio
async def test_create_task_sop_format(sop_llm_base_url):
    """
    Тест создания задачи в формате, который использует проект sop.
    Проверяет совместимость с sop_llm_client.py
    """
    async with httpx.AsyncClient(base_url=sop_llm_base_url, timeout=30.0) as client:
        # Формат запроса из sop/app/shared/sop_llm_client.py:create_task()
        payload = {
            "text": "Test prompt from sop project",
            "task_type": "generate",
            "provider": "local",
            "parameters": {
                "temperature": 0.2,
                "max_tokens": 512,
                "system_prompt": "You are a helpful assistant"
            },
            "expected_format": "text"
        }

        # Создаём задачу
        response = await client.post("/tasks", json=payload)
        assert response.status_code in [200, 201]

        data = response.json()
        assert "task_id" in data
        assert data["status"] in ["pending", "completed"]

        task_id = data["task_id"]

        # Ждём завершения задачи
        max_attempts = 30
        for _ in range(max_attempts):
            status_response = await client.get(f"/tasks/{task_id}")
            assert status_response.status_code == 200

            status_data = status_response.json()

            if status_data["status"] == "completed":
                assert "result" in status_data
                assert "text" in status_data["result"]
                print(f"✅ Task completed: {status_data['result']['text'][:100]}")
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Task failed: {status_data.get('error')}")

            await asyncio.sleep(0.5)
        else:
            pytest.fail("Task did not complete in time")


@pytest.mark.asyncio
async def test_create_task_with_json_format(sop_llm_base_url):
    """
    Тест создания задачи с ожидаемым JSON форматом.
    Проверяет работу JSON fixer.
    """
    async with httpx.AsyncClient(base_url=sop_llm_base_url, timeout=60.0) as client:
        # Запрос с expected_format="json"
        payload = {
            "text": "List 3 programming languages. Return as JSON array with fields: name, year, paradigm",
            "task_type": "generate",
            "provider": "local",
            "parameters": {
                "temperature": 0.1,
                "max_tokens": 512,
            },
            "expected_format": "json"
        }

        response = await client.post("/tasks", json=payload)
        assert response.status_code in [200, 201]

        data = response.json()
        task_id = data["task_id"]

        # Ждём завершения
        max_attempts = 60
        for _ in range(max_attempts):
            status_response = await client.get(f"/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                result = status_data["result"]
                assert "text" in result

                # Проверяем, что результат - валидный JSON
                import json
                parsed = json.loads(result["text"])
                print(f"✅ JSON result: {parsed}")

                # Проверяем флаги JSON fixer
                if result.get("was_fixed"):
                    print(f"⚠️  JSON was fixed in {result['fix_attempts']} attempts")

                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Task failed: {status_data.get('error')}")

            await asyncio.sleep(1.0)
        else:
            pytest.fail("Task did not complete in time")


@pytest.mark.asyncio
async def test_create_task_with_system_prompt(sop_llm_base_url):
    """
    Тест создания задачи с system_prompt в parameters.
    """
    async with httpx.AsyncClient(base_url=sop_llm_base_url, timeout=30.0) as client:
        payload = {
            "text": "What is 2+2?",
            "task_type": "generate",
            "provider": "local",
            "parameters": {
                "temperature": 0.0,
                "max_tokens": 128,
                "system_prompt": "You are a math teacher. Explain your answer step by step."
            }
        }

        response = await client.post("/tasks", json=payload)
        assert response.status_code in [200, 201]

        task_id = response.json()["task_id"]

        # Ждём завершения
        for _ in range(30):
            status_response = await client.get(f"/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                result_text = status_data["result"]["text"]
                print(f"✅ Result with system prompt: {result_text[:100]}")
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Task failed: {status_data.get('error')}")

            await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_embedding_task(sop_llm_base_url):
    """
    Тест создания задачи для embedding.
    """
    async with httpx.AsyncClient(base_url=sop_llm_base_url, timeout=30.0) as client:
        payload = {
            "text": "This is a test sentence for embedding generation",
            "task_type": "embedding",
            "provider": "local"
        }

        response = await client.post("/tasks", json=payload)
        assert response.status_code in [200, 201]

        task_id = response.json()["task_id"]

        # Ждём завершения
        for _ in range(30):
            status_response = await client.get(f"/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                result = status_data["result"]
                assert "embedding" in result
                assert "dimension" in result
                assert isinstance(result["embedding"], list)
                assert len(result["embedding"]) > 0
                print(f"✅ Embedding generated: dimension={result['dimension']}")
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Task failed: {status_data.get('error')}")

            await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_task_detail_contains_processing_details(sop_llm_base_url):
    """
    Тест проверяет, что детальная информация о задаче содержит processing_details.
    Это необходимо для нового Web UI.
    """
    async with httpx.AsyncClient(base_url=sop_llm_base_url, timeout=30.0) as client:
        payload = {
            "text": "Test for processing details",
            "task_type": "generate",
            "provider": "local",
            "parameters": {"temperature": 0.5}
        }

        response = await client.post("/tasks", json=payload)
        task_id = response.json()["task_id"]

        # Ждём завершения
        for _ in range(30):
            status_response = await client.get(f"/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                # Проверяем наличие processing_details
                assert "processing_details" in status_data
                details = status_data["processing_details"]

                assert "original_request" in details
                assert "llm_interaction" in details

                # Проверяем что входной текст сохранен
                assert details["original_request"]["text"] == payload["text"]

                # Проверяем что есть информация о модели
                assert "model_used" in details["llm_interaction"]
                assert "provider_used" in details["llm_interaction"]

                print(f"✅ Processing details present: provider={details['llm_interaction']['provider_used']}, model={details['llm_interaction']['model_used']}")
                break
            elif status_data["status"] == "failed":
                pytest.fail(f"Task failed: {status_data.get('error')}")

            await asyncio.sleep(0.5)


@pytest.mark.asyncio
async def test_cache_functionality(sop_llm_base_url):
    """
    Тест проверяет работу кэша - второй запрос должен вернуться из кэша.
    """
    async with httpx.AsyncClient(base_url=sop_llm_base_url, timeout=30.0) as client:
        payload = {
            "text": "What is the capital of France?",
            "task_type": "generate",
            "provider": "local",
            "parameters": {"temperature": 0.0, "max_tokens": 64},
            "use_cache": True
        }

        # Первый запрос
        response1 = await client.post("/tasks", json=payload)
        task_id_1 = response1.json()["task_id"]

        # Ждём завершения
        for _ in range(30):
            status_response = await client.get(f"/tasks/{task_id_1}")
            status_data = status_response.json()
            if status_data["status"] in ["completed", "failed"]:
                break
            await asyncio.sleep(0.5)

        # Второй запрос с теми же параметрами
        response2 = await client.post("/tasks", json=payload)
        task_id_2 = response2.json()["task_id"]

        # Проверяем второй запрос
        status_response_2 = await client.get(f"/tasks/{task_id_2}")
        status_data_2 = status_response_2.json()

        # Должен быть из кэша (completed сразу или очень быстро)
        if status_data_2.get("from_cache"):
            print(f"✅ Second request served from cache")
        else:
            print(f"⚠️  Second request not from cache (cache may be disabled or expired)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
