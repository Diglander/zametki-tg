
```markdown
# ZametkiTG


Система реализует работу с заметками и тэгизацию через ИИ:
1.  **FastAPI** принимает заметку и мгновенно сохраняет её в **PostgreSQL**.
2.  Задача на анализ текста отправляется в брокер **Redis**.
3.  Фоновый воркер **Celery** подхватывает задачу.
4.  Воркер делает запрос к **Groq API**, генерирует тег и обновляет запись в БД.

### 1. Настройка окружения
Создайте файл `.env`:
Удалите букву "X" в начале
```ini
XDATABASE_URL=Xpostgresql+asyncpg://postgres:postgres@db:5432/zametki_db
XPOSTGRES_USER=Xpostgres
XPOSTGRES_PASSWORD=Xpostgres
XPOSTGRES_DB=Xzametki_db

XREDIS_URL=Xredis://redis:6379/0

XAI_API_KEY=Xgsk_lqm5jP860FDAYj4dyrjbWGdyb3FYjktm1cPpSrsnPdLi7SudOO3K
XAI_BASE_URL=Xhttps://api.groq.com/openai/v1
XAI_MODEL=Xllama-3.3-70b-versatile

```

### 2. Запуск

```bash
docker compose up --build

```

### 3. Предупреждение

```bash
Сервис использует API (Groq), ограниченное для российских IP (VPN)

```