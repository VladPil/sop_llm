"""Integration тесты для Conversations API с Claude.

Тесты проверяют:
1. CRUD операции для диалогов
2. Multi-turn conversations с реальным Claude API
3. Сохранение и загрузка контекста

Требования:
- Сервис должен быть запущен (make up)
- ANTHROPIC_API_KEY должен быть установлен в .env
- Redis должен быть доступен
"""

import time
from typing import Any

import httpx
import pytest

# Конфигурация
BASE_URL = "http://localhost:8200"
API_PREFIX = "/api/v1"

# Имя модели Claude (alias из model_presets, не model_name!)
# В config/model_presets/cloud_models.yaml:
#   name: "claude-sonnet-4" <- это алиас для provider_registry
#   model_name: "claude-sonnet-4-20250514" <- это ID для LiteLLM API
CLAUDE_MODEL = "claude-sonnet-4"


@pytest.fixture(scope="module")
def client() -> httpx.Client:
    """HTTP клиент для тестов."""
    client = httpx.Client(base_url=BASE_URL, timeout=120.0)
    yield client
    client.close()


@pytest.fixture
def conversation_id(client: httpx.Client) -> str:
    """Создать диалог для теста и удалить после."""
    # Создать диалог
    response = client.post(
        f"{API_PREFIX}/conversations/",
        json={
            "model": CLAUDE_MODEL,
            "system_prompt": "Ты - тестовый ассистент. Отвечай кратко.",
        },
    )
    assert response.status_code == 201, f"Failed to create conversation: {response.text}"
    conv_id = response.json()["conversation_id"]

    yield conv_id

    # Удалить после теста
    client.delete(f"{API_PREFIX}/conversations/{conv_id}")


