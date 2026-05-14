import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_zametka(client: AsyncClient):
    """Проверяем базовое создание заметки и работу БД в памяти."""
    response = await client.post("/", json={"text": "Купить молоко и хлеб"})
    
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Купить молоко и хлеб"
    # Проверяем, что Pydantic-валидатор отработал и сам сгенерировал title
    assert data["title"] is not None


@pytest.mark.asyncio
async def test_process_text_mocked_ai(client: AsyncClient):
    """Проверяем интеллектуальный роутинг с подменой ответов ИИ (Mocking)."""
    # Подменяем (мокаем) асинхронный вызов клиента Groq на пустышку
    with patch("app.routers.zametki.aclient.chat.completions.create", new_callable=AsyncMock) as mock_create:
        # Имитируем успешный JSON-ответ от нейросети
        mock_create.return_value.choices[0].message.content = '{"intent": "NOTE", "text": "Очищенный текст заметки"}'
        
        response = await client.post("/process", json={"text": "Эй, ИИ! Сохрани: Очищенный текст заметки"})
        
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "NOTE"
        assert data["note"]["text"] == "Очищенный текст заметки"
        
        # Убеждаемся, что приложение действительно пыталось обратиться к ИИ 1 раз
        mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_delete_all_mocked_ai(client: AsyncClient):
    """Проверяем функционал очистки базы данных через ИИ."""
    with patch("app.routers.zametki.aclient.chat.completions.create", new_callable=AsyncMock) as mock_create:
        # Имитируем ответ нейросети, что пользователь хочет удалить всё
        mock_create.return_value.choices[0].message.content = '{"intent": "DELETE_ALL"}'
        
        response = await client.post("/process", json={"text": "удали все заметки полностью", "tg_chat_id": 12345})
        
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "DELETE_ALL"
        assert data["success"] is True
        mock_create.assert_called_once()