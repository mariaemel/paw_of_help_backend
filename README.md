# Paw of Help Backend

Бэкенд-сервис для платформы помощи животным.


## Установка и запуск (PowerShell)

```powershell
cd paw_of_help
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
docker compose up -d db
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

## Установка и запуск (bash / Git Bash)h

```bash
cd paw_of_help
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
docker compose up -d db
cp .env.example .env
uvicorn app.main:app --reload
```


## Проверка

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)