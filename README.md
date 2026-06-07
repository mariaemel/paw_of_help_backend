# Paw of Help Backend

Бэкенд-сервис для платформы помощи животным.

## Установка и запуск (PowerShell)

```powershell
cd paw_of_help
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d db redis
uvicorn app.main:app --reload
```

## Установка и запуск (bash / Git Bash)

```bash
cd paw_of_help
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db redis
uvicorn app.main:app --reload
```

## База данных

При старте `uvicorn` бэкенд **сам применяет миграции Alembic** и при необходимости заполняет демо-данные (`SEED_DEMO_DATA=true`).  
Ручной `ALTER TABLE` не нужен — достаточно поднять PostgreSQL (`docker compose up -d db`) и запустить API.

Если PostgreSQL ещё не готов, приложение подождёт до ~60 секунд и повторит подключение.

Отдельно миграции можно применить так:

```bash
alembic upgrade head
```


## Проверка

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)