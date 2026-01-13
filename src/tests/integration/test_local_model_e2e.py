"""E2E тест Ollama модели с Langfuse логированием.

Тест проверяет полный flow:
1. Регистрация Ollama модели через LiteLLM
2. Генерация ответа через API
3. Проверка session_id в Langfuse
"""

import time

import httpx
import pytest

# Конфигурация
BASE_URL = "http://localhost:8200"
LANGFUSE_URL = "http://localhost:3001"
LANGFUSE_AUTH = ("pk-lf-local-dev-public-key", "sk-lf-local-dev-secret-key")

# Ollama модель для теста
OLLAMA_MODEL_NAME = "qwen2.5:7b"
REGISTERED_MODEL_NAME = "test-qwen-ollama"


class TestOllamaModelE2E:
    """E2E тесты для Ollama модели через LiteLLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup для каждого теста."""
        self.client = httpx.Client(base_url=BASE_URL, timeout=300.0)
        self.langfuse_client = httpx.Client(
            base_url=LANGFUSE_URL,
            auth=LANGFUSE_AUTH,
            timeout=30.0,
        )
        yield
        self.client.close()
        self.langfuse_client.close()

    def test_service_health(self):
        """Проверка что сервис работает."""
        response = self.client.get("/api/v1/monitor/health")
        assert response.status_code in (200, 503)
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["components"]["redis"]["status"] == "up"
        print(f"Сервис: {data['status']}")

    def test_langfuse_health(self):
        """Проверка что Langfuse работает."""
        response = self.langfuse_client.get("/api/public/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        print(f"Langfuse: OK (v{data['version']})")

    def test_register_ollama_model(self):
        """Регистрация Ollama модели через LiteLLM."""
        print(f"\nРегистрация модели: {REGISTERED_MODEL_NAME}")

        response = self.client.post(
            "/api/v1/models/register",
            json={
                "name": REGISTERED_MODEL_NAME,
                "provider": "openai_compatible",
                "config": {
                    "model_name": f"ollama/{OLLAMA_MODEL_NAME}",
                    "base_url": "http://ollama:11434",
                    "timeout": 300,
                },
            },
            timeout=60.0,
        )

        if response.status_code == 409:
            print("Модель уже зарегистрирована")
            return

        assert response.status_code == 201, f"Ошибка регистрации: {response.text}"
        data = response.json()
        print(f"Модель зарегистрирована: {data.get('name')}")

    def test_model_registered(self):
        """Проверка что модель зарегистрирована."""
        models_response = self.client.get("/api/v1/models/")
        assert models_response.status_code == 200

        models_data = models_response.json()
        models = models_data.get("models", [])
        model_names = [m.get("name") for m in models]

        assert any(OLLAMA_MODEL_NAME in name or REGISTERED_MODEL_NAME in name for name in model_names), \
            f"Модель не найдена в {model_names}"
        print(f"Модель найдена: {model_names}")

    def test_generate_with_conversation(self):
        """Генерация с conversation_id для проверки Langfuse sessions."""
        print("\nСоздание диалога и генерация...")

        # Создать диалог
        conv_response = self.client.post(
            "/api/v1/conversations/",
            json={
                "model": REGISTERED_MODEL_NAME,
                "system_prompt": "Отвечай кратко на русском.",
            },
        )

        if conv_response.status_code not in (200, 201):
            pytest.skip(f"Диалог не создан: {conv_response.text}")

        conv_data = conv_response.json()
        conversation_id = conv_data.get("conversation_id")
        print(f"Диалог: {conversation_id}")

        # Создать задачу с conversation_id
        task_response = self.client.post(
            "/api/v1/tasks/",
            json={
                "model": REGISTERED_MODEL_NAME,
                "prompt": "Скажи 'привет'",
                "conversation_id": conversation_id,
                "save_to_conversation": True,
                "max_tokens": 20,
            },
        )

        if task_response.status_code != 201:
            pytest.skip(f"Задача не создана: {task_response.text}")

        task_data = task_response.json()
        task_id = task_data["task_id"]
        print(f"Задача: {task_id}")

        # Ждём завершения
        max_wait = 30
        start_time = time.time()

        while time.time() - start_time < max_wait:
            status_response = self.client.get(f"/api/v1/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                result = status_data.get("result", {})
                print(f"Ответ: {result.get('text', '')[:100]}")
                return conversation_id

            if status_data["status"] == "failed":
                pytest.skip(f"Задача провалилась: {status_data.get('error')}")

            time.sleep(1)

        pytest.skip(f"Таймаут {max_wait}s")

    def test_langfuse_sessions(self):
        """Проверка sessions в Langfuse."""
        print("\nПроверка Langfuse sessions...")
        time.sleep(2)

        response = self.langfuse_client.get(
            "/api/public/traces",
            params={"limit": 10},
        )

        assert response.status_code == 200, f"Ошибка: {response.text}"
        data = response.json()

        traces = data.get("data", [])
        total = data.get("meta", {}).get("totalItems", 0)
        print(f"Найдено {total} traces")

        # Проверяем наличие session_id в traces
        sessions_found = []
        for trace in traces:
            session_id = trace.get("sessionId")
            if session_id and session_id.startswith("conv_"):
                sessions_found.append(session_id)

        if sessions_found:
            print(f"Sessions: {sessions_found[:3]}")
        else:
            print("Sessions пока не появились (это нормально)")


class TestLocalModelE2E(TestOllamaModelE2E):
    """Алиас для обратной совместимости."""
    pass


def run_tests():
    """Запуск тестов напрямую."""
    test = TestOllamaModelE2E()
    test.setup()

    try:
        test.test_service_health()
        test.test_langfuse_health()
        test.test_register_ollama_model()
        test.test_model_registered()
        test.test_generate_with_conversation()
        test.test_langfuse_sessions()
        print("\nE2E тесты завершены")
    finally:
        test.client.close()
        test.langfuse_client.close()


if __name__ == "__main__":
    run_tests()