def wait_for_task(client: httpx.Client, task_id: str, timeout: int = 60) -> dict[str, Any]:
    """Ожидать завершения задачи."""
    start = time.time()
    while time.time() - start < timeout:
        response = client.get(f"{API_PREFIX}/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()

        if data["status"] in ("completed", "failed"):
            return data

        time.sleep(1)

    raise TimeoutError(f"Task {task_id} did not complete in {timeout}s")


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestConversationsAPI:
    """Тесты CRUD операций для диалогов."""

    def test_service_available(self, client: httpx.Client) -> None:
        """Проверка что сервис доступен."""
        response = client.get("/health")
        assert response.status_code == 200
        print("Service is available")

    def test_create_conversation(self, client: httpx.Client) -> None:
        """Тест создания диалога."""
        response = client.post(
            f"{API_PREFIX}/conversations/",
            json={
                "model": CLAUDE_MODEL,
                "system_prompt": "Test system prompt",
                "metadata": {"test": True},
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert "conversation_id" in data
        assert data["conversation_id"].startswith("conv_")
        assert data["model"] == CLAUDE_MODEL
        assert data["system_prompt"] == "Test system prompt"
        assert data["message_count"] >= 1  # system prompt as first message

        print(f"Created conversation: {data['conversation_id']}")

        # Cleanup
        client.delete(f"{API_PREFIX}/conversations/{data['conversation_id']}")

    def test_create_conversation_minimal(self, client: httpx.Client) -> None:
        """Тест создания диалога с минимальными параметрами."""
        response = client.post(f"{API_PREFIX}/conversations/", json={})

        assert response.status_code == 201
        data = response.json()

        assert "conversation_id" in data
        assert data["model"] is None
        assert data["message_count"] == 0

        # Cleanup
        client.delete(f"{API_PREFIX}/conversations/{data['conversation_id']}")

    def test_get_conversation(self, client: httpx.Client, conversation_id: str) -> None:
        """Тест получения диалога."""
        response = client.get(f"{API_PREFIX}/conversations/{conversation_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["conversation_id"] == conversation_id
        assert "messages" in data  # include_messages=true by default
        print(f"Got conversation with {data['message_count']} messages")

    def test_get_conversation_not_found(self, client: httpx.Client) -> None:
        """Тест получения несуществующего диалога."""
        response = client.get(f"{API_PREFIX}/conversations/conv_nonexistent123")

        assert response.status_code == 404

    def test_list_conversations(self, client: httpx.Client, conversation_id: str) -> None:
        """Тест получения списка диалогов."""
        response = client.get(f"{API_PREFIX}/conversations/")

        assert response.status_code == 200
        data = response.json()

        assert "conversations" in data
        assert "total" in data
        assert data["total"] >= 1

        # Проверяем что наш диалог в списке
        conv_ids = [c["conversation_id"] for c in data["conversations"]]
        assert conversation_id in conv_ids

    def test_update_conversation(self, client: httpx.Client, conversation_id: str) -> None:
        """Тест обновления диалога."""
        response = client.patch(
            f"{API_PREFIX}/conversations/{conversation_id}",
            json={
                "model": "gpt-4-turbo",
                "metadata": {"updated": True},
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["model"] == "gpt-4-turbo"

    def test_add_message_manually(self, client: httpx.Client, conversation_id: str) -> None:
        """Тест ручного добавления сообщения."""
        response = client.post(
            f"{API_PREFIX}/conversations/{conversation_id}/messages",
            json={
                "role": "user",
                "content": "Manual test message",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["role"] == "user"
        assert data["content"] == "Manual test message"

    def test_get_messages(self, client: httpx.Client, conversation_id: str) -> None:
        """Тест получения сообщений."""
        # Добавим сообщение
        client.post(
            f"{API_PREFIX}/conversations/{conversation_id}/messages",
            json={"role": "user", "content": "Test message"},
        )

        response = client.get(f"{API_PREFIX}/conversations/{conversation_id}/messages")

        assert response.status_code == 200
        data = response.json()

        assert "messages" in data
        assert len(data["messages"]) >= 1

    def test_clear_messages(self, client: httpx.Client) -> None:
        """Тест очистки сообщений."""
        # Создаём диалог с сообщениями
        create_resp = client.post(
            f"{API_PREFIX}/conversations/",
            json={"system_prompt": "Test"},
        )
        conv_id = create_resp.json()["conversation_id"]

        # Очищаем
        response = client.delete(f"{API_PREFIX}/conversations/{conv_id}/messages")
        assert response.status_code == 204

        # Проверяем что пусто
        get_resp = client.get(f"{API_PREFIX}/conversations/{conv_id}")
        assert get_resp.json()["message_count"] == 0

        # Cleanup
        client.delete(f"{API_PREFIX}/conversations/{conv_id}")

    def test_delete_conversation(self, client: httpx.Client) -> None:
        """Тест удаления диалога."""
        # Создаём
        create_resp = client.post(f"{API_PREFIX}/conversations/", json={})
        conv_id = create_resp.json()["conversation_id"]

        # Удаляем
        response = client.delete(f"{API_PREFIX}/conversations/{conv_id}")
        assert response.status_code == 204

        # Проверяем что удалён
        get_resp = client.get(f"{API_PREFIX}/conversations/{conv_id}")
        assert get_resp.status_code == 404


@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.slow
class TestConversationsWithClaude:
    """Тесты multi-turn conversations с реальным Claude API."""

    def test_check_claude_available(self, client: httpx.Client) -> None:
        """Проверка что Claude модель зарегистрирована."""
        # Создаём тестовую задачу чтобы проверить что модель работает
        # API /models/ возвращает model_name, а не alias, поэтому проверяем через
        # создание задачи с конкретной моделью
        response = client.post(
            f"{API_PREFIX}/tasks/",
            json={
                "model": CLAUDE_MODEL,
                "prompt": "Say 'test'",
            },
        )

        # Если модель не зарегистрирована - будет 404
        assert response.status_code in (201, 400), (
            f"Claude model {CLAUDE_MODEL} not available. Error: {response.text}"
        )
        print(f"Claude model {CLAUDE_MODEL} is available")

        # Cleanup - удаляем задачу если создалась
        if response.status_code == 201:
            task_id = response.json().get("task_id")
            if task_id:
                client.delete(f"{API_PREFIX}/tasks/{task_id}")

    def test_single_turn_with_conversation(self, client: httpx.Client) -> None:
        """Тест одного запроса с conversation_id."""
        # Создаём диалог
        conv_resp = client.post(
            f"{API_PREFIX}/conversations/",
            json={
                "model": CLAUDE_MODEL,
                "system_prompt": "You are a helpful assistant. Answer briefly.",
            },
        )
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["conversation_id"]
        print(f"Created conversation: {conv_id}")

        try:
            # Отправляем сообщение
            task_resp = client.post(
                f"{API_PREFIX}/tasks/",
                json={
                    "conversation_id": conv_id,
                    "prompt": "What is 2+2? Answer with just the number.",
                },
            )
            assert task_resp.status_code == 201
            task_id = task_resp.json()["task_id"]
            print(f"Created task: {task_id}")

            # Ждём результат
            result = wait_for_task(client, task_id)

            assert result["status"] == "completed", f"Task failed: {result.get('error')}"
            assert "result" in result
            assert "text" in result["result"]

            response_text = result["result"]["text"]
            print(f"Claude response: {response_text}")

            # Проверяем что ответ содержит 4
            assert "4" in response_text

            # Проверяем что сообщения сохранились
            messages_resp = client.get(f"{API_PREFIX}/conversations/{conv_id}/messages")
            messages = messages_resp.json()["messages"]

            # system + user + assistant = 3
            assert len(messages) >= 3, f"Expected 3+ messages, got {len(messages)}"
            print(f"Conversation has {len(messages)} messages")

        finally:
            client.delete(f"{API_PREFIX}/conversations/{conv_id}")

    def test_multi_turn_conversation(self, client: httpx.Client) -> None:
        """Тест multi-turn диалога с сохранением контекста."""
        # Создаём диалог
        conv_resp = client.post(
            f"{API_PREFIX}/conversations/",
            json={
                "model": CLAUDE_MODEL,
                "system_prompt": "You are a helpful assistant. Remember everything the user tells you.",
            },
        )
        conv_id = conv_resp.json()["conversation_id"]
        print(f"Created conversation: {conv_id}")

        try:
            # Первое сообщение - представляемся
            task1_resp = client.post(
                f"{API_PREFIX}/tasks/",
                json={
                    "conversation_id": conv_id,
                    "prompt": "My name is TestUser123. Remember this name.",
                },
            )
            task1_id = task1_resp.json()["task_id"]
            result1 = wait_for_task(client, task1_id)
            assert result1["status"] == "completed"
            print(f"Turn 1 response: {result1['result']['text'][:100]}...")

            # Второе сообщение - спрашиваем имя
            task2_resp = client.post(
                f"{API_PREFIX}/tasks/",
                json={
                    "conversation_id": conv_id,
                    "prompt": "What is my name? Just say the name.",
                },
            )
            task2_id = task2_resp.json()["task_id"]
            result2 = wait_for_task(client, task2_id)
            assert result2["status"] == "completed"

            response_text = result2["result"]["text"]
            print(f"Turn 2 response: {response_text}")

            # Проверяем что Claude помнит имя
            assert "TestUser123" in response_text, (
                f"Claude didn't remember the name. Response: {response_text}"
            )
            print("Claude remembered the name from context!")

            # Проверяем количество сообщений
            messages_resp = client.get(f"{API_PREFIX}/conversations/{conv_id}/messages")
            messages = messages_resp.json()["messages"]
            # system + 2*(user + assistant) = 5
            assert len(messages) >= 5, f"Expected 5+ messages, got {len(messages)}"
            print(f"Total messages in conversation: {len(messages)}")

        finally:
            client.delete(f"{API_PREFIX}/conversations/{conv_id}")

    def test_conversation_without_save(self, client: httpx.Client) -> None:
        """Тест запроса с save_to_conversation=false."""
        # Создаём диалог
        conv_resp = client.post(
            f"{API_PREFIX}/conversations/",
            json={"model": CLAUDE_MODEL},
        )
        conv_id = conv_resp.json()["conversation_id"]

        try:
            # Получаем начальное количество сообщений
            initial_resp = client.get(f"{API_PREFIX}/conversations/{conv_id}")
            initial_count = initial_resp.json()["message_count"]

            # Отправляем сообщение без сохранения
            task_resp = client.post(
                f"{API_PREFIX}/tasks/",
                json={
                    "conversation_id": conv_id,
                    "prompt": "Say hello",
                    "save_to_conversation": False,
                },
            )
            task_id = task_resp.json()["task_id"]
            result = wait_for_task(client, task_id)
            assert result["status"] == "completed"

            # Проверяем что количество сообщений не изменилось
            final_resp = client.get(f"{API_PREFIX}/conversations/{conv_id}")
            final_count = final_resp.json()["message_count"]

            assert final_count == initial_count, (
                f"Messages were saved despite save_to_conversation=false. "
                f"Initial: {initial_count}, Final: {final_count}"
            )
            print("Message was NOT saved to conversation (as expected)")

        finally:
            client.delete(f"{API_PREFIX}/conversations/{conv_id}")


if __name__ == "__main__":
    # Для быстрого запуска отдельных тестов
    pytest.main([__file__, "-v", "-s"])
