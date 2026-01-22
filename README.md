
```markdown
# ZametkiTG
<img width="850" height="379" alt="image" src="https://github.com/user-attachments/assets/0aa0b2a9-8fe2-4a2c-b02f-8a9b26edd9cd" />


Система реализует работу с заметками и тэгизацию через ИИ:
1.  FastAPI принимает заметку и мгновенно сохраняет её в PostgreSQL.
2.  Задача на анализ текста отправляется в брокер *Redis.
3.  Фоновый воркер Celery подхватывает задачу.
4.  Воркер делает запрос к Groq API, генерирует тег и обновляет запись в БД.

### 1. Настройка окружения
Создайте файл `.env`:

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

### 3. Предупреждение

```bash
Сервис использует API (Groq), ограниченное для российских IP (VPN)

```
