import pytest

BASE_URL = "/api/v1/zametki"

@pytest.mark.asyncio
async def test_create_and_read_zametka(client):
    
    payload = {
        "text": "Тестовая заметка ",
        "title": "Заголовок теста"
    }
    
    response = await client.post(f"{BASE_URL}/", json=payload) # client из conftest.py
    
    # Проверки
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == payload["text"]
    assert "id" in data
    note_id = data["id"]

    response_get = await client.get(f"{BASE_URL}/{note_id}")
    
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert data_get["text"] == payload["text"]
    assert data_get["id"] == note_id