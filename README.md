
```markdown
# ZametkiTG


Система реализует работу с заметками и тэгизацию через ИИ:
1.  **FastAPI** принимает заметку и мгновенно сохраняет её в **PostgreSQL**.
2.  Задача на анализ текста отправляется в брокер **Redis**.
3.  Фоновый воркер **Celery** подхватывает задачу.
4.  Воркер делает запрос к **Groq API**, генерирует тег и обновляет запись в БД.

### 1. Настройка окружения
Создайте файл `.env`:

```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/zametki_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=zametki_db

REDIS_URL=redis://redis:6379/0

AI_API_KEY=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
AI_BASE_URL=https://api.groq.com/openai/v1
AI_MODEL=llama-3.3-70b-versatile

```

### 2. Запуск

```bash
docker compose up --build

```
